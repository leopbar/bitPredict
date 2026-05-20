"""Return and volatility features derived from close prices."""

from __future__ import annotations

import math

import polars as pl


def add_log_return(df: pl.DataFrame) -> pl.DataFrame:
    """Log return: ln(close[t] / close[t-1])."""
    return df.with_columns(
        (pl.col("close") / pl.col("close").shift(1)).log(base=math.e).alias("log_return")
    )


def add_rolling_volatility(
    df: pl.DataFrame,
    windows: tuple[int, ...] = (24, 168),
) -> pl.DataFrame:
    """Rolling standard deviation of log returns for multiple windows (in hours)."""
    return df.with_columns(
        [
            pl.col("log_return").rolling_std(window_size=w).alias(f"log_return_std_{w}h")
            for w in windows
        ]
    )


def add_realized_volatility(df: pl.DataFrame, window: int = 24) -> pl.DataFrame:
    """Realized volatility: sqrt of sum of squared log returns over a rolling window."""
    return df.with_columns(
        (pl.col("log_return").pow(2).rolling_sum(window_size=window).sqrt()).alias(
            "realized_vol_24h"
        )
    )


def add_rolling_drawdown(df: pl.DataFrame, window: int = 168) -> pl.DataFrame:
    """Rolling drawdown: (close - rolling_peak) / rolling_peak over `window` hours."""
    return df.with_columns(
        pl.col("close").rolling_max(window_size=window).alias("_rolling_peak")
    ).with_columns(
        (
            (pl.col("close") - pl.col("_rolling_peak")) / pl.col("_rolling_peak")
        ).alias(f"drawdown_{window}h")
    ).drop("_rolling_peak")


def add_all_returns(df: pl.DataFrame) -> pl.DataFrame:
    """Apply all return/volatility features."""
    df = add_log_return(df)
    df = add_rolling_volatility(df)
    df = add_realized_volatility(df)
    df = add_rolling_drawdown(df)
    return df
