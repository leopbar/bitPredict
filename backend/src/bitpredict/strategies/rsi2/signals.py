"""Pure-rules signal generation for the RSI-2 strategy (Caminho A core)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import polars as pl

from bitpredict.strategies.rsi2.config import Rsi2Params


@dataclass
class SignalRow:
    """A single candidate entry signal at bar t."""

    bar_index: int
    open_time: datetime
    side: str            # "long" | "short"
    entry_price: float   # close[t]
    stop_price: float    # structural low/high or ATR-based
    rsi2_prev: float     # RSI(2)[t-1] that triggered the signal
    body_pct: float
    close_pos: float


def _compute_stop(
    row: dict,
    side: str,
    params: Rsi2Params,
    df: pl.DataFrame,
    idx: int,
) -> float:
    """Compute stop price for a given bar and side."""
    if params.stop_type == "atr":
        atr = row["atr_14"]
        if side == "long":
            return float(row["close"]) - params.atr_k * atr
        else:
            return float(row["close"]) + params.atr_k * atr
    else:
        # structural: rolling min/max over stop_lookback bars ending at t
        lb = params.stop_lookback
        start_idx = max(0, idx - lb)
        window = df[start_idx : idx + 1]  # inclusive of current bar
        if side == "long":
            return float(window["low"].min())
        else:
            return float(window["high"].max())


def generate_signals(
    df: pl.DataFrame,
    params: Rsi2Params,
) -> list[SignalRow]:
    """Return a list of candidate entry signals from the feature DataFrame.

    Signals are generated at bar close (bar t) using RSI from t-1.
    No position management — overlapping signals are kept here; the
    engine handles one-position-at-a-time filtering.
    """
    rows_iter = df.iter_rows(named=True)
    rows_list = list(rows_iter)
    signals: list[SignalRow] = []

    for idx, row in enumerate(rows_list):
        rsi_prev = row.get("rsi_2_prev")
        if rsi_prev is None:
            continue

        open_price = float(row["open"])
        close_price = float(row["close"])
        body_pct_val = float(row["body_pct"])
        close_pos_val = float(row["close_pos"])

        # ── LONG ──────────────────────────────────────────────────────────────
        if (
            rsi_prev < params.rsi_long_threshold
            and abs(body_pct_val) >= params.body_min_pct  # raw body_pct is signed positive for bullish
            and body_pct_val > 0                          # close > open (bullish bar)
            and close_pos_val >= params.close_pos_min
        ):
            stop = _compute_stop(row, "long", params, df, idx)
            if stop < close_price:  # only valid if stop is below entry
                signals.append(
                    SignalRow(
                        bar_index=idx,
                        open_time=row["open_time"],
                        side="long",
                        entry_price=close_price,
                        stop_price=stop,
                        rsi2_prev=rsi_prev,
                        body_pct=body_pct_val,
                        close_pos=close_pos_val,
                    )
                )

        # ── SHORT ─────────────────────────────────────────────────────────────
        elif (
            rsi_prev > params.rsi_short_threshold
            and abs(body_pct_val) >= params.body_min_pct
            and body_pct_val < 0                              # close < open (bearish bar)
            and close_pos_val <= (1.0 - params.close_pos_min)  # symmetric: close in bottom portion
        ):
            stop = _compute_stop(row, "short", params, df, idx)
            if stop > close_price:  # only valid if stop is above entry
                signals.append(
                    SignalRow(
                        bar_index=idx,
                        open_time=row["open_time"],
                        side="short",
                        entry_price=close_price,
                        stop_price=stop,
                        rsi2_prev=rsi_prev,
                        body_pct=body_pct_val,
                        close_pos=close_pos_val,
                    )
                )

    return signals
