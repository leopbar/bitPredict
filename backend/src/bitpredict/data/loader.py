"""Bulk-load Parquet klines files into the PostgreSQL klines hypertable via COPY."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import polars as pl
import psycopg

from bitpredict.config import get_settings

logger = logging.getLogger(__name__)

# Column order must match the COPY statement below.
_KLINE_COLS = (
    "symbol",
    "interval",
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
)

_COPY_STAGING = (
    'COPY klines_staging (symbol, "interval", open_time, open, high, low, close, volume, '
    "close_time, quote_volume, trades, taker_buy_base, taker_buy_quote) FROM STDIN"
)

_INSERT_FROM_STAGING = """
    INSERT INTO klines
        (symbol, "interval", open_time, open, high, low, close, volume,
         close_time, quote_volume, trades, taker_buy_base, taker_buy_quote)
    SELECT
        symbol, "interval", open_time, open, high, low, close, volume,
        close_time, quote_volume, trades, taker_buy_base, taker_buy_quote
    FROM klines_staging
    ON CONFLICT (symbol, "interval", open_time) DO UPDATE SET
        open         = EXCLUDED.open,
        high         = EXCLUDED.high,
        low          = EXCLUDED.low,
        close        = EXCLUDED.close,
        volume       = EXCLUDED.volume,
        close_time   = EXCLUDED.close_time,
        quote_volume = EXCLUDED.quote_volume,
        trades       = EXCLUDED.trades,
        taker_buy_base  = EXCLUDED.taker_buy_base,
        taker_buy_quote = EXCLUDED.taker_buy_quote
"""


def _psycopg_url() -> str:
    """Convert SQLAlchemy URL to a plain psycopg connection string."""
    url = str(get_settings().database_url)
    return url.replace("postgresql+psycopg://", "postgresql://")


def load_parquet_to_db(
    path: Path,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """Bulk-load a Parquet klines file into the klines hypertable.

    Uses a staging temp-table + INSERT ... ON CONFLICT DO NOTHING so the
    command is idempotent (safe to re-run on the same file).

    Args:
        path: Path to the Parquet file.
        symbol: Trading pair identifier stored in the symbol column.
        interval: Candle interval stored in the interval column.
        on_progress: Optional callback(rows_sent, total_rows) called every batch.

    Returns:
        Number of rows in the Parquet file (not the net inserted count, which
        may be lower due to duplicate skipping).
    """
    df = _prepare_dataframe(pl.read_parquet(path), symbol, interval)
    total = len(df)

    with psycopg.connect(_psycopg_url()) as conn:
        conn.execute(
            "CREATE TEMP TABLE klines_staging "
            "(LIKE klines INCLUDING DEFAULTS) ON COMMIT DROP"
        )

        with conn.cursor().copy(_COPY_STAGING) as copy:
            for i, row in enumerate(df.iter_rows(), start=1):
                copy.write_row(row)
                if on_progress:
                    on_progress(i, total)

        result = conn.execute(_INSERT_FROM_STAGING)
        inserted = result.rowcount if result.rowcount >= 0 else total
        conn.commit()

    logger.info("Loaded %d rows from %s (%d inserted after dedup)", total, path.name, inserted)
    return total


def _prepare_dataframe(df: pl.DataFrame, symbol: str, interval: str) -> pl.DataFrame:
    """Add metadata columns and cast to the types psycopg COPY expects."""
    required = {
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet is missing required columns: {missing}")

    float_cols = ["open", "high", "low", "close", "volume",
                  "quote_volume", "taker_buy_base", "taker_buy_quote"]

    df = df.with_columns(
        [pl.col(c).cast(pl.Float64) for c in float_cols]
        + [
            pl.col("trades").cast(pl.Int64),
            pl.col("open_time").cast(pl.Datetime("us", "UTC")),
            pl.col("close_time").cast(pl.Datetime("us", "UTC")),
            pl.lit(symbol).alias("symbol"),
            pl.lit(interval).alias("interval"),
        ]
    )

    return df.select(list(_KLINE_COLS))
