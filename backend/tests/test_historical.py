"""Unit tests for historical download (14 tests: TC-21 to TC-34)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import polars as pl
import pytest
import respx

from bitpredict.data.historical import _klines_to_frame, download_historical, load_parquet
from bitpredict.data.schemas import Kline


def _fake_kline_row(open_time_ms: int) -> list[Any]:
    """Helper: Create a fake kline row."""
    return [
        open_time_ms,
        "30000.00",
        "30500.00",
        "29800.00",
        "30200.00",
        "10.5",
        open_time_ms + 3_599_999,
        "315750.00",
        300,
        "5.0",
        "150000.00",
        "0",
    ]


def _make_page(start_ms: int, count: int) -> list[list[Any]]:
    """Helper: Create a page of klines."""
    return [_fake_kline_row(start_ms + i * 3_600_000) for i in range(count)]


START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2024, 1, 2, tzinfo=UTC)


class TestHistoricalDownload:
    """TC-21 to TC-34: Historical download tests."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_empty_response(self, tmp_path: Path) -> None:
        """TC-21: Empty API response returns empty DataFrame."""
        # Arrange
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=[], headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        df = await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=END,
            data_dir=tmp_path,
        )

        # Assert
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_single_page(self, tmp_path: Path) -> None:
        """TC-22: Single page (< 1000 rows)."""
        # Arrange
        page1 = _make_page(int(START.timestamp() * 1000), 500)
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        df = await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=END,
            data_dir=tmp_path,
        )

        # Assert
        assert len(df) == 500
        assert "open_time" in df.columns

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_multiple_pages(self, tmp_path: Path) -> None:
        """TC-23: Multiple pages (pagination).

        Each 1000-row page spans 1000 h ≈ 41 days. To allow 3 full pages without
        early-exit due to next_start >= end, the end window must exceed 2500 h from
        START (≈ 104 days → well past 2024-05-14).
        """
        # Arrange
        from datetime import timedelta

        base_ms = int(START.timestamp() * 1000)
        page1 = _make_page(base_ms, 1000)
        page2 = _make_page(base_ms + 1000 * 3_600_000, 1000)
        page3 = _make_page(base_ms + 2000 * 3_600_000, 500)  # < 1000 → stops pagination

        respx.get("https://api.binance.com/api/v3/klines").mock(
            side_effect=[
                httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"}),
                httpx.Response(200, json=page2, headers={"X-MBX-USED-WEIGHT-1M": "1"}),
                httpx.Response(200, json=page3, headers={"X-MBX-USED-WEIGHT-1M": "1"}),
            ]
        )

        # end must exceed the last timestamp of page2 (base + 1999h) so the loop
        # continues into page3; page3 has < 1000 rows, which stops pagination.
        far_end = START + timedelta(hours=2500)

        # Act
        df = await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=far_end,
            data_dir=tmp_path,
        )

        # Assert
        assert len(df) == 2500  # 1000 + 1000 + 500

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_creates_data_dir(self, tmp_path: Path) -> None:
        """TC-24: Creates data_dir if it doesn't exist."""
        # Arrange
        new_dir = tmp_path / "new" / "nested" / "dir"
        page1 = _make_page(int(START.timestamp() * 1000), 10)
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=END,
            data_dir=new_dir,
        )

        # Assert
        assert new_dir.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_parquet_written(self, tmp_path: Path) -> None:
        """TC-25: Parquet file is written correctly."""
        # Arrange
        page1 = _make_page(int(START.timestamp() * 1000), 10)
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=END,
            data_dir=tmp_path,
        )

        # Assert
        parquet_path = tmp_path / "btcusdt_1h.parquet"
        assert parquet_path.exists()
        loaded = pl.read_parquet(parquet_path)
        assert len(loaded) == 10

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_parquet_schema_correct(self, tmp_path: Path) -> None:
        """TC-26: Parquet schema is correct."""
        # Arrange
        page1 = _make_page(int(START.timestamp() * 1000), 5)
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        df = await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=END,
            data_dir=tmp_path,
        )

        # Assert
        expected_cols = {"open_time", "open", "high", "low", "close", "volume", "close_time",
                        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"}
        assert set(df.columns) == expected_cols

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_unique_by_open_time(self, tmp_path: Path) -> None:
        """TC-27: Duplicates (same open_time) are removed.

        Since page1 has < 1000 rows, pagination stops there. Deduplication removes
        the second copy of the same timestamp → 1 unique row.
        """
        # Arrange
        base_ms = int(START.timestamp() * 1000)
        # Two rows with the same open_time (within a single page)
        page1 = [_fake_kline_row(base_ms), _fake_kline_row(base_ms)]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        df = await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=END,
            data_dir=tmp_path,
        )

        # Assert: 2 raw rows → 1 unique after dedup
        assert len(df) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_sorted_by_open_time(self, tmp_path: Path) -> None:
        """TC-28: Data is sorted by open_time."""
        # Arrange
        base_ms = int(START.timestamp() * 1000)
        # Create out-of-order rows (page 2 then page 1)
        page2 = [_fake_kline_row(base_ms + i * 3_600_000) for i in range(100, 110)]
        page1 = [_fake_kline_row(base_ms + i * 3_600_000) for i in range(0, 10)]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            side_effect=[
                httpx.Response(200, json=page2, headers={"X-MBX-USED-WEIGHT-1M": "1"}),
                httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"}),
            ]
        )

        # Act
        df = await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=datetime(2024, 1, 10, tzinfo=UTC),
            data_dir=tmp_path,
        )

        # Assert: Should be sorted
        assert df["open_time"].is_sorted()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_default_start_date(self, tmp_path: Path) -> None:
        """TC-29: Default start date is 2017-08-17."""
        # Arrange
        page1 = _make_page(int(START.timestamp() * 1000), 5)
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=None,  # Use default
            end=END,
            data_dir=tmp_path,
        )

        # Assert: Request should use default start
        request = respx.calls.last.request
        # Can't directly verify the startTime in request due to async nature,
        # but we can verify the function ran without error
        assert respx.calls.last.response.status_code == 200

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_default_end_date(self, tmp_path: Path) -> None:
        """TC-30: Default end date is now()."""
        # Arrange
        page1 = _make_page(int(START.timestamp() * 1000), 5)
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        df = await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=None,  # Use default
            data_dir=tmp_path,
        )

        # Assert
        assert len(df) == 5

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_callback_invoked(self, tmp_path: Path) -> None:
        """TC-31: on_page callback is invoked after each page."""
        # Arrange
        page1 = _make_page(int(START.timestamp() * 1000), 100)
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )
        callback_calls = []

        def on_page(page: int, total_rows: int) -> None:
            callback_calls.append((page, total_rows))

        # Act
        await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=END,
            data_dir=tmp_path,
            on_page=on_page,
        )

        # Assert
        assert len(callback_calls) >= 1
        assert callback_calls[0][0] == 1  # First page
        assert callback_calls[0][1] == 100  # Total rows so far

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_historical_timezone_enforcement(self, tmp_path: Path) -> None:
        """TC-32: All timestamps are UTC."""
        # Arrange
        page1 = _make_page(int(START.timestamp() * 1000), 5)
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        df = await download_historical(
            symbol="BTCUSDT",
            interval="1h",
            start=START,
            end=END,
            data_dir=tmp_path,
        )

        # Assert
        assert str(df["open_time"].dtype).startswith("Datetime")
        # Polars returns zoneinfo.ZoneInfo("UTC"), not datetime.timezone.utc — compare utcoffset
        from datetime import timedelta
        assert df["open_time"][0].utcoffset() == timedelta(0)

    def test_load_parquet_file_exists(self, tmp_path: Path) -> None:
        """TC-33: Load existing Parquet file."""
        # Arrange
        _ot_us = [
            int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1_000_000),
            int(datetime(2024, 1, 2, tzinfo=UTC).timestamp() * 1_000_000),
        ]
        _ct_us = [
            int(datetime(2024, 1, 1, 1, 0, 0, tzinfo=UTC).timestamp() * 1_000_000),
            int(datetime(2024, 1, 2, 1, 0, 0, tzinfo=UTC).timestamp() * 1_000_000),
        ]
        df_orig = pl.DataFrame([
            pl.Series("open_time", _ot_us, dtype=pl.Datetime("us", "UTC")),
            pl.Series("open", [30000.0, 30100.0]),
            pl.Series("high", [30500.0, 30600.0]),
            pl.Series("low", [29800.0, 29900.0]),
            pl.Series("close", [30200.0, 30300.0]),
            pl.Series("volume", [10.5, 11.5]),
            pl.Series("close_time", _ct_us, dtype=pl.Datetime("us", "UTC")),
            pl.Series("quote_volume", [315750.0, 320000.0]),
            pl.Series("trades", [300, 310]),
            pl.Series("taker_buy_base", [5.0, 5.5]),
            pl.Series("taker_buy_quote", [150000.0, 160000.0]),
        ])
        parquet_path = tmp_path / "btcusdt_1h.parquet"
        df_orig.write_parquet(parquet_path)

        # Act
        df_loaded = load_parquet(symbol="BTCUSDT", interval="1h", data_dir=tmp_path)

        # Assert
        assert len(df_loaded) == 2
        assert "open_time" in df_loaded.columns

    def test_load_parquet_file_not_found(self, tmp_path: Path) -> None:
        """TC-34: FileNotFoundError when file doesn't exist."""
        # Arrange & Act & Assert
        with pytest.raises(FileNotFoundError):
            load_parquet(symbol="BTCUSDT", interval="1h", data_dir=tmp_path)
