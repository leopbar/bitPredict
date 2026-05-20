"""Unit tests for RSI-2 signal generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from bitpredict.strategies.rsi2.config import Rsi2Params
from bitpredict.strategies.rsi2.signals import generate_signals


def _make_df(n: int = 50, seed: int = 0) -> pl.DataFrame:
    """Build a minimal synthetic OHLCV + feature DataFrame suitable for signal generation."""
    import random
    rng = random.Random(seed)

    schema = {
        "open_time": pl.Datetime("us", "UTC"),
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "volume": pl.Float64,
        "rsi_2": pl.Float64,
        "rsi_2_prev": pl.Float64,
        "atr_14": pl.Float64,
        "body_pct": pl.Float64,
        "close_pos": pl.Float64,
    }

    rows = []
    price = 50000.0
    for i in range(n):
        open_p = price
        close_p = open_p * (1 + rng.uniform(-0.005, 0.005))
        high_p = max(open_p, close_p) * (1 + rng.uniform(0, 0.002))
        low_p = min(open_p, close_p) * (1 - rng.uniform(0, 0.002))
        body_pct = (close_p - open_p) / open_p * 100.0
        close_pos = (close_p - low_p) / (high_p - low_p + 1e-9)
        rows.append({
            "open_time": datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * i),
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": 100.0,
            "rsi_2": rng.uniform(5, 95),
            "rsi_2_prev": rng.uniform(5, 95),
            "atr_14": price * 0.002,
            "body_pct": body_pct,
            "close_pos": close_pos,
        })
        price = close_p

    return pl.DataFrame(rows, schema=schema)


def _inject_long_signal(df: pl.DataFrame, idx: int) -> pl.DataFrame:
    """Force a valid long signal at row *idx*."""
    rows = df.to_dicts()
    row = rows[idx]
    open_p = row["open"]
    close_p = open_p * 1.003  # bullish, +0.3%
    high_p = close_p * 1.001
    low_p = open_p * 0.999
    rows[idx] = {
        **row,
        "close": close_p,
        "high": high_p,
        "low": low_p,
        "rsi_2_prev": 5.0,  # oversold
        "body_pct": (close_p - open_p) / open_p * 100.0,
        "close_pos": (close_p - low_p) / (high_p - low_p + 1e-9),
        "atr_14": close_p * 0.002,
    }
    return pl.from_dicts(rows)


def _inject_short_signal(df: pl.DataFrame, idx: int) -> pl.DataFrame:
    """Force a valid short signal at row *idx*."""
    rows = df.to_dicts()
    row = rows[idx]
    open_p = row["open"]
    close_p = open_p * 0.997  # bearish, -0.3%
    high_p = open_p * 1.001
    low_p = close_p * 0.999
    rows[idx] = {
        **row,
        "close": close_p,
        "high": high_p,
        "low": low_p,
        "rsi_2_prev": 95.0,  # overbought
        "body_pct": (close_p - open_p) / open_p * 100.0,
        "close_pos": (close_p - low_p) / (high_p - low_p + 1e-9),
        "atr_14": close_p * 0.002,
    }
    return pl.from_dicts(rows)


@pytest.mark.unit
def test_no_signals_with_neutral_rsi():
    df = _make_df(50)
    # Override all rsi_2_prev to neutral zone so no signals fire
    df = df.with_columns(pl.lit(50.0).alias("rsi_2_prev"))
    params = Rsi2Params()
    signals = generate_signals(df, params)
    assert signals == []


@pytest.mark.unit
def test_long_signal_generated():
    df = _make_df(50)
    df = df.with_columns(pl.lit(50.0).alias("rsi_2_prev"))  # neutral baseline
    df = _inject_long_signal(df, idx=20)

    params = Rsi2Params(body_min_pct=0.1, close_pos_min=0.5, stop_type="atr", atr_k=2.0)
    signals = generate_signals(df, params)

    long_signals = [s for s in signals if s.side == "long"]
    assert len(long_signals) >= 1
    sig = long_signals[0]
    assert sig.bar_index == 20
    assert sig.entry_price > 0
    assert sig.stop_price < sig.entry_price  # stop below entry for long


@pytest.mark.unit
def test_short_signal_generated():
    df = _make_df(50)
    df = df.with_columns(pl.lit(50.0).alias("rsi_2_prev"))
    df = _inject_short_signal(df, idx=25)

    params = Rsi2Params(body_min_pct=0.1, close_pos_min=0.5, stop_type="atr", atr_k=2.0)
    signals = generate_signals(df, params)

    short_signals = [s for s in signals if s.side == "short"]
    assert len(short_signals) >= 1
    sig = short_signals[0]
    assert sig.bar_index == 25
    assert sig.stop_price > sig.entry_price  # stop above entry for short


@pytest.mark.unit
def test_signal_rejected_when_body_too_small():
    df = _make_df(50)
    df = df.with_columns(pl.lit(50.0).alias("rsi_2_prev"))
    # Inject a long signal but with tiny body (< threshold)
    df = _inject_long_signal(df, idx=20)

    params = Rsi2Params(body_min_pct=1.0, close_pos_min=0.0, stop_type="atr", atr_k=2.0)
    signals = generate_signals(df, params)
    long_signals = [s for s in signals if s.bar_index == 20 and s.side == "long"]
    assert len(long_signals) == 0  # body_pct ~0.3% < 1.0%


@pytest.mark.unit
def test_structural_stop_is_below_entry_for_long():
    df = _make_df(50)
    df = df.with_columns(pl.lit(50.0).alias("rsi_2_prev"))
    df = _inject_long_signal(df, idx=30)

    params = Rsi2Params(body_min_pct=0.0, close_pos_min=0.0, stop_type="structural", stop_lookback=10)
    signals = generate_signals(df, params)
    long_signals = [s for s in signals if s.side == "long" and s.bar_index == 30]
    if long_signals:
        assert long_signals[0].stop_price < long_signals[0].entry_price


@pytest.mark.unit
def test_symmetric_long_short():
    """Long and short signals should be symmetric in structure."""
    df = _make_df(60)
    df = df.with_columns(pl.lit(50.0).alias("rsi_2_prev"))
    df = _inject_long_signal(df, idx=10)
    df = _inject_short_signal(df, idx=20)

    params = Rsi2Params(body_min_pct=0.1, close_pos_min=0.5, stop_type="atr", atr_k=2.0)
    signals = generate_signals(df, params)

    sides = {s.bar_index: s.side for s in signals}
    assert 10 in sides and sides[10] == "long"
    assert 20 in sides and sides[20] == "short"
