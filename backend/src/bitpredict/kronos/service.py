"""Kronos prediction service — orchestrates context loading, inference and DB persistence."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import redis as _redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from bitpredict.config import get_settings
from bitpredict.db import get_session
from bitpredict.db_models import Kline, KronosPrediction, Parameter
from bitpredict.kronos.inference import run_inference
from bitpredict.kronos.timeframes import Timeframe

logger = logging.getLogger(__name__)

SIMS_TTL = 1200  # 20 min — enough to cover the monitoring phase


def _cache_sims(timeframe: Timeframe, result: dict, model_variant: str, temperature: float) -> None:
    """Store raw simulation samples in Redis so the frontend can display them."""
    try:
        r = _redis.Redis.from_url(str(get_settings().redis_url))
        r.setex(
            f"kronos:sims:{timeframe.value}",
            SIMS_TTL,
            json.dumps({
                "samples":       result.get("raw_samples", []),
                "ref_close":     result.get("ref_close"),
                "total":         result.get("sample_count", 30),
                "model_variant": model_variant,
                "temperature":   temperature,
            }),
        )
    except Exception as exc:
        logger.warning("Failed to cache sims in Redis: %s", exc)


def _get_param(db: Session, key: str, default: Any) -> Any:
    row = db.get(Parameter, key)
    if row is None:
        return default
    v = row.value_json
    return v.get("value", default) if isinstance(v, dict) else v


def load_context(db: Session, timeframe: Timeframe, context_length: int = 512) -> pd.DataFrame:
    """Fetch the last *context_length* closed candles for *timeframe* from the klines table."""
    from datetime import UTC, datetime
    now = datetime.now(tz=UTC)
    rows = db.execute(
        select(Kline)
        .where(
            Kline.symbol == "BTCUSDT",
            Kline.interval == timeframe.to_binance_interval(),
            Kline.close_time < now,
        )
        .order_by(Kline.open_time.desc())
        .limit(context_length)
    ).scalars().all()

    if not rows:
        raise ValueError(
            f"No klines for BTCUSDT/{timeframe.value} in DB. "
            "Run ingest_klines task first."
        )

    rows = sorted(rows, key=lambda k: k.open_time)
    df = pd.DataFrame([{
        "open_time": k.open_time,
        "open":   float(k.open),
        "high":   float(k.high),
        "low":    float(k.low),
        "close":  float(k.close),
        "volume": float(k.volume),
    } for k in rows])
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    return df


def run_prediction(
    timeframe: Timeframe | str,
    task_id: str | None = None,
    stopped_flag: bool = False,
    stop_check=None,
    progress_callback=None,
) -> KronosPrediction:
    """Full prediction pipeline: read config → load context → run inference → persist.

    Returns the KronosPrediction ORM record (status="done" or "stopped_by_user").
    Raises on error (record is marked status="error" before re-raising).
    """
    if isinstance(timeframe, str):
        timeframe = Timeframe(timeframe)

    db = get_session()
    try:
        context_length = int(_get_param(db, "kronos.context_length", 512))
        sample_count   = int(_get_param(db, "kronos.sample_count", 30))
        temperature    = float(_get_param(db, "kronos.temperature", 0.8))
        model_variant  = str(_get_param(
            db,
            f"kronos.variant.{timeframe.value}",
            timeframe.default_model_variant(),
        ))

        # Create in-progress record so the API can report "running" immediately.
        # id is populated via the DB sequence (nextval called in service to satisfy
        # the TimescaleDB composite PK requirement).
        from sqlalchemy import text as _text
        next_id = db.execute(_text("SELECT nextval('kronos_predictions_id_seq')")).scalar_one()

        predicted_at = datetime.now(tz=UTC)
        record = KronosPrediction(
            id=next_id,
            timeframe=timeframe.value,
            predicted_at=predicted_at,
            model_variant=model_variant,
            sample_count=sample_count,
            temperature=temperature,
            context_length=context_length,
            task_id=task_id,
            status="running",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        try:
            if stopped_flag:
                record.status = "stopped_by_user"
                db.commit()
                db.refresh(record)
                return record

            context = load_context(db, timeframe, context_length)
            result = run_inference(
                timeframe=timeframe,
                context_candles=context,
                sample_count=sample_count,
                model_variant=model_variant,
                temperature=temperature,
                stop_check=stop_check,
                progress_callback=progress_callback,
            )
            _cache_sims(timeframe, result, model_variant, temperature)

            record.target_candle_open_time  = result["target_candle_open_time"]
            record.target_candle_close_time = result["target_candle_close_time"]
            record.predicted_open           = result["predicted_open"]
            record.predicted_high           = result["predicted_high"]
            record.predicted_low            = result["predicted_low"]
            record.predicted_close          = result["predicted_close"]
            record.predicted_volume         = result["predicted_volume"]
            record.q10_close                = result["q10_close"]
            record.q90_close                = result["q90_close"]
            record.prob_bullish             = result["prob_bullish"]
            record.status = "done"
            db.commit()
            db.refresh(record)
            logger.info(
                "Kronos prediction saved: tf=%s id=%d close=%.2f",
                timeframe.value, record.id, float(record.predicted_close),
            )
            return record

        except RuntimeError as exc:
            if "stopped" in str(exc).lower():
                record.status = "stopped_by_user"
            else:
                record.status = "error"
            db.commit()
            if record.status == "stopped_by_user":
                return record
            raise
        except Exception:
            record.status = "error"
            db.commit()
            raise

    finally:
        db.close()
