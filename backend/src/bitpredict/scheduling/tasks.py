"""Celery task definitions for all scheduled and on-demand background work."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from bitpredict.scheduling.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Data ingestion ────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.ingest_klines", bind=True, max_retries=3)
def ingest_klines(self, timeframe: str, symbol: str = "BTCUSDT"):
    """Fetch latest candles for *timeframe* from Binance and persist to DB."""
    try:
        from bitpredict.data.historical import download_and_persist_latest
        result = _run_async(download_and_persist_latest(symbol, timeframe))
        logger.info("Klines updated: %d new candles for %s/%s", result, symbol, timeframe)
        return {"status": "ok", "new_candles": result, "timeframe": timeframe}
    except Exception as exc:
        logger.error("ingest_klines failed: tf=%s error=%s", timeframe, exc)
        raise self.retry(exc=exc, countdown=60)


# ── RSI-2 Strategy tasks ──────────────────────────────────────────────────────

@celery_app.task(name="tasks.ingest_15min_klines", bind=True, max_retries=3)
def ingest_15min_klines(self, symbol: str = "BTCUSDT"):
    """Download latest 15min candles from Binance and append to Parquet."""
    try:
        from pathlib import Path
        import polars as pl
        from bitpredict.data.binance_client import BinanceClient

        data_dir = Path("/app/data/raw")
        out_path = data_dir / f"{symbol.lower()}_15m.parquet"
        interval_delta = timedelta(minutes=15)

        schema = {
            "open_time": pl.Datetime("us", "UTC"),
            "open": pl.Float64, "high": pl.Float64, "low": pl.Float64,
            "close": pl.Float64, "volume": pl.Float64,
            "close_time": pl.Datetime("us", "UTC"),
            "quote_volume": pl.Float64, "trades": pl.Int64,
            "taker_buy_base": pl.Float64, "taker_buy_quote": pl.Float64,
        }

        existing = pl.read_parquet(out_path) if out_path.exists() else pl.DataFrame(schema=schema)
        if not existing.is_empty():
            times = existing["open_time"].to_list()
            last_ts = max(t.replace(tzinfo=UTC) if t.tzinfo is None else t for t in times)
            start = last_ts + interval_delta
        else:
            start = datetime(2018, 1, 1, tzinfo=UTC)

        end = datetime.now(tz=UTC)
        if start >= end:
            return {"status": "ok", "new_candles": 0}

        async def _fetch():
            rows = []
            async with BinanceClient() as client:
                raw = await client.get_klines(symbol=symbol, interval="15m",
                                              start_time=start, end_time=end)
                for r in raw:
                    rows.append({
                        "open_time": datetime.fromtimestamp(r[0] / 1000, tz=UTC),
                        "open": float(r[1]), "high": float(r[2]),
                        "low": float(r[3]), "close": float(r[4]),
                        "volume": float(r[5]),
                        "close_time": datetime.fromtimestamp(r[6] / 1000, tz=UTC),
                        "quote_volume": float(r[7]), "trades": int(r[8]),
                        "taker_buy_base": float(r[9]), "taker_buy_quote": float(r[10]),
                    })
            return rows

        new_rows = _run_async(_fetch())
        if not new_rows:
            return {"status": "ok", "new_candles": 0}

        new_df = pl.DataFrame(new_rows, schema=schema)
        combined = pl.concat([existing, new_df]) if not existing.is_empty() else new_df
        data_dir.mkdir(parents=True, exist_ok=True)
        combined.write_parquet(out_path)
        logger.info("15m klines updated: %d new candles for %s", len(new_rows), symbol)
        return {"status": "ok", "new_candles": len(new_rows)}

    except Exception as exc:
        logger.error("ingest_15min_klines failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="tasks.ingest_funding_rates", bind=True, max_retries=3)
def ingest_funding_rates(self, symbol: str = "BTCUSDT"):
    """Download latest funding rates and append to Parquet."""
    try:
        from bitpredict.data.funding import download_latest_funding
        from pathlib import Path
        n = _run_async(download_latest_funding(symbol=symbol, data_dir=Path("/app/data/raw")))
        logger.info("Funding rates updated: %d new entries for %s", n, symbol)
        return {"status": "ok", "new_entries": n}
    except Exception as exc:
        logger.error("ingest_funding_rates failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(name="tasks.rsi2_inference_tick", bind=True, max_retries=2)
def rsi2_inference_tick(self, symbol: str = "BTCUSDT"):
    """Evaluate RSI-2 strategy on latest bar and persist signal to DB."""
    try:
        from pathlib import Path
        from bitpredict.strategies.rsi2.inference import run_inference
        from bitpredict.db import get_session
        from bitpredict.db_models import Rsi2Signal

        result = run_inference(
            symbol=symbol,
            models_dir=Path("/app/data/models/rsi2"),
            data_dir=Path("/app/data/raw"),
        )

        db = get_session()
        try:
            signal = Rsi2Signal(
                signal_time=result["signal_time"],
                side=result["side"],
                entry_price=result.get("entry_price"),
                stop_price=result.get("stop_price"),
                rsi2_value=result.get("rsi2_value"),
                meta_proba=result.get("meta_proba"),
                params_version=result.get("params_version", "A"),
            )
            db.add(signal)
            db.commit()
        finally:
            db.close()

        logger.info("RSI-2 tick: side=%s entry=%s", result["side"], result.get("entry_price"))
        return {"status": "ok", "side": result["side"]}

    except Exception as exc:
        logger.error("rsi2_inference_tick failed: %s", exc)
        raise self.retry(exc=exc, countdown=30)
