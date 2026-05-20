"""Celery tasks for Kronos predictions."""

from __future__ import annotations

import asyncio
import logging
import time

from bitpredict.scheduling.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="kronos.run_15m_cycle", bind=True, queue="predictions")
def run_15m_cycle(self):
    """15m full cycle: ingest latest klines → run Kronos prediction, sequential."""
    import redis as _redis
    from bitpredict.config import get_settings
    from bitpredict.data.historical import download_and_persist_latest
    from bitpredict.kronos.service import run_prediction
    from bitpredict.kronos.timeframes import Timeframe

    timeframe = "15m"
    tf = Timeframe(timeframe)
    task_id: str = self.request.id
    settings = get_settings()

    # ── Step 1: Ingest ────────────────────────────────────────────────────────
    self.update_state(
        state="PROGRESS",
        meta={"step": "ingesting klines", "current": 0, "total": 30, "eta_seconds": None},
    )
    try:
        new_candles = _run_async(download_and_persist_latest("BTCUSDT", timeframe))
        logger.info("15m cycle: ingested %d new candles", new_candles)
    except Exception as exc:
        logger.error("15m cycle: ingest failed: %s", exc)
        raise

    # ── Step 2: Predict ───────────────────────────────────────────────────────
    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    stop_key = f"kronos:stop:{task_id}"
    sample_times: list[float] = []

    def stop_check() -> bool:
        return bool(r.get(stop_key))

    def progress_callback(current: int, total: int) -> None:
        sample_times.append(time.monotonic())
        eta = None
        if len(sample_times) >= 2:
            avg_s = (sample_times[-1] - sample_times[0]) / (len(sample_times) - 1)
            eta = int(avg_s * (total - current))
        self.update_state(
            state="PROGRESS",
            meta={"step": "inference", "current": current, "total": total, "eta_seconds": eta},
        )

    self.update_state(
        state="PROGRESS",
        meta={"step": "loading context", "current": 0, "total": 30, "eta_seconds": None},
    )

    record = run_prediction(
        tf,
        task_id=task_id,
        stopped_flag=stop_check(),
        stop_check=stop_check,
        progress_callback=progress_callback,
    )

    if record.status == "stopped_by_user":
        logger.info("15m cycle stopped by user")
        return {"status": "stopped_by_user", "timeframe": timeframe}

    logger.info(
        "15m cycle done: id=%d close=%.2f bullish=%.0f%%",
        record.id,
        float(record.predicted_close or 0),
        float(record.prob_bullish or 0) * 100,
    )
    return {"status": "done", "timeframe": timeframe, "prediction_id": record.id}


@celery_app.task(name="kronos.run_1h_cycle", bind=True, queue="predictions")
def run_1h_cycle(self):
    """1h full cycle: ingest latest klines → run Kronos prediction, sequential."""
    import redis as _redis
    from bitpredict.config import get_settings
    from bitpredict.data.historical import download_and_persist_latest
    from bitpredict.kronos.service import run_prediction
    from bitpredict.kronos.timeframes import Timeframe

    timeframe = "1h"
    tf = Timeframe(timeframe)
    task_id: str = self.request.id
    settings = get_settings()

    # ── Step 1: Ingest ────────────────────────────────────────────────────────
    self.update_state(
        state="PROGRESS",
        meta={"step": "ingesting klines", "current": 0, "total": 30, "eta_seconds": None},
    )
    try:
        new_candles = _run_async(download_and_persist_latest("BTCUSDT", timeframe))
        logger.info("1h cycle: ingested %d new candles", new_candles)
    except Exception as exc:
        logger.error("1h cycle: ingest failed: %s", exc)
        raise

    # ── Step 2: Predict ───────────────────────────────────────────────────────
    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    stop_key = f"kronos:stop:{task_id}"
    sample_times: list[float] = []

    def stop_check() -> bool:
        return bool(r.get(stop_key))

    def progress_callback(current: int, total: int) -> None:
        sample_times.append(time.monotonic())
        eta = None
        if len(sample_times) >= 2:
            avg_s = (sample_times[-1] - sample_times[0]) / (len(sample_times) - 1)
            eta = int(avg_s * (total - current))
        self.update_state(
            state="PROGRESS",
            meta={"step": "inference", "current": current, "total": total, "eta_seconds": eta},
        )

    self.update_state(
        state="PROGRESS",
        meta={"step": "loading context", "current": 0, "total": 30, "eta_seconds": None},
    )

    record = run_prediction(
        tf,
        task_id=task_id,
        stopped_flag=stop_check(),
        stop_check=stop_check,
        progress_callback=progress_callback,
    )

    if record.status == "stopped_by_user":
        logger.info("1h cycle stopped by user")
        return {"status": "stopped_by_user", "timeframe": timeframe}

    logger.info(
        "1h cycle done: id=%d close=%.2f bullish=%.0f%%",
        record.id,
        float(record.predicted_close or 0),
        float(record.prob_bullish or 0) * 100,
    )
    return {"status": "done", "timeframe": timeframe, "prediction_id": record.id}


