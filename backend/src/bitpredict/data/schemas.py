"""Pydantic schemas for Binance API responses."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator


class Kline(BaseModel):
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime
    quote_volume: Decimal
    trades: int
    taker_buy_base: Decimal
    taker_buy_quote: Decimal

    @field_validator("open_time", "close_time", mode="before")
    @classmethod
    def parse_ms_timestamp(cls, v: Any) -> datetime:
        if isinstance(v, int | float):
            return datetime.fromtimestamp(v / 1000, tz=UTC)
        return v  # type: ignore[return-value]

    @classmethod
    def from_raw(cls, row: list[Any]) -> "Kline":
        """Parse a raw Binance kline array (12 elements)."""
        return cls(
            open_time=row[0],
            open=row[1],
            high=row[2],
            low=row[3],
            close=row[4],
            volume=row[5],
            close_time=row[6],
            quote_volume=row[7],
            trades=row[8],
            taker_buy_base=row[9],
            taker_buy_quote=row[10],
        )
