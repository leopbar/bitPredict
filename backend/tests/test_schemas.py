"""Unit tests for Kline schema (8 tests: TC-13 to TC-20)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from bitpredict.data.schemas import Kline


class TestKlineSchema:
    """TC-13 to TC-20: Kline schema validation and parsing tests."""

    def test_kline_from_raw_12_elements(self) -> None:
        """TC-13: Parse raw array with 12 elements."""
        # Arrange
        raw = [
            1609459200000,      # open_time_ms
            "100.5",            # open
            "101.0",            # high
            "99.5",             # low
            "100.5",            # close
            "500.0",            # volume
            1609462800000,      # close_time_ms
            "50000.0",          # quote_volume
            10,                 # trades
            "100.0",            # taker_buy_base
            "10000.0",          # taker_buy_quote
            0,                  # ignore
        ]

        # Act
        kline = Kline.from_raw(raw)

        # Assert
        assert kline.open_time == datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert kline.close_time == datetime(2021, 1, 1, 1, 0, 0, tzinfo=UTC)
        assert kline.open == Decimal("100.5")
        assert kline.close == Decimal("100.5")
        assert kline.high == Decimal("101.0")
        assert kline.low == Decimal("99.5")
        assert kline.volume == Decimal("500.0")
        assert kline.quote_volume == Decimal("50000.0")
        assert kline.trades == 10
        assert kline.taker_buy_base == Decimal("100.0")
        assert kline.taker_buy_quote == Decimal("10000.0")

    def test_kline_parse_ms_timestamp_int(self) -> None:
        """TC-14: Int milliseconds → UTC datetime."""
        # Arrange
        raw = [
            1609459200000,
            "100.5",
            "101.0",
            "99.5",
            "100.5",
            "500.0",
            1609462800000,
            "50000.0",
            10,
            "100.0",
            "10000.0",
            0,
        ]

        # Act
        kline = Kline.from_raw(raw)

        # Assert
        assert kline.open_time.year == 2021
        assert kline.open_time.month == 1
        assert kline.open_time.day == 1
        assert kline.open_time.tzinfo == UTC

    def test_kline_parse_ms_timestamp_float(self) -> None:
        """TC-15: Float milliseconds → UTC datetime."""
        # Arrange
        raw = [
            1609459200000.5,    # float ms
            "100.5",
            "101.0",
            "99.5",
            "100.5",
            "500.0",
            1609462800000.5,    # float ms
            "50000.0",
            10,
            "100.0",
            "10000.0",
            0,
        ]

        # Act
        kline = Kline.from_raw(raw)

        # Assert
        assert isinstance(kline.open_time, datetime)
        assert kline.open_time.tzinfo == UTC

    def test_kline_parse_already_datetime(self) -> None:
        """TC-16: Datetime already UTC → passthrough."""
        # Arrange
        dt = datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        raw = [
            dt,                 # already datetime
            "100.5",
            "101.0",
            "99.5",
            "100.5",
            "500.0",
            dt,
            "50000.0",
            10,
            "100.0",
            "10000.0",
            0,
        ]

        # Act
        kline = Kline.from_raw(raw)

        # Assert
        assert kline.open_time == dt
        assert kline.close_time == dt

    def test_kline_decimal_precision(self) -> None:
        """TC-17: Decimal values preserve precision."""
        # Arrange
        raw = [
            1609459200000,
            "100.123456789",    # 9 decimal places
            "101.987654321",
            "99.555555555",
            "100.111111111",
            "500.0",
            1609462800000,
            "50000.0",
            10,
            "100.0",
            "10000.0",
            0,
        ]

        # Act
        kline = Kline.from_raw(raw)

        # Assert
        assert str(kline.open) == "100.123456789"
        assert str(kline.high) == "101.987654321"
        assert str(kline.low) == "99.555555555"

    def test_kline_trades_int_parsing(self) -> None:
        """TC-18: trades field parsed as int."""
        # Arrange
        raw = [
            1609459200000,
            "100.5",
            "101.0",
            "99.5",
            "100.5",
            "500.0",
            1609462800000,
            "50000.0",
            50,                 # trades as int
            "100.0",
            "10000.0",
            0,
        ]

        # Act
        kline = Kline.from_raw(raw)

        # Assert
        assert kline.trades == 50
        assert isinstance(kline.trades, int)

    def test_kline_timezone_all_datetimes_utc(self) -> None:
        """TC-19: All datetimes have UTC timezone."""
        # Arrange
        raw = [
            1609459200000,
            "100.5",
            "101.0",
            "99.5",
            "100.5",
            "500.0",
            1609462800000,
            "50000.0",
            10,
            "100.0",
            "10000.0",
            0,
        ]

        # Act
        kline = Kline.from_raw(raw)

        # Assert
        assert kline.open_time.tzinfo == UTC
        assert kline.close_time.tzinfo == UTC

    def test_kline_from_raw_too_few_elements(self) -> None:
        """TC-20: Array with < 12 elements raises IndexError."""
        # Arrange
        raw = [1609459200000, "100.5"]  # Only 2 elements

        # Act & Assert
        with pytest.raises((IndexError, ValueError)):
            Kline.from_raw(raw)
