"""FastAPI router for Kronos multi-timeframe prediction endpoints."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import redis as _redis
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from bitpredict.api.auth import require_api_key
from bitpredict.api.dependencies import get_db
from bitpredict.config import get_settings
from bitpredict.db_models import KronosPrediction
from bitpredict.kronos.timeframes import Timeframe
from bitpredict.scheduling.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kronos", tags=["Kronos"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class KronosPredictionSchema(BaseModel):
    id: int
    timeframe: str
    predicted_at: datetime
    target_candle_open_time: datetime | None
    target_candle_close_time: datetime | None
    predicted_open: float | None
    predicted_high: float | None
    predicted_low: float | None
    predicted_close: float | None
    predicted_volume: float | None
    q10_close: float | None
    q90_close: float | None
    prob_bullish: float | None
    actual_open: float | None
    actual_high: float | None
    actual_low: float | None
    actual_close: float | None
    actual_volume: float | None
    direction_correct: bool | None
    close_error_pct: float | None
    model_variant: str | None
    sample_count: int | None
    temperature: float | None
    context_length: int | None
    task_id: str | None
    status: str

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class KronosHistoryResponse(BaseModel):
    items: list[KronosPredictionSchema]
    total: int
    limit: int
    offset: int


class KronosProgressResponse(BaseModel):
    timeframe: str
    task_id: str | None
    state: str
    step: str | None
    current: int | None
    total: int | None
    eta_seconds: int | None


class KronosTfHealth(BaseModel):
    last_predicted_at: datetime | None
    last_status: str | None
    last_ingest_at: datetime | None


class KronosHealthResponse(BaseModel):
    status: str
    timeframes: dict[str, KronosTfHealth]


class TriggerResponse(BaseModel):
    task_id: str
    timeframe: str
    message: str


class StopResponse(BaseModel):
    timeframe: str
    task_id: str | None
    message: str


class KronosScoreboardResponse(BaseModel):
    timeframe: str
    total_evaluated: int        # predictions with actual_close filled in
    total_predictions: int      # all done predictions
    directional_accuracy: float | None   # 0.0–1.0
    avg_abs_error_pct: float | None      # mean |close_error_pct|
    best_error_pct: float | None         # smallest |close_error_pct| (best call)
    worst_error_pct: float | None        # largest |close_error_pct| (worst call)
    bullish_count: int | None            # predictions that said bullish
    correct_bullish: int | None          # bullish calls that were correct
    correct_bearish: int | None          # bearish calls that were correct


class KronosSimSampleResponse(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float


class KronosSimsResponse(BaseModel):
    timeframe: str
    samples: list[KronosSimSampleResponse]
    ref_close: float | None
    total: int
    model_variant: str | None
    temperature: float | None
    available: bool

    model_config = {"protected_namespaces": ()}


class KronosLiveCandleResponse(BaseModel):
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    live_price: float
    change_pct: float
    seconds_until_close: int


# ── helpers ───────────────────────────────────────────────────────────────────


def _validate_timeframe(timeframe: str) -> Timeframe:
    try:
        return Timeframe(timeframe)
    except ValueError:
        valid = [tf.value for tf in Timeframe]
        raise HTTPException(status_code=422, detail=f"Invalid timeframe '{timeframe}'. Valid: {valid}")


def _latest_prediction(db: Session, timeframe: str) -> KronosPrediction | None:
    return db.execute(
        select(KronosPrediction)
        .where(KronosPrediction.timeframe == timeframe)
        .order_by(KronosPrediction.predicted_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _running_prediction(db: Session, timeframe: str) -> KronosPrediction | None:
    return db.execute(
        select(KronosPrediction)
        .where(
            KronosPrediction.timeframe == timeframe,
            KronosPrediction.status == "running",
        )
        .order_by(KronosPrediction.predicted_at.desc())
        .limit(1)
    ).scalar_one_or_none()


# ── endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/prediction/{timeframe}",
    response_model=KronosPredictionSchema,
    summary="Get latest prediction for a timeframe",
)
def get_prediction(
    timeframe: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> KronosPredictionSchema:
    _validate_timeframe(timeframe)
    record = _latest_prediction(db, timeframe)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No prediction found for timeframe '{timeframe}'")
    return KronosPredictionSchema.model_validate(record)


@router.get(
    "/history/{timeframe}",
    response_model=KronosHistoryResponse,
    summary="Paginated prediction history (canonical candles only, deduplicated)",
)
def get_history(
    timeframe: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> KronosHistoryResponse:
    _validate_timeframe(timeframe)

    # Over-fetch to have enough rows after canonical filtering + deduplication
    rows = db.execute(
        select(KronosPrediction)
        .where(KronosPrediction.timeframe == timeframe)
        .order_by(KronosPrediction.predicted_at.desc())
        .limit(limit * 10 + 50)
    ).scalars().all()

    # Keep only canonical candles: minute in (0,15,30,45) and second == 0
    # This excludes test-mode entries which have arbitrary open_time seconds
    CANONICAL_MINUTES = {0, 15, 30, 45}

    def _is_canonical(r: KronosPrediction) -> bool:
        t = r.target_candle_open_time
        return t is not None and t.minute in CANONICAL_MINUTES and t.second == 0

    canonical = [r for r in rows if _is_canonical(r)]

    # Deduplicate by target_candle_open_time — keep only the latest predicted_at per candle
    seen: dict = {}
    for r in canonical:
        key = r.target_candle_open_time
        if key not in seen or r.predicted_at > seen[key].predicted_at:
            seen[key] = r

    deduped = sorted(seen.values(), key=lambda r: r.predicted_at, reverse=True)
    total = len(deduped)
    page = deduped[offset: offset + limit]

    return KronosHistoryResponse(
        items=[KronosPredictionSchema.model_validate(r) for r in page],
        total=total,
        limit=limit,
        offset=offset,
    )


class KronosBacktestSchema(BaseModel):
    id: int
    timeframe: str
    executed_at: datetime
    sample_size: int | None
    model_variant: str | None
    sample_count: int | None
    context_length: int | None
    directional_accuracy: float | None
    mape_close: float | None
    mape_high: float | None
    mape_low: float | None
    mape_volume: float | None
    band_width_pct_avg: float | None
    band_calibration_pct: float | None
    high_conf_accuracy: float | None = None
    high_conf_count: int | None = None
    duration_seconds: int | None
    status: str
    task_id: str | None
    sample_from: datetime | None
    sample_to: datetime | None
    initial_capital: float | None
    position_pct: float | None
    compound: bool | None
    final_equity: float | None
    net_profit: float | None
    net_profit_pct: float | None
    profit_factor: float | None
    win_rate_pct: float | None
    payoff_ratio: float | None
    max_drawdown_pct: float | None
    max_consecutive_losses: int | None
    recovery_factor: float | None
    sharpe_ratio: float | None
    avg_trade_pct: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None
    total_trades: int | None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class KronosBacktestDataInfoItem(BaseModel):
    timeframe: str
    binance_interval: str
    total_klines: int
    first_open_time: datetime | None
    last_open_time: datetime | None
    eligible_samples: int
    expected_sample_size: int | None
    actual_sample_size: int


class KronosBacktestDataInfoResponse(BaseModel):
    timeframes: dict[str, KronosBacktestDataInfoItem]


class KronosBacktestProgressResponse(BaseModel):
    timeframe: str
    task_id: str | None
    state: str
    step: str | None
    current: int | None
    total: int | None
    eta_seconds: int | None
    sim_current: int | None = None
    sim_total: int | None = None


@router.get(
    "/backtest/data-info",
    response_model=KronosBacktestDataInfoResponse,
    summary="Kline availability and sample info for all timeframes",
)
def get_backtest_data_info(
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> KronosBacktestDataInfoResponse:
    from sqlalchemy import func as _func
    from bitpredict.db_models import Kline
    from bitpredict.kronos.backtest import _SAMPLE_SIZES

    result: dict[str, KronosBacktestDataInfoItem] = {}
    for tf in Timeframe:
        interval = tf.to_binance_interval()
        row = db.execute(
            select(
                _func.count(Kline.open_time).label("total"),
                _func.min(Kline.open_time).label("first_open"),
                _func.max(Kline.open_time).label("last_open"),
            ).where(Kline.symbol == "BTCUSDT", Kline.interval == interval)
        ).one()

        total: int = row.total or 0
        eligible = max(0, total - 512)
        expected = _SAMPLE_SIZES.get(tf.value)
        actual = min(expected, eligible) if expected is not None else eligible

        result[tf.value] = KronosBacktestDataInfoItem(
            timeframe=tf.value,
            binance_interval=interval,
            total_klines=total,
            first_open_time=row.first_open,
            last_open_time=row.last_open,
            eligible_samples=eligible,
            expected_sample_size=expected,
            actual_sample_size=actual,
        )

    return KronosBacktestDataInfoResponse(timeframes=result)


@router.get(
    "/backtest/{timeframe}",
    response_model=KronosBacktestSchema,
    summary="Latest backtest metrics for a timeframe",
)
def get_backtest(
    timeframe: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
    from bitpredict.db_models import KronosBacktest
    _validate_timeframe(timeframe)
    record = db.execute(
        select(KronosBacktest)
        .where(KronosBacktest.timeframe == timeframe)
        .order_by(KronosBacktest.executed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail=f"No backtest found for timeframe '{timeframe}'")
    return KronosBacktestSchema.model_validate(record)


@router.get(
    "/backtest/{timeframe}/history",
    response_model=list[KronosBacktestSchema],
    summary="All backtest runs for a timeframe",
)
def get_backtest_history(
    timeframe: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> list[KronosBacktestSchema]:
    from bitpredict.db_models import KronosBacktest
    _validate_timeframe(timeframe)
    rows = db.execute(
        select(KronosBacktest)
        .where(KronosBacktest.timeframe == timeframe)
        .order_by(KronosBacktest.executed_at.desc())
    ).scalars().all()
    return [KronosBacktestSchema.model_validate(r) for r in rows]


@router.get(
    "/health",
    response_model=KronosHealthResponse,
    summary="Aggregated Kronos health: last prediction and ingest per timeframe",
)
def get_health(
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> KronosHealthResponse:
    from bitpredict.db_models import Kline

    tf_health: dict[str, KronosTfHealth] = {}
    for tf in Timeframe:
        pred = _latest_prediction(db, tf.value)
        last_kline = db.execute(
            select(Kline)
            .where(Kline.symbol == "BTCUSDT", Kline.interval == tf.to_binance_interval())
            .order_by(Kline.open_time.desc())
            .limit(1)
        ).scalar_one_or_none()

        tf_health[tf.value] = KronosTfHealth(
            last_predicted_at=pred.predicted_at if pred else None,
            last_status=pred.status if pred else None,
            last_ingest_at=last_kline.open_time if last_kline else None,
        )

    overall = "ok" if any(v.last_predicted_at for v in tf_health.values()) else "no_data"
    return KronosHealthResponse(status=overall, timeframes=tf_health)


@router.get(
    "/progress/{timeframe}",
    response_model=KronosProgressResponse,
    summary="Progress of the currently running prediction task",
)
def get_progress(
    timeframe: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> KronosProgressResponse:
    _validate_timeframe(timeframe)
    running = _running_prediction(db, timeframe)

    if running is None or running.task_id is None:
        return KronosProgressResponse(
            timeframe=timeframe,
            task_id=None,
            state="idle",
            step=None,
            current=None,
            total=None,
            eta_seconds=None,
        )

    result = AsyncResult(running.task_id, app=celery_app)
    meta: dict[str, Any] = result.info if isinstance(result.info, dict) else {}

    return KronosProgressResponse(
        timeframe=timeframe,
        task_id=running.task_id,
        state=result.state,
        step=meta.get("step"),
        current=meta.get("current"),
        total=meta.get("total"),
        eta_seconds=meta.get("eta_seconds"),
    )


@router.post(
    "/prediction/{timeframe}/trigger",
    response_model=TriggerResponse,
    summary="Trigger an immediate prediction (does not wait for Celery beat)",
)
def trigger_prediction(
    timeframe: str,
    _: str = Depends(require_api_key),
) -> TriggerResponse:
    _validate_timeframe(timeframe)
    from bitpredict.kronos.tasks import run_15m_cycle, run_kronos_prediction

    if timeframe == "15m":
        task = run_15m_cycle.apply_async()
    else:
        task = run_kronos_prediction.apply_async(args=[timeframe])
    return TriggerResponse(
        task_id=task.id,
        timeframe=timeframe,
        message=f"Prediction task dispatched (task_id={task.id})",
    )


@router.post(
    "/prediction/{timeframe}/stop",
    response_model=StopResponse,
    summary="Soft-stop the currently running prediction task",
)
def stop_prediction(
    timeframe: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> StopResponse:
    _validate_timeframe(timeframe)
    running = _running_prediction(db, timeframe)

    if running is None or running.task_id is None:
        return StopResponse(
            timeframe=timeframe,
            task_id=None,
            message="No running prediction found for this timeframe",
        )

    settings = get_settings()
    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    stop_key = f"kronos:stop:{running.task_id}"
    r.setex(stop_key, 300, "1")  # expire after 5 min (task will have finished by then)

    return StopResponse(
        timeframe=timeframe,
        task_id=running.task_id,
        message=f"Stop signal sent (key={stop_key}). Task will halt after current sample.",
    )


@router.get(
    "/scoreboard/{timeframe}",
    response_model=KronosScoreboardResponse,
    summary="Aggregated accuracy scoreboard for a timeframe",
)
def get_scoreboard(
    timeframe: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> KronosScoreboardResponse:
    from sqlalchemy import func as _func

    _validate_timeframe(timeframe)

    total_predictions: int = db.execute(
        select(_func.count())
        .select_from(KronosPrediction)
        .where(KronosPrediction.timeframe == timeframe, KronosPrediction.status == "done")
    ).scalar_one()

    evaluated = db.execute(
        select(KronosPrediction)
        .where(
            KronosPrediction.timeframe == timeframe,
            KronosPrediction.status == "done",
            KronosPrediction.actual_close.isnot(None),
        )
    ).scalars().all()

    total_evaluated = len(evaluated)

    if total_evaluated == 0:
        return KronosScoreboardResponse(
            timeframe=timeframe,
            total_evaluated=0,
            total_predictions=total_predictions,
            directional_accuracy=None,
            avg_abs_error_pct=None,
            best_error_pct=None,
            worst_error_pct=None,
            bullish_count=None,
            correct_bullish=None,
            correct_bearish=None,
        )

    def _is_bullish_pred(r) -> bool:
        return float(r.prob_bullish or 0) >= 0.5

    errors = [abs(float(r.close_error_pct)) for r in evaluated if r.close_error_pct is not None]
    correct = [r for r in evaluated if r.direction_correct is True]
    bullish_preds = [r for r in evaluated if _is_bullish_pred(r)]
    correct_bullish = sum(1 for r in correct if _is_bullish_pred(r))
    correct_bearish = sum(1 for r in correct if not _is_bullish_pred(r))

    return KronosScoreboardResponse(
        timeframe=timeframe,
        total_evaluated=total_evaluated,
        total_predictions=total_predictions,
        directional_accuracy=len(correct) / total_evaluated if total_evaluated else None,
        avg_abs_error_pct=sum(errors) / len(errors) if errors else None,
        best_error_pct=min(errors) if errors else None,
        worst_error_pct=max(errors) if errors else None,
        bullish_count=len(bullish_preds),
        correct_bullish=correct_bullish,
        correct_bearish=correct_bearish,
    )


class KronosBacktestTradeSchema(BaseModel):
    id: int
    target_open_time: datetime
    backtest_id: int
    timeframe: str
    predicted_close: float | None
    predicted_high: float | None
    predicted_low: float | None
    q10_close: float | None
    q90_close: float | None
    actual_open: float | None
    actual_close: float | None
    actual_high: float | None
    actual_low: float | None
    prob_bullish: float | None
    direction_correct: bool | None
    close_error_pct: float | None
    band_covers_actual: bool | None
    trade_return_pct: float | None
    trade_pnl_usd: float | None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class BacktestTriggerRequest(BaseModel):
    sample_size: int | None = None       # None = use default from _SAMPLE_SIZES
    sample_count: int = 30               # simulations per sample
    initial_capital: float | None = None # portfolio simulation capital
    position_pct: float | None = None    # fraction of capital per trade (0.0–1.0)
    compound: bool = False               # reinvest profits between trades


@router.get(
    "/backtest/{timeframe}/trades",
    response_model=list[KronosBacktestTradeSchema],
    summary="Per-trade results from the latest (or specified) backtest run",
)
def get_backtest_trades(
    timeframe: str,
    limit: int = Query(1000, ge=1, le=5000),
    backtest_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> list[KronosBacktestTradeSchema]:
    from bitpredict.db_models import KronosBacktest, KronosBacktestTrade

    _validate_timeframe(timeframe)

    if backtest_id is None:
        latest = db.execute(
            select(KronosBacktest)
            .where(KronosBacktest.timeframe == timeframe)
            .order_by(KronosBacktest.executed_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest is None:
            return []
        backtest_id = latest.id

    trades = db.execute(
        select(KronosBacktestTrade)
        .where(
            KronosBacktestTrade.backtest_id == backtest_id,
            KronosBacktestTrade.timeframe == timeframe,
        )
        .order_by(KronosBacktestTrade.target_open_time.asc())
        .limit(limit)
    ).scalars().all()

    return [KronosBacktestTradeSchema.model_validate(t) for t in trades]


@router.post(
    "/backtest/{timeframe}/trigger",
    response_model=TriggerResponse,
    summary="Trigger a manual backtest run",
)
def trigger_backtest(
    timeframe: str,
    body: BacktestTriggerRequest = BacktestTriggerRequest(),
    _: str = Depends(require_api_key),
) -> TriggerResponse:
    _validate_timeframe(timeframe)
    from bitpredict.kronos.tasks import run_kronos_backtest

    settings = get_settings()
    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    redis_key = f"kronos:backtest_task:{timeframe}"

    # Don't overwrite the key if an active task is already tracked
    existing_task_id = r.get(redis_key)
    if existing_task_id:
        existing = AsyncResult(existing_task_id, app=celery_app)
        if existing.state not in ("SUCCESS", "FAILURE", "REVOKED"):
            return TriggerResponse(
                task_id=existing_task_id,
                timeframe=timeframe,
                message=f"Backtest already running (task_id={existing_task_id})",
            )

    task = run_kronos_backtest.apply_async(args=[timeframe, body.sample_size, body.sample_count, body.initial_capital, body.position_pct, body.compound])
    r.setex(redis_key, 86400, task.id)

    return TriggerResponse(
        task_id=task.id,
        timeframe=timeframe,
        message=f"Backtest task dispatched (task_id={task.id})",
    )


@router.get(
    "/backtest/{timeframe}/progress",
    response_model=KronosBacktestProgressResponse,
    summary="Progress of the currently running backtest task",
)
def get_backtest_progress(
    timeframe: str,
    _: str = Depends(require_api_key),
) -> KronosBacktestProgressResponse:
    _validate_timeframe(timeframe)
    settings = get_settings()
    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    task_id = r.get(f"kronos:backtest_task:{timeframe}")

    if not task_id:
        return KronosBacktestProgressResponse(
            timeframe=timeframe, task_id=None, state="idle",
            step=None, current=None, total=None, eta_seconds=None,
        )

    result = AsyncResult(task_id, app=celery_app)
    meta: dict[str, Any] = result.info if isinstance(result.info, dict) else {}

    # Clear Redis key if the task has finished
    if result.state in ("SUCCESS", "FAILURE", "REVOKED"):
        r.delete(f"kronos:backtest_task:{timeframe}")

    return KronosBacktestProgressResponse(
        timeframe=timeframe,
        task_id=task_id,
        state=result.state,
        step=meta.get("step"),
        current=meta.get("current"),
        total=meta.get("total"),
        eta_seconds=meta.get("eta_seconds"),
        sim_current=meta.get("sim_current"),
        sim_total=meta.get("sim_total"),
    )


@router.post(
    "/backtest/{timeframe}/stop",
    response_model=StopResponse,
    summary="Soft-stop the currently running backtest task",
)
def stop_backtest(
    timeframe: str,
    _: str = Depends(require_api_key),
) -> StopResponse:
    _validate_timeframe(timeframe)
    settings = get_settings()
    r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    task_id = r.get(f"kronos:backtest_task:{timeframe}")

    if not task_id:
        return StopResponse(timeframe=timeframe, task_id=None, message="No running backtest found")

    stop_key = f"kronos:stop:{task_id}"
    r.setex(stop_key, 300, "1")

    return StopResponse(
        timeframe=timeframe,
        task_id=task_id,
        message=f"Stop signal sent (key={stop_key}). Backtest will halt after current sample.",
    )


@router.get(
    "/prediction/{timeframe}/sims",
    response_model=KronosSimsResponse,
    summary="Raw simulation samples from the last inference run (Redis cache)",
)
def get_sims(
    timeframe: str,
    _: str = Depends(require_api_key),
) -> KronosSimsResponse:
    _validate_timeframe(timeframe)
    settings = get_settings()

    raw: str | None = None
    try:
        r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
        raw = r.get(f"kronos:sims:{timeframe}")
    except Exception as exc:
        logger.warning("Redis error fetching sims for %s: %s", timeframe, exc)

    if raw is None:
        return KronosSimsResponse(
            timeframe=timeframe,
            samples=[],
            ref_close=None,
            total=0,
            model_variant=None,
            temperature=None,
            available=False,
        )

    data = json.loads(raw)
    samples = [
        KronosSimSampleResponse(**s)
        for s in data.get("samples", [])
        if all(k in s for k in ("open", "high", "low", "close", "volume"))
    ]
    return KronosSimsResponse(
        timeframe=timeframe,
        samples=samples,
        ref_close=data.get("ref_close"),
        total=data.get("total", len(samples)),
        model_variant=data.get("model_variant"),
        temperature=data.get("temperature"),
        available=True,
    )


@router.get(
    "/live-candle/{timeframe}",
    response_model=KronosLiveCandleResponse,
    summary="Current live candle OHLCV + live price from Binance",
)
def get_live_candle(
    timeframe: str,
    _: str = Depends(require_api_key),
) -> KronosLiveCandleResponse:
    tf = _validate_timeframe(timeframe)
    interval = tf.to_binance_interval()

    binance_base = get_settings().binance_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=5.0) as client:
            klines_resp = client.get(
                f"{binance_base}/api/v3/klines",
                params={"symbol": "BTCUSDT", "interval": interval, "limit": 1},
            )
            klines_resp.raise_for_status()
            ticker_resp = client.get(
                f"{binance_base}/api/v3/ticker/price",
                params={"symbol": "BTCUSDT"},
            )
            ticker_resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Binance API error: {exc}") from exc

    kline = klines_resp.json()[0]
    open_time = datetime.fromtimestamp(kline[0] / 1000, tz=UTC)
    close_time = datetime.fromtimestamp(kline[6] / 1000, tz=UTC)
    candle_open = float(kline[1])
    candle_high = float(kline[2])
    candle_low = float(kline[3])
    candle_close = float(kline[4])
    candle_volume = float(kline[5])

    live_price = float(ticker_resp.json()["price"])
    change_pct = ((live_price - candle_open) / candle_open * 100) if candle_open else 0.0
    seconds_until_close = max(0, int((close_time - datetime.now(tz=UTC)).total_seconds()))

    return KronosLiveCandleResponse(
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        open=candle_open,
        high=candle_high,
        low=candle_low,
        close=candle_close,
        volume=candle_volume,
        live_price=live_price,
        change_pct=change_pct,
        seconds_until_close=seconds_until_close,
    )
