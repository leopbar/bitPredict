"""Parameter CRUD endpoints: dashboard configuration key/value store."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from bitpredict.api.auth import require_api_key
from bitpredict.api.dependencies import get_db
from bitpredict.api.schemas import MessageResponse, ParameterResponse, ParametersBulkUpdate, ParameterUpdate
from bitpredict.db_models import Parameter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/parameters", tags=["Parameters"])

_DEFAULT_PARAMETERS: dict[str, Any] = {
    "history_days": 90,
    "risk_level": "moderate",
    "confidence_threshold": 0.6,
    "active_model": "ensemble",
    "selected_features": ["rsi_14", "macd", "sma_21", "bollinger_upper", "bollinger_lower"],
    "alert_email": "",
    "report_frequency": "daily",
    "auto_reports": False,
}


def _to_response(p: Parameter) -> ParameterResponse:
    return ParameterResponse(
        key=p.key,
        value=p.value_json.get("v") if isinstance(p.value_json, dict) and "v" in p.value_json else p.value_json,
        updated_at=p.updated_at,
        updated_by=p.updated_by,
    )


def _ensure_defaults(db: Session) -> None:
    """Seed default parameters if the table is empty."""
    count = db.execute(select(Parameter)).scalars().first()
    if count is None:
        for key, val in _DEFAULT_PARAMETERS.items():
            db.add(Parameter(key=key, value_json={"v": val}, updated_by="system"))
        db.commit()


@router.get(
    "",
    response_model=list[ParameterResponse],
    summary="List all configuration parameters",
    dependencies=[Depends(require_api_key)],
)
def list_parameters(db: Session = Depends(get_db)) -> list[ParameterResponse]:
    _ensure_defaults(db)
    rows = db.execute(select(Parameter).order_by(Parameter.key)).scalars().all()
    return [_to_response(r) for r in rows]


@router.get(
    "/{key}",
    response_model=ParameterResponse,
    summary="Get a single parameter by key",
    dependencies=[Depends(require_api_key)],
)
def get_parameter(key: str, db: Session = Depends(get_db)) -> ParameterResponse:
    _ensure_defaults(db)
    param = db.get(Parameter, key)
    if param is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parameter '{key}' not found")
    return _to_response(param)


@router.put(
    "/{key}",
    response_model=ParameterResponse,
    summary="Create or update a parameter",
    dependencies=[Depends(require_api_key)],
)
def upsert_parameter(
    key: str,
    body: ParameterUpdate,
    db: Session = Depends(get_db),
) -> ParameterResponse:
    param = db.get(Parameter, key)
    if param is None:
        param = Parameter(key=key, value_json={"v": body.value}, updated_by=body.updated_by)
        db.add(param)
    else:
        param.value_json = {"v": body.value}
        param.updated_by = body.updated_by
        param.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(param)
    return _to_response(param)


@router.put(
    "",
    response_model=MessageResponse,
    summary="Bulk update multiple parameters",
    dependencies=[Depends(require_api_key)],
)
def bulk_update_parameters(
    body: ParametersBulkUpdate,
    db: Session = Depends(get_db),
) -> MessageResponse:
    now = datetime.now(tz=timezone.utc)
    for key, val in body.parameters.items():
        param = db.get(Parameter, key)
        if param is None:
            param = Parameter(key=key, value_json={"v": val}, updated_by=body.updated_by)
            db.add(param)
        else:
            param.value_json = {"v": val}
            param.updated_by = body.updated_by
            param.updated_at = now
    db.commit()
    return MessageResponse(message=f"Updated {len(body.parameters)} parameter(s)")
