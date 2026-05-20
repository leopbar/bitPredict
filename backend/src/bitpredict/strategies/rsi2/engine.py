"""Backtest engine for RSI-2: long+short, per-trade stop/target/timeout, costs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import polars as pl

from bitpredict.strategies.rsi2.config import Rsi2Params
from bitpredict.strategies.rsi2.costs import compute_net_pnl_pct
from bitpredict.strategies.rsi2.signals import SignalRow


@dataclass
class TradeResult:
    entry_time: datetime
    exit_time: datetime
    side: str
    entry_price: float
    exit_price: float
    stop_price: float
    gross_pnl_pct: float
    net_pnl_pct: float
    exit_reason: str   # "target" | "stop" | "timeout"
    bars_held: int
    label: int = 0     # 1=win (exit=target), 0=loss — used by meta-labeling


@dataclass
class BacktestResult:
    trades: list[TradeResult]
    equity: np.ndarray           # cumulative equity curve (starts at 1.0)
    times: list[datetime]
    n_long: int
    n_short: int
    params: Rsi2Params


def _get_funding_rate(funding_series: list[tuple[datetime, float]], ts: datetime) -> float:
    """Return the most recent funding rate at or before *ts*."""
    best = 0.0
    best_ts: datetime | None = None
    for fts, frate in funding_series:
        if fts <= ts:
            if best_ts is None or fts > best_ts:
                best_ts = fts
                best = frate
    return best


def run_backtest(
    df: pl.DataFrame,
    signals: list[SignalRow],
    params: Rsi2Params,
    funding_series: list[tuple[datetime, float]] | None = None,
    meta_mask: list[bool] | None = None,
) -> BacktestResult:
    """Simulate the RSI-2 strategy bar-by-bar.

    Args:
        df: Feature DataFrame with OHLCV + RSI columns, sorted by open_time.
        signals: Pre-computed candidate signals from signals.py.
        params: Strategy parameters.
        funding_series: List of (funding_time, rate) tuples sorted by time.
        meta_mask: Optional bool mask aligned with signals list. If provided,
                   only signals where mask[i]=True are taken.

    Returns:
        BacktestResult with all completed trades and equity curve.
    """
    if funding_series is None:
        funding_series = []

    rows = df.to_dicts()
    n = len(rows)
    rsi2_values = [r.get("rsi_2") for r in rows]
    open_times = [r["open_time"] for r in rows]

    # Build signal lookup: bar_index → SignalRow (first signal per bar, filtered)
    signal_map: dict[int, SignalRow] = {}
    for i, sig in enumerate(signals):
        if meta_mask is not None and not meta_mask[i]:
            continue
        if sig.bar_index not in signal_map:
            signal_map[sig.bar_index] = sig

    trades: list[TradeResult] = []
    equity_series: list[float] = [1.0]
    equity_val = 1.0

    in_position = False
    current_trade_side: str = ""
    current_entry_bar: int = 0
    current_entry_price: float = 0.0
    current_stop_price: float = 0.0
    current_target_price: float | None = None  # price-based target; None → use RSI exit
    current_entry_time: datetime = datetime(2000, 1, 1, tzinfo=UTC)

    for t in range(n):
        row = rows[t]
        high_t = float(row["high"])
        low_t = float(row["low"])
        close_t = float(row["close"])
        open_time_t = open_times[t]
        if open_time_t.tzinfo is None:
            open_time_t = open_time_t.replace(tzinfo=UTC)

        if in_position:
            bars_held = t - current_entry_bar
            rsi_t = rsi2_values[t]
            exit_reason: str | None = None
            exit_price: float = close_t

            if current_trade_side == "long":
                # Price target (N×R) has priority when configured
                if current_target_price is not None and high_t >= current_target_price:
                    exit_reason = "target"
                    exit_price = current_target_price
                # Stop hit
                elif low_t <= current_stop_price:
                    exit_reason = "stop"
                    exit_price = current_stop_price
                # RSI exit (only when no price target is set)
                elif current_target_price is None and rsi_t is not None and rsi_t >= params.rsi_exit_long:
                    exit_reason = "target"
                    exit_price = close_t
                # Timeout
                elif params.timeout_bars > 0 and bars_held >= params.timeout_bars:
                    exit_reason = "timeout"
                    exit_price = close_t

            else:  # short
                # Price target has priority when configured
                if current_target_price is not None and low_t <= current_target_price:
                    exit_reason = "target"
                    exit_price = current_target_price
                # Stop hit
                elif high_t >= current_stop_price:
                    exit_reason = "stop"
                    exit_price = current_stop_price
                # RSI exit (only when no price target is set)
                elif current_target_price is None and rsi_t is not None and rsi_t <= params.rsi_exit_short:
                    exit_reason = "target"
                    exit_price = close_t
                # Timeout
                elif params.timeout_bars > 0 and bars_held >= params.timeout_bars:
                    exit_reason = "timeout"
                    exit_price = close_t

            if exit_reason is not None:
                # Compute funding average over holding period
                funding_avg = _get_funding_rate(funding_series, open_time_t)

                gross_pct, net_pct = compute_net_pnl_pct(
                    side=current_trade_side,
                    entry_price_raw=current_entry_price,
                    exit_price_raw=exit_price,
                    exit_reason=exit_reason,
                    entry_time=current_entry_time,
                    exit_time=open_time_t,
                    funding_rate_avg=funding_avg,
                    params=params,
                )

                label = 1 if exit_reason == "target" else 0
                trade = TradeResult(
                    entry_time=current_entry_time,
                    exit_time=open_time_t,
                    side=current_trade_side,
                    entry_price=current_entry_price,
                    exit_price=exit_price,
                    stop_price=current_stop_price,
                    gross_pnl_pct=gross_pct,
                    net_pnl_pct=net_pct,
                    exit_reason=exit_reason,
                    bars_held=bars_held,
                    label=label,
                )
                trades.append(trade)
                equity_val *= (1.0 + net_pct)
                in_position = False

        # After checking exit, check for new entry signal (only if not in position)
        if not in_position and t in signal_map:
            sig = signal_map[t]
            in_position = True
            current_trade_side = sig.side
            current_entry_bar = t
            current_entry_price = sig.entry_price
            current_stop_price = sig.stop_price
            current_entry_time = open_time_t

            # Compute price-based profit target when target_r_multiple > 0
            if params.target_r_multiple > 0:
                r_dist = abs(current_entry_price - current_stop_price)
                if current_trade_side == "long":
                    current_target_price = current_entry_price + params.target_r_multiple * r_dist
                else:
                    current_target_price = current_entry_price - params.target_r_multiple * r_dist
            else:
                current_target_price = None

        equity_series.append(equity_val)

    # Force-close any open position at last bar
    if in_position and len(rows) > 0:
        last_row = rows[-1]
        last_time = open_times[-1]
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=UTC)

        funding_avg = _get_funding_rate(funding_series, last_time)
        gross_pct, net_pct = compute_net_pnl_pct(
            side=current_trade_side,
            entry_price_raw=current_entry_price,
            exit_price_raw=float(last_row["close"]),
            exit_reason="timeout",
            entry_time=current_entry_time,
            exit_time=last_time,
            funding_rate_avg=funding_avg,
            params=params,
        )
        trades.append(
            TradeResult(
                entry_time=current_entry_time,
                exit_time=last_time,
                side=current_trade_side,
                entry_price=current_entry_price,
                exit_price=float(last_row["close"]),
                stop_price=current_stop_price,
                gross_pnl_pct=gross_pct,
                net_pnl_pct=net_pct,
                exit_reason="timeout",
                bars_held=n - 1 - current_entry_bar,
                label=0,
            )
        )
        equity_val *= (1.0 + net_pct)
        equity_series.append(equity_val)

    n_long = sum(1 for t in trades if t.side == "long")
    n_short = sum(1 for t in trades if t.side == "short")

    return BacktestResult(
        trades=trades,
        equity=np.array(equity_series),
        times=list(open_times),
        n_long=n_long,
        n_short=n_short,
        params=params,
    )
