"""Kronos backtest engine — samples historical candles, runs inference with context, measures accuracy."""

from __future__ import annotations

import logging
import random
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from bitpredict.db_models import Kline
from bitpredict.kronos.inference import run_inference
from bitpredict.kronos.timeframes import Timeframe

logger = logging.getLogger(__name__)

# How many historical samples to evaluate per timeframe
_SAMPLE_SIZES: dict[str, int] = {
    "15m": 500,
    "1h":  200,
    "4h":  200,
    "8h":  200,
    "1d":  200,
    "1w":  None,  # None = use all available
}


def select_sample_candles(
    db: Session,
    timeframe: Timeframe,
    sample_size: int | None = None,
    seed: int | None = None,
) -> list[datetime]:
    """Return a list of target candle open_times to backtest.

    Each returned datetime points to a CLOSED candle that has enough
    historical context (≥512 candles) before it.
    """
    interval = timeframe.to_binance_interval()
    context_needed = 513  # 512 context + 1 target

    all_times = db.execute(
        select(Kline.open_time)
        .where(Kline.symbol == "BTCUSDT", Kline.interval == interval)
        .order_by(Kline.open_time.asc())
    ).scalars().all()

    if len(all_times) < context_needed:
        logger.warning(
            "Not enough candles for backtest: tf=%s have=%d need=%d",
            timeframe.value, len(all_times), context_needed,
        )
        return []

    # Only candles that have at least 512 candles before them
    eligible = list(all_times[512:])

    n = sample_size if sample_size is not None else _SAMPLE_SIZES.get(timeframe.value)
    if n is None:
        return [dt for dt in eligible if isinstance(dt, datetime)]

    rng = random.Random(seed)
    chosen = rng.sample(eligible, min(n, len(eligible)))
    return sorted(chosen)


def run_single_backtest_point(
    db: Session,
    timeframe: Timeframe,
    target_open_time: datetime,
    model_variant: str = "small",
    sample_count: int = 10,
    temperature: float = 0.8,
    stop_check=None,
    sim_progress_callback=None,
) -> dict[str, Any] | None:
    """Run inference for one historical target candle and compare to actual values.

    Returns None if the actual candle is not in the DB (gap in data).
    """
    interval = timeframe.to_binance_interval()

    # Load 512 context candles strictly before target_open_time
    context_rows = db.execute(
        select(Kline)
        .where(
            Kline.symbol == "BTCUSDT",
            Kline.interval == interval,
            Kline.open_time < target_open_time,
        )
        .order_by(Kline.open_time.desc())
        .limit(512)
    ).scalars().all()

    if len(context_rows) < 10:
        return None

    context_rows = sorted(context_rows, key=lambda k: k.open_time)
    context_df = pd.DataFrame([{
        "open_time": k.open_time,
        "open":   float(k.open),
        "high":   float(k.high),
        "low":    float(k.low),
        "close":  float(k.close),
        "volume": float(k.volume),
    } for k in context_rows])
    context_df["open_time"] = pd.to_datetime(context_df["open_time"], utc=True)

    # Fetch actual candle
    actual_row = db.execute(
        select(Kline)
        .where(
            Kline.symbol == "BTCUSDT",
            Kline.interval == interval,
            Kline.open_time == target_open_time,
        )
    ).scalar_one_or_none()

    if actual_row is None:
        return None

    if stop_check and stop_check():
        return None

    result = run_inference(
        timeframe=timeframe,
        context_candles=context_df,
        sample_count=sample_count,
        model_variant=model_variant,
        temperature=temperature,
        target_candle_open=target_open_time,
        stop_check=stop_check,
        progress_callback=sim_progress_callback,
    )

    actual_close = float(actual_row.close)
    last_close = float(context_rows[-1].close)
    pred_close = result["predicted_close"]
    pred_dir_up = pred_close > last_close
    actual_dir_up = actual_close > last_close

    return {
        "target_open_time": target_open_time,
        "predicted_close":  pred_close,
        "predicted_high":   result["predicted_high"],
        "predicted_low":    result["predicted_low"],
        "q10_close":        result["q10_close"],
        "q90_close":        result["q90_close"],
        "actual_open":      float(actual_row.open),
        "actual_close":     actual_close,
        "actual_high":      float(actual_row.high),
        "actual_low":       float(actual_row.low),
        "prob_bullish":     result.get("prob_bullish", 0.5),
        "direction_correct": pred_dir_up == actual_dir_up,
        "close_error_pct":  ((pred_close - actual_close) / actual_close * 100) if actual_close != 0 else None,
        "band_covers_actual": result["q10_close"] <= actual_close <= result["q90_close"],
    }


