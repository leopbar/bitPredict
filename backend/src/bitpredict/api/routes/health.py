"""Health and readiness endpoints."""

from __future__ import annotations

from pathlib import Path

import redis as _redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from bitpredict.api.dependencies import get_db
from bitpredict.api.schemas import HealthStatus, ReadinessStatus
from bitpredict.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthStatus, summary="Liveness probe")
def health() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/ready", response_model=ReadinessStatus, summary="Readiness probe")
def ready(db: Session = Depends(get_db)) -> ReadinessStatus:
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    try:
        settings = get_settings()
        r = _redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    kronos_path = Path("/app/data/kronos")
    checks["kronos_model"] = "ok" if kronos_path.exists() else "not found"

    ready = all(v == "ok" for v in checks.values())
    return ReadinessStatus(ready=ready, checks=checks)
