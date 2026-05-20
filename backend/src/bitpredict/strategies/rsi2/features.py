"""Feature engineering for the RSI-2 strategy (15min OHLCV → feature DataFrame)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from bitpredict.features.technical import add_atr, add_ema, add_rsi

_DEFAULT_DATA_DIR = Path("/app/data/raw")
_FEATURE_DIR = Path("/app/data/features")

# How many bars to warm up indicators before the first usable row
_WARMUP_BARS = 200


def build_features(
    df: pl.DataFrame,
    max_stop_lookback: int = 80,
) -> pl.DataFrame:
    """Compute all features needed for signal generation and meta-labeling.

    Input DataFrame must have columns: open_time, open, high, low, close, volume.
    Returns a new DataFrame with additional feature columns. Rows with null
    indicator values (warm-up period) are dropped.
    """
    df = add_rsi(df, period=2)
    df = add_atr(df, period=14)
    df = add_ema(df, periods=(50, 200))

    # Entry confirmation features
    df = df.with_columns(
        # body_pct: normalized signed body relative to open price
        ((pl.col("close") - pl.col("open")) / pl.col("open") * 100.0).alias("body_pct"),
        # close_pos: where close sits within the bar's range [0=low, 1=high]
        (
            (pl.col("close") - pl.col("low"))
            / (pl.col("high") - pl.col("low") + 1e-9)
        ).alias("close_pos"),
    )

    # RSI shifted by 1 (previous bar value, as the strategy requires)
    df = df.with_columns(
        pl.col("rsi_2").shift(1).alias("rsi_2_prev"),
    )

    # Rolling min/max for structural stop — use maximum lookback
    df = df.with_columns(
        pl.col("low").rolling_min(window_size=max_stop_lookback).alias(f"roll_low_{max_stop_lookback}"),
        pl.col("high").rolling_max(window_size=max_stop_lookback).alias(f"roll_high_{max_stop_lookback}"),
    )

    # EMA slopes (% change over 5 bars)
    df = df.with_columns(
        (
            (pl.col("ema_50") - pl.col("ema_50").shift(5))
            / pl.col("ema_50").shift(5)
            * 100.0
        ).alias("ema50_slope_5"),
        (
            (pl.col("ema_200") - pl.col("ema_200").shift(5))
            / pl.col("ema_200").shift(5)
            * 100.0
        ).alias("ema200_slope_5"),
    )

    # Price vs EMA (z-score proxy)
    df = df.with_columns(
        ((pl.col("close") - pl.col("ema_50")) / pl.col("ema_50") * 100.0).alias("price_vs_ema50_pct"),
        ((pl.col("close") - pl.col("ema_200")) / pl.col("ema_200") * 100.0).alias("price_vs_ema200_pct"),
    )

    # Volume relative to 20-bar rolling mean
    df = df.with_columns(
        (pl.col("volume") / (pl.col("volume").rolling_mean(window_size=20) + 1e-9)).alias("vol_relative"),
    )

    # Calendar features for meta-labeling context
    df = df.with_columns(
        pl.col("open_time").dt.hour().alias("hour_utc"),
        pl.col("open_time").dt.weekday().alias("weekday"),
    )

    # ATR normalized by price
    df = df.with_columns(
        (pl.col("atr_14") / pl.col("close") * 100.0).alias("atr_pct"),
    )

    # Drop warm-up rows (where any key indicator is null)
    df = df.drop_nulls(subset=["rsi_2_prev", "atr_14", "ema_200", f"roll_low_{max_stop_lookback}"])

    return df


def load_15m_parquet(
    symbol: str = "BTCUSDT",
    data_dir: Path = _DEFAULT_DATA_DIR,
) -> pl.DataFrame:
    """Load 15min OHLCV Parquet. Raises FileNotFoundError if not present."""
    path = data_dir / f"{symbol.lower()}_15m.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"15min data not found at {path}. Run rsi2_ingest_backfill.py first."
        )
    return pl.read_parquet(path)


def load_and_build(
    symbol: str = "BTCUSDT",
    data_dir: Path = _DEFAULT_DATA_DIR,
) -> pl.DataFrame:
    """Load 15min OHLCV and compute all features."""
    df = load_15m_parquet(symbol=symbol, data_dir=data_dir)
    return build_features(df)
