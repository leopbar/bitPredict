"""Pydantic config for RSI-2 strategy parameters."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Rsi2Params(BaseModel):
    """Full parameter set for the RSI-2 strategy (Caminho A outcome)."""

    # Fixed (not optimized)
    rsi_period: int = 2
    rsi_long_threshold: float = 10.0
    rsi_short_threshold: float = 90.0
    rsi_exit_long: float = 70.0
    rsi_exit_short: float = 30.0

    # Optimized — entry confirmation
    body_min_pct: float = Field(default=0.1, ge=0.0, le=5.0)
    close_pos_min: float = Field(default=0.5, ge=0.0, le=1.0)

    # Optimized — stop
    stop_type: str = Field(default="structural", pattern="^(structural|atr)$")
    stop_lookback: int = Field(default=10, ge=3, le=100)
    atr_k: float = Field(default=2.0, ge=0.5, le=5.0)

    # Optimized — exit timeout (0 = disabled)
    timeout_bars: int = Field(default=0, ge=0)

    # Optimized — profit target (0 = RSI-based exit; >0 = price target at N × stop distance)
    target_r_multiple: float = Field(default=0.0, ge=0.0, le=4.0)

    # Costs (fixed) — assuming limit/maker orders for entry and stop-limit exits
    fee_pct: float = 0.0001       # 0.01% per side (maker tier on Binance Futures)
    slippage_normal_pct: float = 0.0001   # 0.01% on limit entries/exits
    slippage_stop_pct: float = 0.0003     # 0.03% on stop-limit hits (partial fill slippage)
    funding_interval_hours: int = 8


class Rsi2MetaParams(BaseModel):
    """Meta-labeling Caminho B configuration."""

    min_proba_threshold: float = Field(default=0.55, ge=0.5, le=0.95)
    n_estimators: int = 300
    max_depth: int = 4
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    embargo_bars: int = 10
    n_folds: int = 5
