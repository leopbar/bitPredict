"""Real-time kline streaming via Binance WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import AsyncIterator, Callable

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

_WS_BASE = "wss://stream.binance.com:9443/ws"
_RECONNECT_DELAY = 5.0


@dataclass(frozen=True)
class KlineEvent:
    event_time: datetime
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades: int
    is_closed: bool

    @classmethod
    def from_message(cls, msg: dict[object, object]) -> "KlineEvent":
        k = msg["k"]  # type: ignore[index]
        return cls(
            event_time=datetime.fromtimestamp(int(msg["E"]) / 1000, tz=UTC),  # type: ignore[arg-type]
            symbol=str(k["s"]),  # type: ignore[index]
            interval=str(k["i"]),  # type: ignore[index]
            open_time=datetime.fromtimestamp(int(k["t"]) / 1000, tz=UTC),  # type: ignore[index]
            close_time=datetime.fromtimestamp(int(k["T"]) / 1000, tz=UTC),  # type: ignore[index]
            open=Decimal(str(k["o"])),  # type: ignore[index]
            high=Decimal(str(k["h"])),  # type: ignore[index]
            low=Decimal(str(k["l"])),  # type: ignore[index]
            close=Decimal(str(k["c"])),  # type: ignore[index]
            volume=Decimal(str(k["v"])),  # type: ignore[index]
            trades=int(k["n"]),  # type: ignore[index]
            is_closed=bool(k["x"]),  # type: ignore[index]
        )


class KlineStreamer:
    """Subscribe to a Binance kline stream with automatic reconnection."""

    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1h") -> None:
        self._stream = f"{symbol.lower()}@kline_{interval}"
        self._url = f"{_WS_BASE}/{self._stream}"

    async def stream(self) -> AsyncIterator[KlineEvent]:
        """Yield KlineEvent objects indefinitely, reconnecting on drops."""
        while True:
            try:
                async with websockets.connect(self._url, ping_interval=20) as ws:
                    logger.info("Connected to Binance stream: %s", self._stream)
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("e") == "kline":
                            yield KlineEvent.from_message(msg)
            except ConnectionClosed as exc:
                logger.warning("Stream closed (%s), reconnecting in %ss…", exc, _RECONNECT_DELAY)
                await asyncio.sleep(_RECONNECT_DELAY)
            except Exception as exc:  # noqa: BLE001
                logger.error("Stream error (%s), reconnecting in %ss…", exc, _RECONNECT_DELAY)
                await asyncio.sleep(_RECONNECT_DELAY)

    async def stream_with_callback(
        self,
        callback: Callable[[KlineEvent], None],
        max_events: int | None = None,
    ) -> None:
        """Stream events and call *callback* for each one."""
        count = 0
        async for event in self.stream():
            callback(event)
            count += 1
            if max_events is not None and count >= max_events:
                break
