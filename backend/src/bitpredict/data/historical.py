"""Download historical OHLCV klines from Binance and persist to Parquet."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

import polars as pl

from bitpredict.data.binance_client import BinanceClient
from bitpredict.data.gaps import detect_gaps, gap_summary
from bitpredict.data.schemas import Kline

_DEFAULT_DATA_DIR = Path("/app/data/raw")

_INTERVAL_DELTAS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
    "6h": timedelta(hours=6),
    "8h": timedelta(hours=8),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "1w": timedelta(weeks=1),
}


def _interval_delta(interval: str) -> timedelta:
    if interval not in _INTERVAL_DELTAS:
        raise ValueError(f"Unsupported interval: {interval!r}")
    return _INTERVAL_DELTAS[interval]


_SCHEMA = {
    "open_time": pl.Datetime("us", "UTC"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
    "close_time": pl.Datetime("us", "UTC"),
    "quote_volume": pl.Float64,
    "trades": pl.Int64,
    "taker_buy_base": pl.Float64,
    "taker_buy_quote": pl.Float64,
}


def _klines_to_frame(klines: list[Kline]) -> pl.DataFrame:
    rows = [
        {
            "open_time": k.open_time,
            "open": float(k.open),
            "high": float(k.high),
            "low": float(k.low),
            "close": float(k.close),
            "volume": float(k.volume),
            "close_time": k.close_time,
            "quote_volume": float(k.quote_volume),
            "trades": k.trades,
            "taker_buy_base": float(k.taker_buy_base),
            "taker_buy_quote": float(k.taker_buy_quote),
        }
        for k in klines
    ]
    return pl.DataFrame(rows, schema=_SCHEMA)


async def download_historical(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    start: datetime | None = None,
    end: datetime | None = None,
    data_dir: Path = _DEFAULT_DATA_DIR,
    on_page: Callable[[int, int], None] | None = None,
) -> pl.DataFrame:
    """Download all klines between *start* and *end* and write to Parquet.

    Args:
        symbol: Binance trading pair (e.g. "BTCUSDT").
        interval: Candle interval (e.g. "1h").
        start: Inclusive start time (UTC). Defaults to 2017-08-17.
        end: Exclusive end time (UTC). Defaults to now.
        data_dir: Directory where the Parquet file will be written.
        on_page: Optional callback invoked after each page with (page_index, total_rows_so_far).

    Returns:
        Complete DataFrame with all downloaded candles.
    """
    if start is None:
        start = datetime(2017, 8, 17, tzinfo=UTC)
    if end is None:
        end = datetime.now(tz=UTC)

    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / f"{symbol.lower()}_{interval}.parquet"

    frames: list[pl.DataFrame] = []
    current_start = start
    page = 0

    async with BinanceClient() as client:
        while current_start < end:
            raw = await client.get_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end,
            )
            if not raw:
                break

            klines = [Kline.from_raw(row) for row in raw]
            frame = _klines_to_frame(klines)
            frames.append(frame)
            page += 1

            total_rows = sum(len(f) for f in frames)
            if on_page:
                on_page(page, total_rows)

            last_open_time = klines[-1].open_time
            next_start = (
                last_open_time.replace(tzinfo=UTC)
                if last_open_time.tzinfo is None
                else last_open_time
            )
            next_start = next_start + _interval_delta(interval)

            if next_start >= end or len(raw) < 1000:
                break
            current_start = next_start

    if not frames:
        return pl.DataFrame(schema=_SCHEMA)

    result = pl.concat(frames)

    # Sort and deduplicate using Python-level sort to avoid the Polars lazy-engine
    # sort crash on Datetime("us","UTC") columns (Windows Polars 1.12 known issue).
    timestamps = result["open_time"].to_list()
    epoch_us = [int(ts.timestamp() * 1_000_000) for ts in timestamps]
    seen: set[int] = set()
    keep: list[int] = []
    for idx in sorted(range(len(epoch_us)), key=lambda i: epoch_us[i]):
        if epoch_us[idx] not in seen:
            seen.add(epoch_us[idx])
            keep.append(idx)
    result = result[keep]

    result.write_parquet(out_path)
    return result


async def download_and_persist_latest(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
) -> int:
    """Download candles since the last DB entry and persist them directly.

    Used by the hourly Celery task to keep the klines table current.
    Returns the number of new rows written to the DB.
    """
    from sqlalchemy import select, func
    from bitpredict.db import get_session
    from bitpredict.db_models import Kline as KlineModel
    from bitpredict.data.loader import load_parquet_to_db

    db = get_session()
    try:
        last_open_time = db.execute(
            select(func.max(KlineModel.open_time)).where(
                KlineModel.symbol == symbol,
                KlineModel.interval == interval,
            )
        ).scalar_one_or_none()
    finally:
        db.close()

    iv_delta = _interval_delta(interval)
    # Start one candle back so the previously saved candle is always re-fetched
    # and upserted with its final Binance close (fixes stale preliminary closes).
    start = (
        (last_open_time - iv_delta).replace(tzinfo=UTC)
        if last_open_time and last_open_time.tzinfo is None
        else (last_open_time - iv_delta)
        if last_open_time
        else datetime(2017, 8, 17, tzinfo=UTC)
    )
    end = datetime.now(tz=UTC)

    if start >= end:
        return 0

    tmp_dir = Path("/tmp/bitpredict_latest")
    df = await download_historical(symbol=symbol, interval=interval, start=start, end=end, data_dir=tmp_dir)
    if df.is_empty():
        return 0

    # Drop the currently forming candle — its close_time is still in the future,
    # meaning it hasn't closed yet and its OHLCV data is preliminary.
    now_ts = datetime.now(tz=UTC)
    df = df.filter(pl.col("close_time") < pl.lit(now_ts).cast(pl.Datetime("us", "UTC")))
    if df.is_empty():
        return 0

    out_path = tmp_dir / f"{symbol.lower()}_{interval}.parquet"
    return load_parquet_to_db(out_path, symbol=symbol, interval=interval)


def load_parquet(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    data_dir: Path = _DEFAULT_DATA_DIR,
) -> pl.DataFrame:
    """Load previously downloaded Parquet file."""
    path = data_dir / f"{symbol.lower()}_{interval}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No data file found at {path}. Run 'bitpredict download' first.")
    return pl.read_parquet(path)


def parquet_summary(
    df: pl.DataFrame,
    symbol: str,
    interval: str,
    out_path: Path,
) -> dict[str, object]:
    """Build a summary dict for display after a download."""
    gaps = detect_gaps(df, interval)
    summary = gap_summary(gaps, interval)
    return {
        "symbol": symbol,
        "interval": interval,
        "rows": len(df),
        "start": df["open_time"].min(),
        "end": df["open_time"].max(),
        "gap_count": summary["gap_count"],
        "missing_candles": summary["missing_candles"],
        "file_size_mb": round(out_path.stat().st_size / 1024 / 1024, 2) if out_path.exists() else 0,
    }
