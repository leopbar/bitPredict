"""Lag features: shifted close and volume values."""

from __future__ import annotations

import polars as pl

_CLOSE_LAGS = (1, 2, 3, 6, 12, 24, 168)
_VOLUME_LAGS = (1, 24)


def add_close_lags(df: pl.DataFrame, lags: tuple[int, ...] = _CLOSE_LAGS) -> pl.DataFrame:
    """Add lagged close price columns."""
    return df.with_columns(
        [pl.col("close").shift(n).alias(f"lag_close_{n}") for n in lags]
    )


def add_volume_lags(df: pl.DataFrame, lags: tuple[int, ...] = _VOLUME_LAGS) -> pl.DataFrame:
    """Add lagged volume columns."""
    return df.with_columns(
        [pl.col("volume").shift(n).alias(f"lag_volume_{n}") for n in lags]
    )


def add_all_lags(df: pl.DataFrame) -> pl.DataFrame:
    """Apply all lag features."""
    df = add_close_lags(df)
    df = add_volume_lags(df)
    return df
