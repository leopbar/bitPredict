"""Market data endpoints: OHLCV klines for dashboard charts."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from bitpredict.api.auth import require_api_key
from bitpredict.api.dependencies import get_db
from bitpredict.api.schemas import KlineRangeResponse, KlineResponse
from bitpredict.db_models import Kline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/klines", tags=["Market Data"])

_CONTEXT_MIN = 512  # candles Kronos needs as context


class EnsureKlinesResponse(BaseModel):
    status: str   # "ok" | "ingesting"
    count: int
    is_fresh: bool


def _klines_status(db: Session, timeframe: str) -> tuple[int, bool]:
    """Return (count, is_fresh) for the given timeframe."""
    from bitpredict.kronos.timeframes import Timeframe
    tf = Timeframe(timeframe)
    interval = tf.to_binance_interval()
    iv_delta = tf.to_timedelta()

    count = db.execute(
        select(func.count()).select_from(Kline)
        .where(Kline.symbol == "BTCUSDT", Kline.interval == interval)
    ).scalar_one()

    last_open_time = db.execute(
        select(func.max(Kline.open_time))
        .where(Kline.symbol == "BTCUSDT", Kline.interval == interval)
    ).scalar_one_or_none()

    if last_open_time is None:
        return count, False

    last_dt = last_open_time if last_open_time.tzinfo else last_open_time.replace(tzinfo=UTC)
    is_fresh = (datetime.now(tz=UTC) - last_dt) <= iv_delta * 2
    return count, is_fresh

# In-memory ticker cache. Binance rate-limits public endpoints — without a
# small cache, 100 concurrent dashboard tabs would each fire a request.
_TICKER_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_TICKER_TTL_SECONDS = 4.0
_TICKER_LOCK = asyncio.Lock()


@router.get(
    "",
    response_model=KlineRangeResponse,
    summary="Fetch OHLCV candles for a date range",
    dependencies=[Depends(require_api_key)],
)
def get_klines(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="1h"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=168, ge=1, le=10000),
    db: Session = Depends(get_db),
) -> KlineRangeResponse:
    if end is None:
        end = datetime.now(tz=timezone.utc)
    if start is None:
        try:
            from bitpredict.kronos.timeframes import Timeframe
            start = end - Timeframe(interval).to_timedelta() * limit
        except ValueError:
            start = end - timedelta(hours=limit)

    stmt = (
        select(Kline)
        .where(
            Kline.symbol == symbol,
            Kline.interval == interval,
            Kline.open_time >= start,
            Kline.open_time <= end,
        )
        .order_by(Kline.open_time.asc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()

    items = [
        KlineResponse(
            open_time=r.open_time,
            open=float(r.open),
            high=float(r.high),
            low=float(r.low),
            close=float(r.close),
            volume=float(r.volume),
            trades=r.trades,
        )
        for r in rows
    ]
    return KlineRangeResponse(symbol=symbol, interval=interval, count=len(items), items=items)


@router.get(
    "/daily",
    response_model=KlineRangeResponse,
    summary="Fetch daily aggregated OHLCV candles (1h data grouped by day)",
    dependencies=[Depends(require_api_key)],
)
def get_daily_klines(
    symbol: str = Query(default="BTCUSDT"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=365, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> KlineRangeResponse:
    if end is None:
        end = datetime.now(tz=timezone.utc)
    if start is None:
        start = end - timedelta(days=limit)

    # TimescaleDB time_bucket aggregates hourly rows into daily OHLCV
    sql = text("""
        SELECT
            time_bucket('1 day', open_time) AS day,
            FIRST(open, open_time)           AS open,
            MAX(high)                        AS high,
            MIN(low)                         AS low,
            LAST(close, open_time)           AS close,
            SUM(volume)                      AS volume,
            SUM(trades)                      AS trades
        FROM klines
        WHERE symbol = :symbol
          AND interval = '1h'
          AND open_time >= :start
          AND open_time <= :end
        GROUP BY day
        ORDER BY day ASC
        LIMIT :limit
    """)
    rows = db.execute(sql, {"symbol": symbol, "start": start, "end": end, "limit": limit}).fetchall()

    items = [
        KlineResponse(
            open_time=r.day,
            open=float(r.open),
            high=float(r.high),
            low=float(r.low),
            close=float(r.close),
            volume=float(r.volume),
            trades=int(r.trades),
        )
        for r in rows
    ]
    return KlineRangeResponse(symbol=symbol, interval="1d", count=len(items), items=items)


@router.get(
    "/ticker",
    summary="Live spot ticker for a symbol (proxied from Binance, 4s server-side cache)",
    dependencies=[Depends(require_api_key)],
)
async def get_ticker(symbol: str = Query(default="BTCUSDT")) -> dict[str, Any]:
    """Return the current live price + 24h stats. Use for real-time dashboard polling.

    Server-side cache (~4s) prevents Binance rate-limit issues even with many
    concurrent clients polling every 5s.
    """
    key = symbol.upper()
    now = time.monotonic()

    cached = _TICKER_CACHE.get(key)
    if cached and (now - cached[0]) < _TICKER_TTL_SECONDS:
        return cached[1]

    async with _TICKER_LOCK:
        # Double-check after acquiring the lock — another request may have
        # populated the cache while we waited.
        cached = _TICKER_CACHE.get(key)
        if cached and (time.monotonic() - cached[0]) < _TICKER_TTL_SECONDS:
            return cached[1]

        try:
            from bitpredict.data.binance_client import BinanceClient
            async with BinanceClient() as client:
                raw = await client.get_ticker_24h(symbol=key)
        except Exception as exc:
            logger.error("get_ticker failed for %s: %s", key, exc)
            # Fall back to cached data if available, even if stale
            if cached:
                return cached[1]
            raise HTTPException(status_code=502, detail="Could not fetch ticker from Binance")

        payload = {
            "symbol": key,
            "price": float(raw["lastPrice"]),
            "price_change_24h": float(raw["priceChange"]),
            "price_change_pct_24h": float(raw["priceChangePercent"]),
            "high_24h": float(raw["highPrice"]),
            "low_24h": float(raw["lowPrice"]),
            "volume_24h": float(raw["volume"]),
            "quote_volume_24h": float(raw["quoteVolume"]),
            "trades_24h": int(raw["count"]),
            "timestamp": int(raw["closeTime"]),
        }
        _TICKER_CACHE[key] = (time.monotonic(), payload)
        return payload


@router.get(
    "/info",
    summary="Coverage statistics for the klines table (total rows, date range, gaps)",
    dependencies=[Depends(require_api_key)],
)
def get_klines_info(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="1h"),
    db: Session = Depends(get_db),
) -> dict:
    sql = text("""
        SELECT
            COUNT(*)                          AS total_rows,
            MIN(open_time)                    AS first_ts,
            MAX(open_time)                    AS last_ts,
            EXTRACT(EPOCH FROM (MAX(open_time) - MIN(open_time))) / 3600 AS span_hours
        FROM klines
        WHERE symbol = :symbol AND interval = :interval
    """)
    row = db.execute(sql, {"symbol": symbol, "interval": interval}).fetchone()
    total = int(row.total_rows or 0)
    first_ts = row.first_ts
    last_ts = row.last_ts
    span_hours = int(row.span_hours or 0)
    expected = span_hours + 1 if total > 0 else 0
    missing = max(0, expected - total)

    return {
        "symbol": symbol,
        "interval": interval,
        "total_rows": total,
        "first_open_time": first_ts.isoformat() if first_ts else None,
        "last_open_time": last_ts.isoformat() if last_ts else None,
        "expected_rows": expected,
        "missing_rows": missing,
    }


@router.post(
    "/sync",
    summary="Trigger a background sync of the latest candles from Binance",
    dependencies=[Depends(require_api_key)],
)
def sync_klines(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="1h"),
) -> dict:
    try:
        from bitpredict.scheduling.tasks import download_latest_klines
        task = download_latest_klines.delay(symbol=symbol, interval=interval)
        return {"status": "queued", "task_id": task.id}
    except Exception as exc:
        logger.error("sync_klines failed to enqueue: %s", exc)
        raise HTTPException(status_code=503, detail="Could not enqueue sync task")


@router.post(
    "/backfill",
    summary="Download a date range from Binance and persist to DB (idempotent)",
    dependencies=[Depends(require_api_key)],
)
def backfill_klines(
    background: BackgroundTasks,
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="1h"),
    start: datetime = Query(..., description="Inclusive start (UTC)"),
    end: datetime | None = Query(default=None, description="Exclusive end (UTC); defaults to now"),
) -> dict:
    end_dt = end or datetime.now(tz=timezone.utc)
    if start >= end_dt:
        raise HTTPException(status_code=400, detail="start must be before end")

    def _run():
        import asyncio
        from pathlib import Path
        from bitpredict.data.historical import download_historical
        from bitpredict.data.loader import load_parquet_to_db

        tmp_dir = Path("/tmp/bitpredict_backfill")
        try:
            asyncio.run(
                download_historical(
                    symbol=symbol,
                    interval=interval,
                    start=start,
                    end=end_dt,
                    data_dir=tmp_dir,
                )
            )
            out_path = tmp_dir / f"{symbol.lower()}_{interval}.parquet"
            if out_path.exists():
                load_parquet_to_db(out_path, symbol=symbol, interval=interval)
        except Exception as exc:
            logger.error("backfill_klines failed: %s", exc)

    background.add_task(_run)
    return {
        "status": "queued",
        "symbol": symbol,
        "interval": interval,
        "start": start.isoformat(),
        "end": end_dt.isoformat(),
    }


def _validate_tf(timeframe: str) -> None:
    from bitpredict.kronos.timeframes import Timeframe
    try:
        Timeframe(timeframe)
    except ValueError:
        valid = [t.value for t in Timeframe]
        raise HTTPException(422, f"Invalid timeframe '{timeframe}'. Valid: {valid}")


@router.get(
    "/ensure/{timeframe}",
    response_model=EnsureKlinesResponse,
    summary="Check if klines are available and fresh for a timeframe",
    dependencies=[Depends(require_api_key)],
)
def check_klines_status(
    timeframe: str,
    db: Session = Depends(get_db),
) -> EnsureKlinesResponse:
    _validate_tf(timeframe)
    count, is_fresh = _klines_status(db, timeframe)
    status = "ok" if count >= _CONTEXT_MIN and is_fresh else "ingesting"
    return EnsureKlinesResponse(status=status, count=count, is_fresh=is_fresh)


@router.post(
    "/ensure/{timeframe}",
    response_model=EnsureKlinesResponse,
    summary="Ensure klines are available and fresh; triggers ingest if needed",
    dependencies=[Depends(require_api_key)],
)
def ensure_klines(
    timeframe: str,
    db: Session = Depends(get_db),
) -> EnsureKlinesResponse:
    _validate_tf(timeframe)
    count, is_fresh = _klines_status(db, timeframe)

    if count >= _CONTEXT_MIN and is_fresh:
        return EnsureKlinesResponse(status="ok", count=count, is_fresh=True)

    from bitpredict.scheduling.tasks import ingest_klines as ingest_task
    ingest_task.apply_async(args=[timeframe])
    return EnsureKlinesResponse(status="ingesting", count=count, is_fresh=is_fresh)
