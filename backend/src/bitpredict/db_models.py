"""SQLAlchemy 2.0 ORM models for bitPredict."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Kline(Base):
    """OHLCV candle data — becomes a TimescaleDB hypertable partitioned by open_time."""

    __tablename__ = "klines"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    interval: Mapped[str] = mapped_column("interval", String(10), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quote_volume: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    trades: Mapped[int] = mapped_column(Integer, nullable=False)
    taker_buy_base: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    taker_buy_quote: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)


class Parameter(Base):
    """Key/value store for dashboard configuration and system settings."""

    __tablename__ = "parameters"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_by: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="'system'"
    )


# ── Kronos predictions ────────────────────────────────────────────────────────

class KronosPrediction(Base):
    """Kronos stochastic forecast for one future candle (one row per prediction run)."""

    __tablename__ = "kronos_predictions"

    # Composite PK required by TimescaleDB (partition column must be part of PK)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    target_candle_open_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_candle_close_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Median of 30 stochastic samples
    predicted_open:   Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_high:   Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_low:    Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_close:  Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_volume: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Uncertainty band
    q10_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    q90_close: Mapped[float | None] = mapped_column(Float, nullable=True)

    # % of samples where predicted close > last actual close (0.0–1.0)
    prob_bullish: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Filled in after the candle closes
    actual_open:   Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_high:   Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_low:    Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_close:  Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_volume: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Accuracy metrics (filled post-close)
    direction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    close_error_pct:   Mapped[float | None] = mapped_column(Float, nullable=True)

    # Inference config snapshot
    model_variant:  Mapped[str | None] = mapped_column(String(20), nullable=True)
    sample_count:   Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature:    Mapped[float | None] = mapped_column(Float, nullable=True)
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Celery tracking
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status:  Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


# ── Kronos backtests ──────────────────────────────────────────────────────────

class KronosBacktest(Base):
    """Aggregated backtest run for one timeframe (one row per execution)."""

    __tablename__ = "kronos_backtests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_variant: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    directional_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    mape_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    mape_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    mape_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    mape_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    band_width_pct_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    band_calibration_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # High-confidence calibration: accuracy when prob_bullish >= 70% or <= 30%
    high_conf_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_conf_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sample_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sample_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Portfolio simulation parameters
    initial_capital:  Mapped[float | None] = mapped_column(Float, nullable=True)
    position_pct:     Mapped[float | None] = mapped_column(Float, nullable=True)
    compound:         Mapped[bool | None]  = mapped_column(Boolean, nullable=True)

    # Portfolio simulation results
    final_equity:           Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit:             Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit_pct:         Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor:          Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate_pct:           Mapped[float | None] = mapped_column(Float, nullable=True)
    payoff_ratio:           Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct:       Mapped[float | None] = mapped_column(Float, nullable=True)
    max_consecutive_losses: Mapped[int | None]   = mapped_column(Integer, nullable=True)
    recovery_factor:        Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_ratio:           Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_trade_pct:          Mapped[float | None] = mapped_column(Float, nullable=True)
    best_trade_pct:         Mapped[float | None] = mapped_column(Float, nullable=True)
    worst_trade_pct:        Mapped[float | None] = mapped_column(Float, nullable=True)
    total_trades:           Mapped[int | None]   = mapped_column(Integer, nullable=True)


# ── RSI-2 Strategy tables ─────────────────────────────────────────────────────

class FundingRate(Base):
    """Binance perpetual funding rate recorded every 8 hours."""

    __tablename__ = "funding_rates"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    funding_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    funding_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    mark_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, server_default="0")


class Rsi2Signal(Base):
    """Decision produced by the RSI-2 inference tick (long / short / none)."""

    __tablename__ = "rsi2_signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signal_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(5), nullable=False)  # long | short | none
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    rsi2_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    meta_proba: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    params_version: Mapped[str] = mapped_column(String(50), nullable=False, server_default="'A'")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Rsi2Trade(Base):
    """Completed RSI-2 trade (entry → exit) for PnL tracking."""

    __tablename__ = "rsi2_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    side: Mapped[str] = mapped_column(String(5), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    stop_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    gross_pnl_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    net_pnl_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    exit_reason: Mapped[str] = mapped_column(String(20), nullable=False)  # target|stop|timeout
    bars_held: Mapped[int] = mapped_column(Integer, nullable=False)
    params_version: Mapped[str] = mapped_column(String(50), nullable=False, server_default="'A'")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