@celery_app.task(name="kronos.run_1d_cycle", bind=True, queue="predictions")
def run_1d_cycle(self):
    """1d full cycle: ingest latest klines → run Kronos prediction, sequential."""
    import redis as _redis
    from bitpredict.config import get_settings
    from bitpredict.data.historical import download_and_persist_latest
    from bitpredict.kronos.service import run_prediction
    from bitpredict.kronos.timeframes import Timeframe

    timeframe = "1d"
    tf = Timeframe(timeframe)
    task_id: str = self.request.id
    settings = get_settings()

    # ── Step 1: Ingest ────────────────────────────────────────────────────────
    self.update_state(
        state="PROGRESS",
        meta={"step": "ingesting klines", "current": 0, "total": 30, "eta_seconds": None},
    )
    try:
        new_candles = _run_async(download_and_persist_latest("BTCUSDT", timeframe))
        logger.info("1d cycle: ingested %d new candles", new_candles)
    except Exception as exc:
        logger.error("1d cycle: ingest failed: %s", exc)
        raise

    # ── Step 2: Predict ───────────────────────────────────────────────────────
    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    stop_key = f"kronos:stop:{task_id}"
    sample_times: list[float] = []

    def stop_check() -> bool:
        return bool(r.get(stop_key))

    def progress_callback(current: int, total: int) -> None:
        sample_times.append(time.monotonic())
        eta = None
        if len(sample_times) >= 2:
            avg_s = (sample_times[-1] - sample_times[0]) / (len(sample_times) - 1)
            eta = int(avg_s * (total - current))
        self.update_state(
            state="PROGRESS",
            meta={"step": "inference", "current": current, "total": total, "eta_seconds": eta},
        )

    self.update_state(
        state="PROGRESS",
        meta={"step": "loading context", "current": 0, "total": 30, "eta_seconds": None},
    )

    record = run_prediction(
        tf,
        task_id=task_id,
        stopped_flag=stop_check(),
        stop_check=stop_check,
        progress_callback=progress_callback,
    )

    if record.status == "stopped_by_user":
        logger.info("1d cycle stopped by user")
        return {"status": "stopped_by_user", "timeframe": timeframe}

    logger.info(
        "1d cycle done: id=%d close=%.2f bullish=%.0f%%",
        record.id,
        float(record.predicted_close or 0),
        float(record.prob_bullish or 0) * 100,
    )
    return {"status": "done", "timeframe": timeframe, "prediction_id": record.id}


