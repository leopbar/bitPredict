"""Gap detection in time-series kline data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl


_INTERVAL_DELTA: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
    "6h": timedelta(hours=6),
    "8h": timedelta(hours=8),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "1w": timedelta(weeks=1),
}


def detect_gaps(df: pl.DataFrame, interval: str = "1h") -> list[tuple[datetime, datetime]]:
    """Return a list of (gap_start, gap_end) tuples for missing candles.

    A gap is any pair of consecutive open_times whose difference is
    larger than one interval step.
    """
    delta = _INTERVAL_DELTA.get(interval)
    if delta is None:
        raise ValueError(f"Unknown interval '{interval}'. Supported: {list(_INTERVAL_DELTA)}")

    if len(df) == 0:
        return []

    # Use to_list() then sort in Python to avoid the Polars lazy-engine operations
    # on Datetime("us","UTC") columns (select_seq/collect) that crash on Windows
    # under pytest-cov in Polars 1.12. to_list() extracts directly without creating
    # intermediate Series.
    timestamps: list[datetime] = sorted(df["open_time"].to_list())

    gaps: list[tuple[datetime, datetime]] = []
    for prev, curr in zip(timestamps, timestamps[1:]):
        expected_next = prev + delta
        if curr > expected_next:
            gaps.append((expected_next, curr))

    return gaps


def gap_summary(gaps: list[tuple[datetime, datetime]], interval: str = "1h") -> dict[str, int]:
    """Return a dict with gap count and total missing candles."""
    delta = _INTERVAL_DELTA.get(interval, timedelta(hours=1))
    missing = sum(
        int((end - start) / delta)
        for start, end in gaps
    )
    return {"gap_count": len(gaps), "missing_candles": missing}