def aggregate_backtest_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary metrics from a list of single-point backtest results."""
    if not results:
        return {}

    def _mape(pred_key: str, actual_key: str) -> float | None:
        vals = [
            abs(r[pred_key] - r[actual_key]) / r[actual_key] * 100
            for r in results
            if r.get(pred_key) is not None and r.get(actual_key) and r[actual_key] != 0
        ]
        return float(np.mean(vals)) if vals else None

    directional_accuracy = float(np.mean([r["direction_correct"] for r in results])) * 100

    band_widths = [
        (r["q90_close"] - r["q10_close"]) / r["actual_close"] * 100
        for r in results
        if r.get("q90_close") and r.get("q10_close") and r.get("actual_close")
    ]
    band_calibration = float(np.mean([r["band_covers_actual"] for r in results])) * 100

    # High-confidence accuracy: samples where model had ≥70% conviction either way.
    # prob_bullish >= 0.70 means confident bullish; <= 0.30 means confident bearish (70% bearish).
    HIGH_CONF_THRESHOLD = 0.70
    high_conf = [
        r for r in results
        if r.get("prob_bullish") is not None
        and (r["prob_bullish"] >= HIGH_CONF_THRESHOLD or r["prob_bullish"] <= (1 - HIGH_CONF_THRESHOLD))
    ]
    high_conf_accuracy = float(np.mean([r["direction_correct"] for r in high_conf])) * 100 if high_conf else None
    high_conf_count = len(high_conf)

    return {
        "sample_size":          len(results),
        "directional_accuracy": directional_accuracy,
        "mape_close":           _mape("predicted_close", "actual_close"),
        "mape_high":            _mape("predicted_high",  "actual_high"),
        "mape_low":             _mape("predicted_low",   "actual_low"),
        "band_width_pct_avg":   float(np.mean(band_widths)) if band_widths else None,
        "band_calibration_pct": band_calibration,
        "high_conf_accuracy":   high_conf_accuracy,
        "high_conf_count":      high_conf_count,
    }


def simulate_portfolio(
    results: list[dict[str, Any]],
    initial_capital: float,
    position_pct: float,
    compound: bool,
) -> dict[str, Any]:
    """Run a paper-trading simulation over backtest results.

    Each sample becomes one trade:
      - Long  when prob_bullish >= 0.5  (entry=actual_open, exit=actual_close)
      - Short when prob_bullish <  0.5  (entry=actual_open, exit=actual_close, P&L inverted)
    """
    capital = initial_capital
    equity: list[float] = [capital]
    trade_returns: list[float] = []

    # Sort chronologically so equity curve is meaningful
    ordered = sorted(results, key=lambda r: r["target_open_time"])

    for r in ordered:
        open_px  = r.get("actual_open")
        close_px = r.get("actual_close")
        prob     = r.get("prob_bullish", 0.5)

        if not open_px or not close_px or open_px == 0:
            continue

        is_long  = prob >= 0.5
        raw_ret  = (close_px - open_px) / open_px          # positive = price went up
        trade_ret = raw_ret if is_long else -raw_ret        # short inverts sign

        pos_size = (capital if compound else initial_capital) * position_pct
        capital += pos_size * trade_ret
        equity.append(capital)
        trade_returns.append(trade_ret)

    if not trade_returns:
        return {}

    tr = np.array(trade_returns)
    wins   = tr[tr > 0]
    losses = tr[tr <= 0]

    gross_profit = float(wins.sum())   if len(wins)   > 0 else 0.0
    gross_loss   = float(-losses.sum()) if len(losses) > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    avg_win  = float(wins.mean())    if len(wins)   > 0 else 0.0
    avg_loss = float(-losses.mean()) if len(losses) > 0 else 0.0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else None

    # Max drawdown on equity curve
    peak = equity[0]
    max_dd_abs = 0.0
    for eq in equity:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd_abs:
            max_dd_abs = dd
    max_dd_pct = (max_dd_abs / initial_capital * 100) if initial_capital > 0 else 0.0

    # Max consecutive losses
    max_consec = cur_consec = 0
    for ret in trade_returns:
        if ret <= 0:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0

    net_profit     = capital - initial_capital
    net_profit_pct = net_profit / initial_capital * 100 if initial_capital > 0 else 0.0
    recovery_factor = net_profit / max_dd_abs if max_dd_abs > 0 else None

    sharpe: float | None = None
    if len(tr) > 1 and float(np.std(tr)) > 0:
        sharpe = float(np.mean(tr) / np.std(tr) * np.sqrt(len(tr)))

    return {
        "final_equity":           round(capital, 2),
        "net_profit":             round(net_profit, 2),
        "net_profit_pct":         round(net_profit_pct, 4),
        "profit_factor":          round(profit_factor, 4) if profit_factor is not None else None,
        "win_rate_pct":           round(len(wins) / len(tr) * 100, 2),
        "payoff_ratio":           round(payoff_ratio, 4) if payoff_ratio is not None else None,
        "max_drawdown_pct":       round(max_dd_pct, 4),
        "max_consecutive_losses": max_consec,
        "recovery_factor":        round(recovery_factor, 4) if recovery_factor is not None else None,
        "sharpe_ratio":           round(sharpe, 4) if sharpe is not None else None,
        "avg_trade_pct":          round(float(np.mean(tr)) * 100, 4),
        "best_trade_pct":         round(float(np.max(tr)) * 100, 4),
        "worst_trade_pct":        round(float(np.min(tr)) * 100, 4),
        "total_trades":           len(trade_returns),
    }


def run_backtest(
    db: Session,
    timeframe: Timeframe,
    model_variant: str = "small",
    sample_count: int = 30,
    sample_size: int | None = None,
    temperature: float = 0.8,
    initial_capital: float | None = None,
    position_pct: float | None = None,
    compound: bool = False,
    task_id: str | None = None,
    stop_check=None,
    progress_callback=None,
    sim_progress_callback=None,
) -> dict[str, Any]:
    """Full backtest pipeline for one timeframe. Returns metrics dict."""
    from bitpredict.db_models import KronosBacktest
    from sqlalchemy import text as _text

    # sample_size override: if provided use it, otherwise fall back to _SAMPLE_SIZES default
    n = sample_size if sample_size is not None else _SAMPLE_SIZES.get(timeframe.value)
    targets = select_sample_candles(db, timeframe, sample_size=n)
    total = len(targets)
    logger.info("Kronos backtest starting: tf=%s samples=%d variant=%s", timeframe.value, total, model_variant)

    started_at = time.monotonic()
    results: list[dict[str, Any]] = []

    # Initialize progress so sim_progress_callback knows the total before the first sample
    if progress_callback:
        progress_callback(0, total)

    for i, target_time in enumerate(targets):
        if stop_check and stop_check():
            logger.info("Kronos backtest stopped at sample %d/%d", i, total)
            break

        point = run_single_backtest_point(
            db=db,
            timeframe=timeframe,
            target_open_time=target_time,
            model_variant=model_variant,
            sample_count=sample_count,
            temperature=temperature,
            stop_check=stop_check,
            sim_progress_callback=sim_progress_callback,
        )
        if point is not None:
            results.append(point)

        if progress_callback:
            progress_callback(i + 1, total)

    duration = time.monotonic() - started_at
    metrics = aggregate_backtest_results(results)

    status = "stopped_by_user" if (stop_check and stop_check()) else "done"
    if not results:
        status = "error"

    sample_from = min(targets) if targets else None
    sample_to   = max(targets) if targets else None

    # Portfolio simulation (only if parameters were provided)
    portfolio: dict[str, Any] = {}
    if initial_capital is not None and position_pct is not None and results:
        portfolio = simulate_portfolio(results, initial_capital, position_pct, compound)

    next_id = db.execute(_text("SELECT nextval('kronos_backtests_id_seq')")).scalar_one()
    record = KronosBacktest(
        id=next_id,
        executed_at=datetime.now(tz=UTC),
        timeframe=timeframe.value,
        sample_size=len(results),
        model_variant=model_variant,
        sample_count=sample_count,
        context_length=512,
        directional_accuracy=metrics.get("directional_accuracy"),
        mape_close=metrics.get("mape_close"),
        mape_high=metrics.get("mape_high"),
        mape_low=metrics.get("mape_low"),
        mape_volume=None,
        band_width_pct_avg=metrics.get("band_width_pct_avg"),
        band_calibration_pct=metrics.get("band_calibration_pct"),
        high_conf_accuracy=metrics.get("high_conf_accuracy"),
        high_conf_count=metrics.get("high_conf_count"),
        duration_seconds=int(duration),
        status=status,
        task_id=task_id,
        sample_from=sample_from,
        sample_to=sample_to,
        # portfolio params
        initial_capital=initial_capital,
        position_pct=position_pct,
        compound=compound,
        # portfolio results
        final_equity=portfolio.get("final_equity"),
        net_profit=portfolio.get("net_profit"),
        net_profit_pct=portfolio.get("net_profit_pct"),
        profit_factor=portfolio.get("profit_factor"),
        win_rate_pct=portfolio.get("win_rate_pct"),
        payoff_ratio=portfolio.get("payoff_ratio"),
        max_drawdown_pct=portfolio.get("max_drawdown_pct"),
        max_consecutive_losses=portfolio.get("max_consecutive_losses"),
        recovery_factor=portfolio.get("recovery_factor"),
        sharpe_ratio=portfolio.get("sharpe_ratio"),
        avg_trade_pct=portfolio.get("avg_trade_pct"),
        best_trade_pct=portfolio.get("best_trade_pct"),
        worst_trade_pct=portfolio.get("worst_trade_pct"),
        total_trades=portfolio.get("total_trades"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "Kronos backtest saved: tf=%s id=%d dir_acc=%.1f%% net_profit=%.2f",
        timeframe.value, record.id,
        metrics.get("directional_accuracy", 0),
        portfolio.get("net_profit", 0) or 0,
    )
    return {"record_id": record.id, "metrics": metrics, "portfolio": portfolio, "status": status}