@celery_app.task(name="kronos.run_prediction", bind=True, queue="predictions")
def run_kronos_prediction(self, timeframe: str):
    """Run Kronos inference for one timeframe and persist the result.

    Reports per-sample progress via Celery state. Supports soft stop via
    Redis key kronos:stop:{task_id}.
    """
    import redis as _redis
    from bitpredict.config import get_settings
    from bitpredict.kronos.service import run_prediction
    from bitpredict.kronos.timeframes import Timeframe

    tf = Timeframe(timeframe)
    task_id: str = self.request.id
    settings = get_settings()

    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    stop_key = f"kronos:stop:{task_id}"
    sample_times: list[float] = []

    def stop_check() -> bool:
        return bool(r.get(stop_key))

    def progress_callback(current: int, total: int) -> None:
        sample_times.append(time.monotonic())
        if len(sample_times) >= 2:
            avg_s = (sample_times[-1] - sample_times[0]) / (len(sample_times) - 1)
            eta = int(avg_s * (total - current))
        else:
            eta = None
        self.update_state(
            state="PROGRESS",
            meta={"step": "inference", "current": current, "total": total, "eta_seconds": eta},
        )

    self.update_state(
        state="PROGRESS",
        meta={"step": "loading context", "current": 0, "total": 1, "eta_seconds": None},
    )

    record = run_prediction(
        tf,
        task_id=task_id,
        stopped_flag=stop_check(),
        stop_check=stop_check,
        progress_callback=progress_callback,
    )

    if record.status == "stopped_by_user":
        logger.info("Kronos prediction stopped by user: tf=%s", timeframe)
        return {"status": "stopped_by_user", "timeframe": timeframe}

    logger.info(
        "Kronos prediction done: tf=%s id=%d close=%.2f q10=%.2f q90=%.2f bullish=%.0f%%",
        timeframe, record.id,
        float(record.predicted_close or 0),
        float(record.q10_close or 0),
        float(record.q90_close or 0),
        float(record.prob_bullish or 0) * 100,
    )
    return {"status": "done", "timeframe": timeframe, "prediction_id": record.id}


@celery_app.task(name="kronos.fill_actuals", queue="predictions")
def fill_actuals():
    """Fill actual OHLCV + accuracy metrics for predictions whose target candle has closed.

    Runs every 5 minutes. Finds done predictions with null actual_close and
    target_candle_close_time in the past, then joins against the klines table.
    """
    from datetime import UTC, datetime
    from sqlalchemy import select
    from bitpredict.db import get_session
    from bitpredict.db_models import KronosPrediction, Kline
    from bitpredict.kronos.timeframes import Timeframe

    db = get_session()
    try:
        now = datetime.now(tz=UTC)

        pending = db.execute(
            select(KronosPrediction)
            .where(
                KronosPrediction.status == "done",
                KronosPrediction.target_candle_close_time.isnot(None),
                KronosPrediction.target_candle_close_time < now,
            )
            .order_by(KronosPrediction.predicted_at)
        ).scalars().all()

        updated = 0
        for pred in pending:
            tf = Timeframe(pred.timeframe)
            interval = tf.to_binance_interval()

            # Normalize target open time to UTC for comparison
            target_open = pred.target_candle_open_time
            if target_open and target_open.tzinfo is None:
                target_open = target_open.replace(tzinfo=UTC)

            kline = db.execute(
                select(Kline).where(
                    Kline.symbol == "BTCUSDT",
                    Kline.interval == interval,
                    Kline.open_time == target_open,
                )
            ).scalar_one_or_none()

            if kline is None:
                continue

            pred.actual_open   = float(kline.open)
            pred.actual_high   = float(kline.high)
            pred.actual_low    = float(kline.low)
            pred.actual_close  = float(kline.close)
            pred.actual_volume = float(kline.volume)

            # Direction: model is "bullish" if prob_bullish >= 0.5 (consistent with UI).
            # Actual is "bullish" if the candle closed higher than it opened.
            pred_bullish   = float(pred.prob_bullish or 0) >= 0.5
            actual_bullish = float(kline.close) > float(kline.open)
            pred.direction_correct = pred_bullish == actual_bullish

            # Signed close error: positive = predicted too high
            pred.close_error_pct = (
                (float(pred.predicted_close) - float(kline.close))
                / float(kline.close) * 100
            )

            updated += 1

        db.commit()
        logger.info("fill_actuals: updated %d predictions", updated)
        return {"updated": updated}
    finally:
        db.close()


