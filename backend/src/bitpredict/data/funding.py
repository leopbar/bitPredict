"""Fetch and persist Binance perpetual funding rate history."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import polars as pl
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = Path("/app/data/raw")
_FAPI_BASE = "https://fapi.binance.com"
_MAX_PER_REQUEST = 1000

_SCHEMA = {
    "symbol": pl.Utf8,
    "funding_time": pl.Datetime("us", "UTC"),
    "funding_rate": pl.Float64,
    "mark_price": pl.Float64,
}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, httpx.TimeoutException | httpx.NetworkError)


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(6),
    reraise=True,
)
async def _fetch_funding_page(
    client: httpx.AsyncClient,
    symbol: str,
    start_time: int | None = None,
    end_time: int | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"symbol": symbol.upper(), "limit": _MAX_PER_REQUEST}
    if start_time is not None:
        params["startTime"] = start_time
    if end_time is not None:
        params["endTime"] = end_time

    resp = await client.get("/fapi/v1/fundingRate", params=params)
    resp.raise_for_status()
    return resp.json()


def _rows_to_frame(rows: list[dict[str, Any]], symbol: str) -> pl.DataFrame:
    data = [
        {
            "symbol": symbol.upper(),
            "funding_time": datetime.fromtimestamp(r["fundingTime"] / 1000, tz=UTC),
            "funding_rate": float(r["fundingRate"]),
            "mark_price": float(r.get("markPrice", 0.0)),
        }
        for r in rows
    ]
    return pl.DataFrame(data, schema=_SCHEMA)


async def download_funding_history(
    symbol: str = "BTCUSDT",
    start: datetime | None = None,
    end: datetime | None = None,
    data_dir: Path = _DEFAULT_DATA_DIR,
) -> pl.DataFrame:
    """Download all funding rate entries and write to Parquet.

    Funding rates are emitted every 8 hours on Binance perpetuals.
    Historical data from 2019-09 onward for BTCUSDT.
    """
    if start is None:
        start = datetime(2019, 9, 1, tzinfo=UTC)
    if end is None:
        end = datetime.now(tz=UTC)

    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / f"{symbol.lower()}_funding.parquet"

    frames: list[pl.DataFrame] = []
    current_start = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    async with httpx.AsyncClient(base_url=_FAPI_BASE, timeout=30.0) as client:
        while current_start < end_ms:
            rows = await _fetch_funding_page(client, symbol, start_time=current_start, end_time=end_ms)
            if not rows:
                break

            frame = _rows_to_frame(rows, symbol)
            frames.append(frame)

            last_ts = rows[-1]["fundingTime"]
            current_start = last_ts + 1  # next ms to avoid overlap

            if len(rows) < _MAX_PER_REQUEST:
                break

            await asyncio.sleep(0.1)  # be polite to Binance futures API

    if not frames:
        return pl.DataFrame(schema=_SCHEMA)

    result = pl.concat(frames)

    # deduplicate by funding_time
    timestamps = result["funding_time"].to_list()
    epoch_us = [int(ts.timestamp() * 1_000_000) for ts in timestamps]
    seen: set[int] = set()
    keep: list[int] = []
    for idx in sorted(range(len(epoch_us)), key=lambda i: epoch_us[i]):
        if epoch_us[idx] not in seen:
            seen.add(epoch_us[idx])
            keep.append(idx)
    result = result[keep]

    result.write_parquet(out_path)
    logger.info("Funding history written: %d rows → %s", len(result), out_path)
    return result


async def download_latest_funding(
    symbol: str = "BTCUSDT",
    data_dir: Path = _DEFAULT_DATA_DIR,
) -> int:
    """Download funding rates since last stored and append to Parquet. Returns new rows count."""
    out_path = data_dir / f"{symbol.lower()}_funding.parquet"

    if out_path.exists():
        existing = pl.read_parquet(out_path)
        timestamps = existing["funding_time"].to_list()
        if timestamps:
            last_ts = max(timestamps)
            start = last_ts + timedelta(hours=8)
        else:
            start = datetime(2019, 9, 1, tzinfo=UTC)
    else:
        start = datetime(2019, 9, 1, tzinfo=UTC)
        existing = pl.DataFrame(schema=_SCHEMA)

    end = datetime.now(tz=UTC)
    if start >= end:
        return 0

    new_frame = await download_funding_history(symbol=symbol, start=start, end=end, data_dir=Path("/tmp"))
    if new_frame.is_empty():
        return 0

    combined = pl.concat([existing, new_frame])

    # deduplicate
    timestamps_all = combined["funding_time"].to_list()
    epoch_us = [int(ts.timestamp() * 1_000_000) for ts in timestamps_all]
    seen: set[int] = set()
    keep: list[int] = []
    for idx in sorted(range(len(epoch_us)), key=lambda i: epoch_us[i]):
        if epoch_us[idx] not in seen:
            seen.add(epoch_us[idx])
            keep.append(idx)
    combined = combined[keep]

    data_dir.mkdir(parents=True, exist_ok=True)
    combined.write_parquet(out_path)
    return len(new_frame)


def load_funding(
    symbol: str = "BTCUSDT",
    data_dir: Path = _DEFAULT_DATA_DIR,
) -> pl.DataFrame:
    """Load funding rate Parquet; returns empty DataFrame if missing."""
    path = data_dir / f"{symbol.lower()}_funding.parquet"
    if not path.exists():
        return pl.DataFrame(schema=_SCHEMA)
    return pl.read_parquet(path)


def get_funding_rate_at(
    funding_df: pl.DataFrame,
    timestamp: datetime,
) -> float:
    """Return the most recent funding rate at or before *timestamp*. Returns 0.0 if unknown."""
    if funding_df.is_empty():
        return 0.0

    ts_list = funding_df["funding_time"].to_list()
    rate_list = funding_df["funding_rate"].to_list()

    best_rate = 0.0
    best_ts: datetime | None = None
    for ts, rate in zip(ts_list, rate_list):
        ts_aware = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
        if ts_aware <= timestamp:
            if best_ts is None or ts_aware > best_ts:
                best_ts = ts_aware
                best_rate = rate

    return best_rate
