"""Timeframe enum and helpers for Kronos multi-TF predictions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum


class Timeframe(str, Enum):
    M15 = "15m"
    H1  = "1h"
    H4  = "4h"
    H8  = "8h"
    D1  = "1d"
    W1  = "1w"

    def to_binance_interval(self) -> str:
        return self.value

    def to_timedelta(self) -> timedelta:
        _map = {
            "15m": timedelta(minutes=15),
            "1h":  timedelta(hours=1),
            "4h":  timedelta(hours=4),
            "8h":  timedelta(hours=8),
            "1d":  timedelta(days=1),
            "1w":  timedelta(weeks=1),
        }
        return _map[self.value]

    def seconds_in_candle(self) -> int:
        return int(self.to_timedelta().total_seconds())

    def next_candle_boundary(self, now: datetime) -> datetime:
        """UTC open time of the next candle boundary after *now*."""
        now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        elapsed = int((now - epoch).total_seconds())
        period = self.seconds_in_candle()
        next_epoch = (elapsed // period + 1) * period
        return epoch + timedelta(seconds=next_epoch)

    def current_candle_boundary(self, now: datetime) -> datetime:
        """UTC open time of the currently-forming candle."""
        now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        elapsed = int((now - epoch).total_seconds())
        period = self.seconds_in_candle()
        current_epoch = (elapsed // period) * period
        return epoch + timedelta(seconds=current_epoch)

    def default_model_variant(self) -> str:
        return "base"

    def backtest_window_days(self) -> int:
        _map = {
            "15m": 180,
            "1h":  730,
            "4h":  1460,
            "8h":  1825,
            "1d":  3000,
            "1w":  3000,
        }
        return _map[self.value]

    def backtest_sample_size(self) -> int | None:
        """Number of random candles to sample for backtesting (None = all available)."""
        _map = {
            "15m": 500,
            "1h":  200,
            "4h":  200,
            "8h":  200,
            "1d":  200,
            "1w":  None,
        }
        return _map[self.value]
