"""Pydantic v2 request/response schemas for the bitPredict REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthStatus(BaseModel):
    status: str
    version: str = "1.0.0"


class ReadinessStatus(BaseModel):
    ready: bool
    checks: dict[str, str]


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------


class PredictionRequest(BaseModel):
    model_name: str = Field(default="ensemble", description="Model to use for inference")
    horizon_hours: int = Field(default=24, ge=1, le=168)


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    target_time: datetime
    model_version: str
    q10: float
    q50: float
    q90: float
    recommendation: str
    confidence: float
    actual_price: float | None = None


class PredictionListResponse(BaseModel):
    total: int
    items: list[PredictionResponse]


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------


class BacktestRequest(BaseModel):
    model_name: str = Field(default="ensemble")
    start: str = Field(description="ISO date string, e.g. 2024-01-01")
    end: str = Field(description="ISO date string, e.g. 2024-12-31")
    capital: float = Field(default=10_000.0, gt=0)
    risk: str = Field(default="moderate", pattern="^(conservative|moderate|aggressive)$")


class BacktestJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class BacktestStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float = 0.0
    message: str = ""


class BacktestResultResponse(BaseModel):
    job_id: str
    status: str
    metrics: dict[str, Any] | None = None
    error: str | None = None
    equity_curve: list[float] | None = None


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


class ParameterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any
    updated_at: datetime
    updated_by: str


class ParameterUpdate(BaseModel):
    value: Any
    updated_by: str = "api"


class ParametersBulkUpdate(BaseModel):
    parameters: dict[str, Any]
    updated_by: str = "api"


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class AlertCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    condition: dict[str, Any] = Field(description="Condition expression dict")
    channel: str = Field(default="email", pattern="^(email|webhook|dashboard)$")
    active: bool = True


class AlertUpdate(BaseModel):
    name: str | None = None
    condition: dict[str, Any] | None = None
    channel: str | None = None
    active: bool | None = None


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    condition_json: dict[str, Any]
    channel: str
    active: bool
    created_at: datetime
    last_triggered_at: datetime | None = None


# ---------------------------------------------------------------------------
# Klines / Market data
# ---------------------------------------------------------------------------


class KlineResponse(BaseModel):
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int


class KlineRangeResponse(BaseModel):
    symbol: str
    interval: str
    count: int
    items: list[KlineResponse]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ModelInfo(BaseModel):
    name: str
    active: bool
    metrics: dict[str, float] | None = None
    registered_at: str | None = None


class ModelsListResponse(BaseModel):
    active_model: str
    models: list[ModelInfo]


class ActivateModelResponse(BaseModel):
    model_name: str
    message: str


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    detail: str


class MessageResponse(BaseModel):
    message: str
