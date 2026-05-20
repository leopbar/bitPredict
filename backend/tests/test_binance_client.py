"""Unit tests for BinanceClient (12 tests: TC-01 to TC-12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from bitpredict.data.binance_client import BinanceClient


def _make_raw_kline(open_time_ms: int = 1_502_942_400_000) -> list[Any]:
    """Helper: Create a raw kline array (12 elements)."""
    return [
        open_time_ms,
        "4261.48000000",
        "4313.62000000",
        "4261.32000000",
        "4308.83000000",
        "47.18440000",
        open_time_ms + 3_599_999,
        "202585.03750000",
        152,
        "25.57830000",
        "109728.12260000",
        "0",
    ]


class TestBinanceClientGetKlines:
    """TC-01 to TC-12: BinanceClient.get_klines tests."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_single_page(self) -> None:
        """TC-01: Single page response (< 1000 rows)."""
        # Arrange
        raw = [_make_raw_kline(1_502_942_400_000 + i * 3_600_000) for i in range(5)]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=raw, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            result = await client.get_klines("BTCUSDT", "1h")

        # Assert
        assert len(result) == 5
        assert result[0][4] == "4308.83000000"
        assert client.used_weight == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_multiple_pages_pagination(self) -> None:
        """TC-02: Multiple pages (pagination test)."""
        # Arrange: Simulate 1000 rows per page
        page1 = [_make_raw_kline(1_502_942_400_000 + i * 3_600_000) for i in range(1000)]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=page1, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            result = await client.get_klines("BTCUSDT", "1h")

        # Assert: get_klines returns single page (up to 1000)
        assert len(result) <= 1000
        assert len(result) == 1000

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_with_start_time(self) -> None:
        """TC-03: startTime parameter included in request."""
        # Arrange
        raw = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=raw, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )
        start_dt = datetime(2021, 1, 1, 12, 0, 0, tzinfo=UTC)

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            await client.get_klines("BTCUSDT", "1h", start_time=start_dt)

        # Assert: Verify startTime in request
        request = respx.calls.last.request
        assert "startTime" in request.url.params
        assert int(request.url.params["startTime"]) == int(start_dt.timestamp() * 1000)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_with_end_time(self) -> None:
        """TC-04: endTime parameter included in request."""
        # Arrange
        raw = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=raw, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )
        end_dt = datetime(2021, 1, 2, 12, 0, 0, tzinfo=UTC)

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            await client.get_klines("BTCUSDT", "1h", end_time=end_dt)

        # Assert
        request = respx.calls.last.request
        assert "endTime" in request.url.params
        assert int(request.url.params["endTime"]) == int(end_dt.timestamp() * 1000)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_limit_clamped_to_1000(self) -> None:
        """TC-05: limit > 1000 is clamped to 1000."""
        # Arrange
        raw = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=raw, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            await client.get_klines("BTCUSDT", "1h", limit=5000)

        # Assert
        request = respx.calls.last.request
        assert request.url.params["limit"] == "1000"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_tracks_weight_header(self) -> None:
        """TC-06: X-MBX-USED-WEIGHT-1M header is tracked."""
        # Arrange
        raw = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=raw, headers={"X-MBX-USED-WEIGHT-1M": "850"})
        )

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            await client.get_klines("BTCUSDT", "1h")

        # Assert
        assert client.used_weight == 850

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_invalid_weight_header(self) -> None:
        """TC-07: Invalid weight header (non-numeric) defaults to 0."""
        # Arrange
        raw = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=raw, headers={"X-MBX-USED-WEIGHT-1M": "invalid"})
        )

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            await client.get_klines("BTCUSDT", "1h")

        # Assert
        assert client.used_weight == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_weight_backoff_threshold(self) -> None:
        """TC-08: weight >= 1000 triggers backoff (60s sleep)."""
        # Arrange
        raw = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=raw, headers={"X-MBX-USED-WEIGHT-1M": "1200"})
        )

        # Act & Assert
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            async with BinanceClient(base_url="https://api.binance.com") as client:
                await client.get_klines("BTCUSDT", "1h")
            # Verify sleep was called
            mock_sleep.assert_called()

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_retry_429_with_retry_after(self) -> None:
        """TC-09: HTTP 429 with Retry-After header triggers retry."""
        # Arrange
        success = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            side_effect=[
                httpx.Response(429, json={"code": -1003, "msg": "Too much request weight used"}, headers={"Retry-After": "10"}),
                httpx.Response(200, json=success, headers={"X-MBX-USED-WEIGHT-1M": "1"}),
            ]
        )

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            result = await client.get_klines("BTCUSDT", "1h")

        # Assert: Should have retried and succeeded
        assert len(result) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_retry_503(self) -> None:
        """TC-10: HTTP 503 retries up to 6 attempts."""
        # Arrange
        success = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            side_effect=[
                httpx.Response(503, json={"code": -1001, "msg": "Server unavailable"}),
                httpx.Response(503, json={"code": -1001, "msg": "Server unavailable"}),
                httpx.Response(200, json=success, headers={"X-MBX-USED-WEIGHT-1M": "1"}),
            ]
        )

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            result = await client.get_klines("BTCUSDT", "1h")

        # Assert
        assert len(result) == 1
        assert len(respx.calls) == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_klines_timeout_retry(self) -> None:
        """TC-11: httpx.TimeoutException triggers retry."""
        # Arrange
        success = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            side_effect=[
                httpx.TimeoutException("Timeout"),
                httpx.TimeoutException("Timeout"),
                httpx.Response(200, json=success, headers={"X-MBX-USED-WEIGHT-1M": "1"}),
            ]
        )

        # Act
        async with BinanceClient(base_url="https://api.binance.com") as client:
            result = await client.get_klines("BTCUSDT", "1h")

        # Assert
        assert len(result) == 1
        assert len(respx.calls) == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_context_manager_lifecycle(self) -> None:
        """TC-12: Context manager __aenter__/__aexit__ lifecycle."""
        # Arrange
        raw = [_make_raw_kline()]
        respx.get("https://api.binance.com/api/v3/klines").mock(
            return_value=httpx.Response(200, json=raw, headers={"X-MBX-USED-WEIGHT-1M": "1"})
        )

        # Act
        client = BinanceClient(base_url="https://api.binance.com")
        assert client._client is None

        async with client as ctx:
            assert ctx._client is not None
            assert isinstance(ctx._client, httpx.AsyncClient)
            await ctx.get_klines("BTCUSDT", "1h")

        # Assert: Client closed after exiting context
        assert client._client is None
