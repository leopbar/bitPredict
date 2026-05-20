"""Global test fixtures and mock data for bitPredict test suite."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, AsyncGenerator

import httpx
import polars as pl
import pytest
from unittest.mock import AsyncMock, MagicMock

from bitpredict.data.schemas import Kline
from bitpredict.data.streaming import KlineEvent


# ============================================================================
# TIMESTAMP & DATE FIXTURES
# ============================================================================


@pytest.fixture
def utc_now() -> datetime:
    """Current datetime in UTC."""
    return datetime.now(timezone.utc)


@pytest.fixture
def base_timestamp() -> int:
    """Base timestamp in milliseconds (2021-01-01 00:00:00 UTC)."""
    return 1609459200000


@pytest.fixture
def base_datetime() -> datetime:
    """Base datetime (2021-01-01 00:00:00 UTC)."""
    return datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


# ============================================================================
# KLINE DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_kline_raw() -> list:
    """Raw kline array from Binance API (12 elements)."""
    return [
        1609459200000,  # open_time_ms
        "100.5",        # open
        "101.0",        # high
        "99.5",         # low
        "100.5",        # close
        "500.0",        # volume
        1609462800000,  # close_time_ms
        "50000.0",      # quote_volume
        10,             # trades
        "100.0",        # taker_buy_base
        "10000.0",      # taker_buy_quote
        0,              # ignore
    ]


@pytest.fixture
def sample_kline(sample_kline_raw) -> Kline:
    """Valid Kline object."""
    return Kline.from_raw(sample_kline_raw)


@pytest.fixture
def sample_kline_raw_with_float_ms() -> list:
    """Raw kline with float milliseconds."""
    return [
        1609459200000.5,  # open_time_ms (float)
        "100.5",
        "101.0",
        "99.5",
        "100.5",
        "500.0",
        1609462800000.5,  # close_time_ms (float)
        "50000.0",
        10,
        "100.0",
        "10000.0",
        0,
    ]


@pytest.fixture
def sample_kline_raw_too_few_elements() -> list:
    """Raw kline with too few elements (should fail)."""
    return [1609459200000, "100.5"]


@pytest.fixture
def multiple_klines_raw() -> list:
    """Multiple raw klines for pagination tests."""
    klines = []
    base_ms = 1609459200000
    for i in range(3):
        open_price = 100.5 + (i * 0.1)
        klines.append([
            base_ms + (i * 3600000),     # open_time_ms
            f"{open_price}",              # open
            f"{open_price + 0.5}",        # high
            f"{open_price - 0.5}",        # low
            f"{open_price}",              # close
            "500.0",                      # volume
            base_ms + ((i + 1) * 3600000),# close_time_ms
            "50000.0",                    # quote_volume
            10,                           # trades
            "100.0",                      # taker_buy_base
            "10000.0",                    # taker_buy_quote
            0,                            # ignore
        ])
    return klines


# ============================================================================
# DATAFRAME FIXTURES
# ============================================================================


@pytest.fixture
def sample_dataframe_100_rows() -> pl.DataFrame:
    """Polars DataFrame with 100 klines."""
    base_ms = 1609459200000
    rows = []
    for i in range(100):
        open_price = 100.0 + (i * 0.1)
        rows.append({
            "open_time": datetime.fromtimestamp(base_ms / 1000 + i * 3600, tz=timezone.utc),
            "open": Decimal(f"{open_price}"),
            "high": Decimal(f"{open_price + 0.5}"),
            "low": Decimal(f"{open_price - 0.5}"),
            "close": Decimal(f"{open_price}"),
            "volume": Decimal("500.0"),
            "close_time": datetime.fromtimestamp(base_ms / 1000 + (i + 1) * 3600, tz=timezone.utc),
            "quote_volume": Decimal("50000.0"),
            "trades": 10,
            "taker_buy_base": Decimal("100.0"),
            "taker_buy_quote": Decimal("10000.0"),
        })
    return pl.DataFrame(rows)


@pytest.fixture
def sample_dataframe_with_gaps() -> pl.DataFrame:
    """Polars DataFrame with intentional gaps."""
    base_ms = 1609459200000
    rows = []
    indices = [0, 1, 2, 3, 4, 10, 11, 12, 20, 21]  # Gaps at 5-9 and 13-19
    for idx in indices:
        open_price = 100.0 + (idx * 0.1)
        rows.append({
            "open_time": datetime.fromtimestamp(base_ms / 1000 + idx * 3600, tz=timezone.utc),
            "open": Decimal(f"{open_price}"),
            "high": Decimal(f"{open_price + 0.5}"),
            "low": Decimal(f"{open_price - 0.5}"),
            "close": Decimal(f"{open_price}"),
            "volume": Decimal("500.0"),
            "close_time": datetime.fromtimestamp(base_ms / 1000 + (idx + 1) * 3600, tz=timezone.utc),
            "quote_volume": Decimal("50000.0"),
            "trades": 10,
            "taker_buy_base": Decimal("100.0"),
            "taker_buy_quote": Decimal("10000.0"),
        })
    return pl.DataFrame(rows)


@pytest.fixture
def sample_dataframe_empty() -> pl.DataFrame:
    """Empty Polars DataFrame with correct schema."""
    return pl.DataFrame({
        "open_time": [],
        "open": [],
        "high": [],
        "low": [],
        "close": [],
        "volume": [],
        "close_time": [],
        "quote_volume": [],
        "trades": [],
        "taker_buy_base": [],
        "taker_buy_quote": [],
    }).with_columns([
        pl.col("open").cast(pl.Float64),
        pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64),
        pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
        pl.col("quote_volume").cast(pl.Float64),
        pl.col("trades").cast(pl.Int32),
        pl.col("taker_buy_base").cast(pl.Float64),
        pl.col("taker_buy_quote").cast(pl.Float64),
    ])


@pytest.fixture
def sample_dataframe_single_row(sample_kline) -> pl.DataFrame:
    """Polars DataFrame with single kline."""
    return pl.DataFrame({
        "open_time": [sample_kline.open_time],
        "open": [sample_kline.open],
        "high": [sample_kline.high],
        "low": [sample_kline.low],
        "close": [sample_kline.close],
        "volume": [sample_kline.volume],
        "close_time": [sample_kline.close_time],
        "quote_volume": [sample_kline.quote_volume],
        "trades": [sample_kline.trades],
        "taker_buy_base": [sample_kline.taker_buy_base],
        "taker_buy_quote": [sample_kline.taker_buy_quote],
    })


# ============================================================================
# BINANCE API RESPONSE FIXTURES
# ============================================================================


@pytest.fixture
def mock_binance_single_page_response() -> list:
    """Mock response from Binance /klines endpoint (single page)."""
    return [
        [1609459200000, "100.5", "101.0", "99.5", "100.5", "500.0", 1609462800000, "50000.0", 10, "100.0", "10000.0", 0],
        [1609462800000, "100.6", "101.1", "99.6", "100.6", "510.0", 1609466400000, "50100.0", 11, "101.0", "10100.0", 0],
    ]


@pytest.fixture
def mock_binance_empty_response() -> list:
    """Mock empty response from Binance API."""
    return []


@pytest.fixture
def mock_binance_response_1000_rows() -> list:
    """Mock response with exactly 1000 rows."""
    base_ms = 1609459200000
    rows = []
    for i in range(1000):
        open_price = 100.0 + (i * 0.01)
        rows.append([
            base_ms + (i * 3600000),
            f"{open_price}",
            f"{open_price + 0.5}",
            f"{open_price - 0.5}",
            f"{open_price}",
            "500.0",
            base_ms + ((i + 1) * 3600000),
            "50000.0",
            10,
            "100.0",
            "10000.0",
            0,
        ])
    return rows


# ============================================================================
# WEBSOCKET MESSAGE FIXTURES
# ============================================================================


@pytest.fixture
def sample_websocket_kline_message() -> dict:
    """Mock WebSocket kline event message."""
    base_ms = 1609459200000
    return {
        "e": "kline",
        "E": base_ms,
        "s": "BTCUSDT",
        "k": {
            "t": base_ms,
            "T": base_ms + 3600000,
            "s": "BTCUSDT",
            "i": "1h",
            "f": 100,
            "L": 200,
            "o": "100.5",
            "c": "100.5",
            "h": "101.0",
            "l": "99.5",
            "v": "500.0",
            "q": "50000.0",
            "n": 10,
            "V": "100.0",
            "Q": "10000.0",
            "B": "0",
            "x": False,  # Not closed
        }
    }


@pytest.fixture
def sample_websocket_kline_message_closed() -> dict:
    """Mock WebSocket kline event message (candle closed)."""
    base_ms = 1609459200000
    return {
        "e": "kline",
        "E": base_ms,
        "s": "BTCUSDT",
        "k": {
            "t": base_ms,
            "T": base_ms + 3600000,
            "s": "BTCUSDT",
            "i": "1h",
            "f": 100,
            "L": 200,
            "o": "100.5",
            "c": "100.5",
            "h": "101.0",
            "l": "99.5",
            "v": "500.0",
            "q": "50000.0",
            "n": 10,
            "V": "100.0",
            "Q": "10000.0",
            "B": "0",
            "x": True,  # Closed
        }
    }


@pytest.fixture
def sample_websocket_non_kline_message() -> dict:
    """Mock WebSocket message that is NOT a kline event."""
    return {
        "e": "trade",
        "E": 1609459200000,
        "s": "BTCUSDT",
    }


# ============================================================================
# KLINE EVENT FIXTURES
# ============================================================================


@pytest.fixture
def sample_kline_event(sample_websocket_kline_message) -> KlineEvent:
    """Valid KlineEvent object."""
    return KlineEvent.from_message(sample_websocket_kline_message)


@pytest.fixture
def sample_kline_event_closed(sample_websocket_kline_message_closed) -> KlineEvent:
    """KlineEvent with candle closed."""
    return KlineEvent.from_message(sample_websocket_kline_message_closed)


# ============================================================================
# HTTP RESPONSE FIXTURES
# ============================================================================


@pytest.fixture
def mock_httpx_response_200(mock_binance_single_page_response) -> httpx.Response:
    """Mock successful HTTP response."""
    return httpx.Response(200, json=mock_binance_single_page_response)


@pytest.fixture
def mock_httpx_response_429_with_retry_after() -> httpx.Response:
    """Mock 429 response with Retry-After header."""
    return httpx.Response(
        429,
        json={"code": -1003, "msg": "Too much request weight used"},
        headers={"Retry-After": "10"}
    )


@pytest.fixture
def mock_httpx_response_503() -> httpx.Response:
    """Mock 503 Service Unavailable response."""
    return httpx.Response(503, json={"code": -1001, "msg": "Server unavailable"})


# ============================================================================
# MOCK HELPERS
# ============================================================================


@pytest.fixture
def mock_sleep(mocker):
    """Mock asyncio.sleep to avoid waiting in tests."""
    return mocker.patch("asyncio.sleep", new_callable=AsyncMock)


@pytest.fixture
def mock_websocket_connect(mocker):
    """Mock websockets.connect for streaming tests."""
    return mocker.patch("websockets.connect", new_callable=AsyncMock)


@pytest.fixture
def mock_datetime_now(mocker):
    """Mock datetime.now() to return fixed datetime."""
    base_dt = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return mocker.patch("datetime.datetime", wraps=datetime)


# ============================================================================
# ASYNC FIXTURES
# ============================================================================


@pytest.fixture
async def async_context_manager_mock():
    """Mock async context manager."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock()
    mock.__aexit__ = AsyncMock()
    return mock


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Disable external network calls
    import os
    os.environ["PYTEST_CURRENT_TEST"] = "test"
    yield
    # Cleanup
    pass
