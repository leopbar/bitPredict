"""Kronos stochastic inference — runs sample_count independent trajectories and aggregates."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from bitpredict.kronos.loader import get_predictor
from bitpredict.kronos.timeframes import Timeframe

logger = logging.getLogger(__name__)


def run_inference(
    timeframe: Timeframe | str,
    context_candles: pd.DataFrame,
    sample_count: int = 30,
    model_variant: str = "small",
    temperature: float = 0.8,
    target_candle_open: datetime | None = None,
    stop_check=None,
    progress_callback=None,
) -> dict:
    """Run Kronos stochastic inference for the next candle of *timeframe*.

    Calls predictor.predict() *sample_count* times independently (sample_count=1 each call)
    to produce a distribution of predictions. KronosPredictor.predict(sample_count=N>1)
    returns only 1 aggregated row; independent calls with T>0 produce variance.

    Args:
        timeframe: Target timeframe.
        context_candles: DataFrame with columns open_time, open, high, low, close, volume.
        sample_count: Number of independent stochastic trajectories (default 30).
        model_variant: "small" or "base".
        temperature: Sampling temperature (default 0.8). Higher = more variance.
        target_candle_open: Override target candle open time (used in backtesting).
        stop_check: Optional callable() → bool. If returns True, inference is stopped early.
        progress_callback: Optional callable(current, total) for progress reporting.

    Returns dict with medians, Q10/Q90, prob_bullish, raw_samples, and config snapshot.
    """
    if isinstance(timeframe, str):
        timeframe = Timeframe(timeframe)

    predictor = get_predictor(model_variant)

    x_df = context_candles[["open", "high", "low", "close", "volume"]].copy()
    x_timestamp = context_candles["open_time"].copy()

    now = datetime.now(tz=UTC)
    if target_candle_open is None:
        # Use the candle currently forming on Binance (floor wall-clock to 15m boundary).
        # At 17:01 → 17:00; at 17:31 → 17:30. Matches what the user sees as "the current candle".
        target_open = timeframe.current_candle_boundary(now)
    else:
        target_open = (
            target_candle_open
            if target_candle_open.tzinfo
            else target_candle_open.replace(tzinfo=UTC)
        )

    target_close = target_open + timeframe.to_timedelta()
    y_timestamp = pd.Series([target_open])

    logger.debug(
        "Kronos inference: tf=%s variant=%s samples=%d target=%s",
        timeframe.value, model_variant, sample_count, target_open.isoformat(),
    )

    samples: list[dict] = []
    for i in range(sample_count):
        if stop_check and stop_check():
            logger.info("Kronos inference stopped at sample %d/%d", i, sample_count)
            break

        pred_df: pd.DataFrame = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=1,
            T=temperature,
            top_p=0.9,
            sample_count=1,
            verbose=False,
        )

        samples.append({
            "open":   float(pred_df["open"].iloc[0]),
            "high":   float(pred_df["high"].iloc[0]),
            "low":    float(pred_df["low"].iloc[0]),
            "close":  float(pred_df["close"].iloc[0]),
            "volume": float(pred_df["volume"].iloc[0]),
        })

        if progress_callback:
            progress_callback(i + 1, sample_count)

    if not samples:
        raise RuntimeError("Inference stopped before producing any samples.")

    closes  = np.array([s["close"]  for s in samples])
    opens   = np.array([s["open"]   for s in samples])
    highs   = np.array([s["high"]   for s in samples])
    lows    = np.array([s["low"]    for s in samples])
    volumes = np.array([s["volume"] for s in samples])

    last_close = float(context_candles["close"].iloc[-1])

    return {
        "target_candle_open_time":  target_open,
        "target_candle_close_time": target_close,
        "predicted_open":   float(np.median(opens)),
        "predicted_high":   float(np.median(highs)),
        "predicted_low":    float(np.median(lows)),
        "predicted_close":  float(np.median(closes)),
        "predicted_volume": float(np.median(volumes)),
        "q10_close":    float(np.percentile(closes, 10)),
        "q90_close":    float(np.percentile(closes, 90)),
        "prob_bullish": float(np.mean(closes > last_close)),
        "ref_close":    last_close,
        "raw_samples":  samples,
        "model_variant":    model_variant,
        "sample_count":     len(samples),
        "temperature":      temperature,
        "context_length":   len(context_candles),
    }
