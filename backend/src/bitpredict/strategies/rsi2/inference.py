"""Production inference: evaluate RSI-2 signal on the latest 15min bar."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from bitpredict.strategies.rsi2.config import Rsi2Params
from bitpredict.strategies.rsi2.features import build_features
from bitpredict.strategies.rsi2.persistence import load_model_b, load_params_a, load_winner
from bitpredict.strategies.rsi2.signals import generate_signals

logger = logging.getLogger(__name__)

_MODELS_DIR = Path("/app/data/models/rsi2")
_DATA_DIR = Path("/app/data/raw")

# Minimum bars needed to compute all indicators reliably
_MIN_BARS = 250


def _load_recent_bars(symbol: str = "BTCUSDT", n: int = 500) -> pl.DataFrame:
    """Load the most recent N 15min bars from Parquet."""
    path = _DATA_DIR / f"{symbol.lower()}_15m.parquet"
    if not path.exists():
        raise FileNotFoundError(f"15min data not found at {path}")
    df = pl.read_parquet(path)
    return df.tail(n)


def run_inference(
    symbol: str = "BTCUSDT",
    models_dir: Path = _MODELS_DIR,
    data_dir: Path = _DATA_DIR,
) -> dict:
    """Evaluate the RSI-2 strategy on the most recent bar and return a signal dict.

    Returns a dict with keys:
        side: "long" | "short" | "none"
        entry_price: float | None
        stop_price: float | None
        rsi2_value: float | None
        meta_proba: float | None (only if winner=A+B)
        signal_time: datetime
        params_version: "A" | "A+B"
        reason: human-readable explanation string
    """
    now = datetime.now(tz=UTC)

    try:
        winner_info = load_winner(models_dir)
        winner = winner_info.get("winner", "A")
    except FileNotFoundError:
        winner = "A"

    try:
        params_a = load_params_a(models_dir)
    except FileNotFoundError:
        logger.error("No params_a found — returning none signal")
        return _none_signal(now, "A", "No params_A.json found")

    try:
        df = _load_recent_bars(symbol=symbol, n=500, data_dir=data_dir) if False else _load_recent_bars(symbol=symbol)
    except FileNotFoundError as e:
        return _none_signal(now, winner, str(e))

    if len(df) < _MIN_BARS:
        return _none_signal(now, winner, f"Insufficient data: {len(df)} bars")

    try:
        feature_df = build_features(df)
    except Exception as e:
        return _none_signal(now, winner, f"Feature build failed: {e}")

    # Generate signals on the full window (one-at-a-time rule not enforced in inference)
    signals = generate_signals(feature_df, params_a)

    # We only care about the LAST bar signal
    last_bar_idx = len(feature_df) - 1
    last_signal = None
    for sig in reversed(signals):
        if sig.bar_index == last_bar_idx:
            last_signal = sig
            break

    if last_signal is None:
        last_row = feature_df.row(-1, named=True)
        rsi2 = last_row.get("rsi_2_prev")
        rsi2_str = f"{rsi2:.1f}" if rsi2 is not None else "N/A"
        return _none_signal(
            now, winner,
            f"No signal (RSI={rsi2_str})"
        )

    meta_proba: float | None = None

    if winner == "A+B":
        model_b, threshold = load_model_b(models_dir)
        if model_b is not None:
            from bitpredict.strategies.rsi2.meta_labeling import predict_proba_signal
            df_rows = feature_df.to_dicts()
            last_row_dict = df_rows[last_signal.bar_index] if last_signal.bar_index < len(df_rows) else df_rows[-1]
            meta_proba = predict_proba_signal(model_b, last_signal, last_row_dict)
            if meta_proba < (threshold or 0.55):
                return _none_signal(
                    now, winner,
                    f"{last_signal.side.upper()} signal filtered by meta-model (proba={meta_proba:.3f} < {threshold:.2f})"
                )

    last_row = feature_df.row(-1, named=True)
    rsi2_val = last_row.get("rsi_2_prev")

    return {
        "side": last_signal.side,
        "entry_price": last_signal.entry_price,
        "stop_price": last_signal.stop_price,
        "rsi2_value": rsi2_val,
        "meta_proba": meta_proba,
        "signal_time": now,
        "params_version": winner,
        "reason": (
            f"RSI(2)={rsi2_val:.1f}, body_pct={last_signal.body_pct:.3f}, "
            f"close_pos={last_signal.close_pos:.2f}, stop={last_signal.stop_price:.2f}"
        ),
    }


def _none_signal(ts: datetime, params_version: str, reason: str) -> dict:
    return {
        "side": "none",
        "entry_price": None,
        "stop_price": None,
        "rsi2_value": None,
        "meta_proba": None,
        "signal_time": ts,
        "params_version": params_version,
        "reason": reason,
    }
