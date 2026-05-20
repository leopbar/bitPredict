"""Calendar and seasonality features extracted from open_time."""

from __future__ import annotations

import math

import polars as pl


def add_calendar(df: pl.DataFrame) -> pl.DataFrame:
    """Add calendar features plus Fourier (sin/cos) cyclic encodings."""
    two_pi = 2.0 * math.pi

    return df.with_columns(
        # Raw calendar components
        pl.col("open_time").dt.hour().alias("hour"),
        pl.col("open_time").dt.weekday().alias("day_of_week"),
        pl.col("open_time").dt.day().alias("day_of_month"),
        pl.col("open_time").dt.month().alias("month"),
        pl.col("open_time").dt.ordinal_day().alias("_day_of_year"),
    ).with_columns(
        # is_weekend: Saturday=5, Sunday=6
        (pl.col("day_of_week") >= 5).alias("is_weekend"),
        # Fourier encoding for hour (period 24)
        (pl.col("hour").cast(pl.Float64) * (two_pi / 24.0)).sin().alias("hour_sin"),
        (pl.col("hour").cast(pl.Float64) * (two_pi / 24.0)).cos().alias("hour_cos"),
        # Fourier encoding for day of year (period 365)
        (pl.col("_day_of_year").cast(pl.Float64) * (two_pi / 365.0)).sin().alias("doy_sin"),
        (pl.col("_day_of_year").cast(pl.Float64) * (two_pi / 365.0)).cos().alias("doy_cos"),
    ).drop("_day_of_year")