@celery_app.task(name="kronos.run_backtest", bind=True, queue="backtests")
def run_kronos_backtest(self, timeframe: str, sample_size: int | None = None, sample_count: int | None = None, initial_capital: float | None = None, position_pct: float | None = None, compound: bool = False):
    """Run Kronos backtest for one timeframe and persist aggregated metrics.

    sample_size: number of historical candles to test (None = default from _SAMPLE_SIZES)
    sample_count: simulations per sample (None = use parameter table default)
    """
    import redis as _redis
    from bitpredict.config import get_settings
    from bitpredict.db import get_session
    from bitpredict.kronos.backtest import run_backtest
    from bitpredict.kronos.service import _get_param
    from bitpredict.kronos.timeframes import Timeframe

    tf = Timeframe(timeframe)
    task_id: str = self.request.id
    settings = get_settings()

    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    stop_key = f"kronos:stop:{task_id}"
    sample_times: list[float] = []

    # Shared state so both callbacks can write a consistent meta dict.
    _state: dict = {"sample_current": 0, "sample_total": 0, "eta": None}

    def stop_check() -> bool:
        return bool(r.get(stop_key))

    def progress_callback(current: int, total: int) -> None:
        sample_times.append(time.monotonic())
        if len(sample_times) >= 2:
            avg_s = (sample_times[-1] - sample_times[0]) / (len(sample_times) - 1)
            eta = int(avg_s * (total - current))
        else:
            eta = None
        _state["sample_current"] = current
        _state["sample_total"] = total
        _state["eta"] = eta
        self.update_state(
            state="PROGRESS",
            meta={
                "step": "backtest",
                "current": current,
                "total": total,
                "eta_seconds": eta,
                "sim_current": 0,
                "sim_total": 0,
            },
        )

    def sim_progress_callback(sim_current: int, sim_total: int) -> None:
        # Per-sample: shows progress of simulations within the current sample.
        # Resets to 0 when the next sample starts (progress_callback fires).
        self.update_state(
            state="PROGRESS",
            meta={
                "step": "backtest",
                "current": _state["sample_current"],
                "total": _state["sample_total"],
                "eta_seconds": _state["eta"],
                "sim_current": sim_current,
                "sim_total": sim_total,
            },
        )

    self.update_state(
        state="PROGRESS",
        meta={"step": "loading model", "current": 0, "total": 0, "eta_seconds": None, "sim_current": 0, "sim_total": 0},
    )

    db = get_session()
    try:
        effective_sample_count = sample_count if sample_count is not None else int(_get_param(db, "kronos.backtest_sample_count", 30))
        temperature   = float(_get_param(db, "kronos.temperature", 0.8))
        model_variant = str(_get_param(db, f"kronos.variant.{timeframe}", tf.default_model_variant()))

        self.update_state(
            state="PROGRESS",
            meta={"step": "loading samples", "current": 0, "total": 0, "eta_seconds": None, "sim_current": 0, "sim_total": 0},
        )

        result = run_backtest(
            db=db,
            timeframe=tf,
            model_variant=model_variant,
            sample_count=effective_sample_count,
            sample_size=sample_size,
            temperature=temperature,
            initial_capital=initial_capital,
            position_pct=position_pct,
            compound=compound,
            task_id=task_id,
            stop_check=stop_check,
            progress_callback=progress_callback,
            sim_progress_callback=sim_progress_callback,
        )
    finally:
        db.close()

    logger.info(
        "Kronos backtest done: tf=%s status=%s dir_acc=%.1f%%",
        timeframe, result["status"],
        result["metrics"].get("directional_accuracy", 0),
    )
    return {"status": result["status"], "timeframe": timeframe, "backtest_id": result["record_id"]}
