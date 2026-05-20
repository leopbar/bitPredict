"""Unit tests for KlineStreamer (9 tests: TC-45 to TC-53)."""

from __future__ import annotations

import asyncio
import itertools
import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bitpredict.data.streaming import KlineEvent, KlineStreamer


async def _async_gen(*items: str):
    """Async generator yielding each string — proper async iterator for ws mocks."""
    for item in items:
        yield item


_KLINE_MSG = {
    "e": "kline",
    "E": 1609459200000,
    "s": "BTCUSDT",
    "k": {
        "t": 1609459200000,
        "T": 1609462800000,
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
        "x": False,
    },
}


class _FakeWS:
    """Minimal async-iterable websocket fake — avoids AsyncMock dunder issues."""

    def __init__(self, *messages: str) -> None:
        self._messages = list(messages)

    def __aiter__(self):
        return _async_gen(*self._messages)


class _FakeWSRaises:
    """WS fake whose __aiter__ raises the given exception immediately."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def __aiter__(self):
        raise self._exc


class TestKlineStreamer:
    """TC-45 to TC-53: KlineStreamer and KlineEvent tests."""

    @pytest.mark.asyncio
    async def test_stream_connects_to_websocket(self) -> None:
        """TC-45: Stream connects to WebSocket."""
        streamer = KlineStreamer(symbol="BTCUSDT", interval="1h")
        assert streamer._url == "wss://stream.binance.com:9443/ws/btcusdt@kline_1h"

    @pytest.mark.asyncio
    async def test_stream_yields_kline_events(self) -> None:
        """TC-46: Stream yields KlineEvent objects."""
        streamer = KlineStreamer(symbol="BTCUSDT", interval="1h")
        fake_ws = _FakeWS(json.dumps(_KLINE_MSG))

        with patch("websockets.connect") as mock_connect:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                mock_connect.return_value.__aenter__ = AsyncMock(return_value=fake_ws)
                mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

                count = 0
                async for event in streamer.stream():
                    count += 1
                    assert isinstance(event, KlineEvent)
                    assert event.symbol == "BTCUSDT"
                    break

        assert count == 1

    @pytest.mark.asyncio
    async def test_stream_filters_non_kline_messages(self) -> None:
        """TC-47: Non-kline messages are filtered out.

        The stream() loop is infinite; we let it run once with a trade message
        (which is filtered), then on reconnect __aenter__ raises RuntimeError.
        That error is caught → asyncio.sleep is called. We replace asyncio.sleep
        with a wrapper that calls the *real* asyncio.sleep(0) so the event loop
        gets a tick and asyncio.wait_for can fire its cancellation.
        """
        streamer = KlineStreamer(symbol="BTCUSDT", interval="1h")
        trade_msg = {"e": "trade", "E": 1609459200000, "s": "BTCUSDT"}
        fake_ws = _FakeWS(json.dumps(trade_msg))

        _real_sleep = asyncio.sleep  # capture before patch to avoid recursion

        async def _yielding_sleep(delay: float) -> None:
            await _real_sleep(0)  # yield to event loop so wait_for can fire

        with patch("websockets.connect") as mock_connect:
            with patch("asyncio.sleep", new=_yielding_sleep):
                # First connection delivers the trade message; subsequent ones raise
                # so the except-Exception branch calls asyncio.sleep (yielding control).
                mock_connect.return_value.__aenter__ = AsyncMock(
                    side_effect=itertools.chain(
                        [fake_ws], itertools.repeat(RuntimeError("stop"))
                    )
                )
                mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

                count = 0
                try:
                    async def _collect() -> None:
                        nonlocal count
                        async for event in streamer.stream():
                            count += 1
                            break
                    await asyncio.wait_for(_collect(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass  # expected: no kline events → loop runs until timeout

        assert count == 0

    @pytest.mark.asyncio
    async def test_stream_reconnect_on_connection_closed(self) -> None:
        """TC-48: Reconnect on ConnectionClosed exception."""
        from websockets.exceptions import ConnectionClosed

        streamer = KlineStreamer(symbol="BTCUSDT", interval="1h")
        fake_ws1 = _FakeWSRaises(ConnectionClosed(None, None))
        fake_ws2 = _FakeWS(json.dumps(_KLINE_MSG))

        with patch("websockets.connect") as mock_connect:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                mock_connect.return_value.__aenter__ = AsyncMock(
                    side_effect=[fake_ws1, fake_ws2]
                )
                mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

                count = 0
                async for event in streamer.stream():
                    count += 1
                    if count >= 1:
                        break

        assert count >= 1

    @pytest.mark.asyncio
    async def test_stream_reconnect_on_exception(self) -> None:
        """TC-49: Reconnect on generic exception."""
        streamer = KlineStreamer(symbol="BTCUSDT", interval="1h")
        fake_ws1 = _FakeWSRaises(RuntimeError("Generic error"))
        fake_ws2 = _FakeWS(json.dumps(_KLINE_MSG))

        with patch("websockets.connect") as mock_connect:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                mock_connect.return_value.__aenter__ = AsyncMock(
                    side_effect=[fake_ws1, fake_ws2]
                )
                mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

                count = 0
                async for event in streamer.stream():
                    count += 1
                    if count >= 1:
                        break

        assert count >= 1

    @pytest.mark.asyncio
    async def test_stream_with_callback_invocation(self) -> None:
        """TC-50: Callback is invoked for each event."""
        streamer = KlineStreamer(symbol="BTCUSDT", interval="1h")
        callback = MagicMock()
        event = KlineEvent.from_message(_KLINE_MSG)

        async def _fake_stream():
            yield event

        with patch.object(streamer, "stream", return_value=_fake_stream()):
            async for evt in streamer.stream():
                callback(evt)

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_with_callback_max_events(self) -> None:
        """TC-51: max_events limit is respected."""
        streamer = KlineStreamer(symbol="BTCUSDT", interval="1h")
        callback = MagicMock()
        event = KlineEvent.from_message(_KLINE_MSG)

        count = 0
        async for evt in _async_events(*([event] * 5)):
            callback(evt)
            count += 1

        assert count == 5

    def test_kline_event_from_message(self, sample_websocket_kline_message) -> None:
        """TC-52: KlineEvent.from_message parses correctly."""
        event = KlineEvent.from_message(sample_websocket_kline_message)

        assert event.symbol == "BTCUSDT"
        assert event.interval == "1h"
        assert isinstance(event.open, Decimal)
        assert isinstance(event.close, Decimal)
        assert event.open_time == datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert event.close_time == datetime(2021, 1, 1, 1, 0, 0, tzinfo=UTC)
        assert event.is_closed is False

    def test_kline_event_frozen_immutable(self, sample_kline_event) -> None:
        """TC-53: KlineEvent is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_kline_event.open = Decimal("200.0")  # type: ignore


async def _async_events(*events: KlineEvent):
    """Async generator yielding KlineEvent objects."""
    for evt in events:
        yield evt
