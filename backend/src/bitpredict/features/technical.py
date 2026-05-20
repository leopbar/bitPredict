"""Classical technical indicators computed with Polars rolling expressions."""

from __future__ import annotations

import math

import polars as pl


def add_rsi(df: pl.DataFrame, period: int = 14) -> pl.DataFrame:
    """Relative Strength Index using Wilder's smoothing (EMA, com=period-1)."""
    delta = pl.col("close").diff(1)
    gain = pl.when(delta > 0).then(delta).otherwise(pl.lit(0.0))
    loss = pl.when(delta < 0).then(-delta).otherwise(pl.lit(0.0))

    return df.with_columns(
        gain.ewm_mean(com=period - 1, ignore_nulls=True).alias("_avg_gain"),
        loss.ewm_mean(com=period - 1, ignore_nulls=True).alias("_avg_loss"),
    ).with_columns(
        (
            pl.lit(100.0)
            - pl.lit(100.0) / (pl.lit(1.0) + pl.col("_avg_gain") / pl.col("_avg_loss"))
        ).alias(f"rsi_{period}")
    ).drop(["_avg_gain", "_avg_loss"])


def add_macd(
    df: pl.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pl.DataFrame:
    """MACD line, signal line, and histogram."""
    return df.with_columns(
        pl.col("close").ewm_mean(span=fast).alias("_ema_fast"),
        pl.col("close").ewm_mean(span=slow).alias("_ema_slow"),
    ).with_columns(
        (pl.col("_ema_fast") - pl.col("_ema_slow")).alias("macd")
    ).with_columns(
        pl.col("macd").ewm_mean(span=signal).alias("macd_signal")
    ).with_columns(
        (pl.col("macd") - pl.col("macd_signal")).alias("macd_hist")
    ).drop(["_ema_fast", "_ema_slow"])


def add_sma(df: pl.DataFrame, periods: tuple[int, ...] = (7, 21, 50, 200)) -> pl.DataFrame:
    """Simple Moving Averages for multiple periods."""
    return df.with_columns(
        [pl.col("close").rolling_mean(window_size=p).alias(f"sma_{p}") for p in periods]
    )


def add_ema(df: pl.DataFrame, periods: tuple[int, ...] = (12, 26)) -> pl.DataFrame:
    """Exponential Moving Averages for multiple periods."""
    return df.with_columns(
        [pl.col("close").ewm_mean(span=p).alias(f"ema_{p}") for p in periods]
    )


def add_bollinger_bands(df: pl.DataFrame, period: int = 20, std_dev: float = 2.0) -> pl.DataFrame:
    """Bollinger Bands: middle, upper, lower, width, and %B."""
    return df.with_columns(
        pl.col("close").rolling_mean(window_size=period).alias("bb_middle"),
        pl.col("close").rolling_std(window_size=period).alias("_bb_std"),
    ).with_columns(
        (pl.col("bb_middle") + std_dev * pl.col("_bb_std")).alias("bb_upper"),
        (pl.col("bb_middle") - std_dev * pl.col("_bb_std")).alias("bb_lower"),
    ).with_columns(
        (
            (pl.col("bb_upper") - pl.col("bb_lower")) / pl.col("bb_middle")
        ).alias("bb_width"),
        (
            (pl.col("close") - pl.col("bb_lower"))
            / (pl.col("bb_upper") - pl.col("bb_lower"))
        ).alias("bb_pct_b"),
    ).drop("_bb_std")


def add_atr(df: pl.DataFrame, period: int = 14) -> pl.DataFrame:
    """Average True Range — max of (H-L, |H-C_prev|, |L-C_prev|)."""
    prev_close = pl.col("close").shift(1)
    true_range = pl.max_horizontal(
        pl.col("high") - pl.col("low"),
        (pl.col("high") - prev_close).abs(),
        (pl.col("low") - prev_close).abs(),
    )
    return df.with_columns(
        true_range.rolling_mean(window_size=period).alias(f"atr_{period}")
    )


def add_obv(df: pl.DataFrame) -> pl.DataFrame:
    """On-Balance Volume — cumulative sum of signed volume."""
    direction = (
        pl.when(pl.col("close") > pl.col("close").shift(1))
        .then(pl.lit(1.0))
        .when(pl.col("close") < pl.col("close").shift(1))
        .then(pl.lit(-1.0))
        .otherwise(pl.lit(0.0))
    )
    return df.with_columns(
        (direction * pl.col("volume")).cum_sum().alias("obv")
    )


def add_all_technical(df: pl.DataFrame) -> pl.DataFrame:
    """Apply all technical indicators in one pass."""
    df = add_rsi(df)
    df = add_macd(df)
    df = add_sma(df)
    df = add_ema(df)
    df = add_bollinger_bands(df)
    df = add_atr(df)
    df = add_obv(df)
    return df
