"""Unit tests for gap detection (10 tests: TC-35 to TC-44)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from bitpredict.data.gaps import detect_gaps, gap_summary


def _make_df(timestamps: list[datetime]) -> pl.DataFrame:
    """Helper: Create DataFrame with open_time column.

    Passes epoch-microseconds as Int64 with explicit timezone dtype to avoid
    the Windows Polars crash triggered by replace_time_zone() or the dict
    constructor with Python tz-aware datetime lists.
    """
    epoch_us = [int(ts.timestamp() * 1_000_000) for ts in timestamps]
    return pl.Series("open_time", epoch_us, dtype=pl.Datetime("us", "UTC")).to_frame()


def _hourly(start: datetime, count: int) -> list[datetime]:
    """Helper: Generate hourly timestamps."""
    return [start + timedelta(hours=i) for i in range(count)]


START = datetime(2024, 1, 1, tzinfo=UTC)


class TestGapDetection:
    """TC-35 to TC-44: Gap detection tests."""

    def test_detect_gaps_no_gaps_complete_series(self) -> None:
        """TC-35: Complete series without gaps."""
        # Arrange
        df = _make_df(_hourly(START, 24))

        # Act
        gaps = detect_gaps(df, "1h")

        # Assert
        assert gaps == []

    def test_detect_gaps_single_gap(self) -> None:
        """TC-36: Single gap detected."""
        # Arrange
        timestamps = _hourly(START, 10) + _hourly(START + timedelta(hours=12), 10)
        df = _make_df(timestamps)

        # Act
        gaps = detect_gaps(df, "1h")

        # Assert
        assert len(gaps) == 1
        gap_start, gap_end = gaps[0]
        assert gap_start == START + timedelta(hours=10)
        assert gap_end == START + timedelta(hours=12)

    def test_detect_gaps_multiple_gaps(self) -> None:
        """TC-37: Multiple gaps detected."""
        # Arrange
        part1 = _hourly(START, 5)
        part2 = _hourly(START + timedelta(hours=10), 5)
        part3 = _hourly(START + timedelta(hours=20), 5)
        df = _make_df(part1 + part2 + part3)

        # Act
        gaps = detect_gaps(df, "1h")

        # Assert
        assert len(gaps) == 2

    def test_detect_gaps_empty_dataframe(self) -> None:
        """TC-38: Empty DataFrame returns no gaps."""
        # Arrange
        df = pl.DataFrame({"open_time": []}, schema={"open_time": pl.Datetime("us", "UTC")})

        # Act
        gaps = detect_gaps(df, "1h")

        # Assert
        assert gaps == []

    def test_detect_gaps_single_row(self) -> None:
        """TC-39: Single row returns no gaps."""
        # Arrange
        df = _make_df([START])

        # Act
        gaps = detect_gaps(df, "1h")

        # Assert
        assert gaps == []

    @pytest.mark.parametrize("interval,delta_hours", [
        ("1m", 1/60),
        ("5m", 5/60),
        ("1h", 1),
        ("4h", 4),
        ("1d", 24),
    ])
    def test_detect_gaps_all_interval_types(self, interval: str, delta_hours: float) -> None:
        """TC-40: Gap detection works for all interval types."""
        # Arrange
        delta = timedelta(hours=delta_hours)
        timestamps = [START, START + delta, START + delta * 3]  # Gap at position 2
        df = _make_df(timestamps)

        # Act
        gaps = detect_gaps(df, interval)

        # Assert
        assert len(gaps) == 1

    def test_detect_gaps_invalid_interval(self) -> None:
        """TC-41: Invalid interval raises ValueError."""
        # Arrange
        df = _make_df(_hourly(START, 5))

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown interval"):
            detect_gaps(df, "99x")

    def test_gap_summary_gap_count_correct(self) -> None:
        """TC-42: gap_summary returns correct gap count."""
        # Arrange
        timestamps = _hourly(START, 5) + _hourly(START + timedelta(hours=8), 5)
        df = _make_df(timestamps)
        gaps = detect_gaps(df, "1h")

        # Act
        summary = gap_summary(gaps, "1h")

        # Assert
        assert summary["gap_count"] == 1

    def test_gap_summary_missing_candles_count(self) -> None:
        """TC-43: gap_summary calculates missing candles correctly."""
        # Arrange
        timestamps = _hourly(START, 5) + _hourly(START + timedelta(hours=8), 5)
        df = _make_df(timestamps)
        gaps = detect_gaps(df, "1h")

        # Act
        summary = gap_summary(gaps, "1h")

        # Assert
        assert summary["missing_candles"] == 3  # hours 5, 6, 7

    def test_gap_summary_empty_gaps_list(self) -> None:
        """TC-44: gap_summary with empty gaps."""
        # Arrange
        gaps = []

        # Act
        summary = gap_summary(gaps, "1h")

        # Assert
        assert summary["gap_count"] == 0
        assert summary["missing_candles"] == 0
