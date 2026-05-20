"""Async HTTP client for the Binance REST API with rate-limit awareness and retry."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from bitpredict.config import get_settings

logger = logging.getLogger(__name__)

_WEIGHT_BACKOFF_THRESHOLD = 1000
_WEIGHT_BACKOFF_SLEEP = 60.0
_MAX_KLINES_PER_REQUEST = 1000


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, httpx.TimeoutException | httpx.NetworkError)


class BinanceClient:
    """Thin async wrapper around the Binance public REST API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.binance_base_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._used_weight: int = 0

    async def __aenter__(self) -> "BinanceClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0),
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def used_weight(self) -> int:
        return self._used_weight

    def _update_weight(self, response: httpx.Response) -> None:
        raw = response.headers.get("X-MBX-USED-WEIGHT-1M", "0")
        try:
            self._used_weight = int(raw)
        except ValueError:
            pass

    async def _maybe_backoff(self) -> None:
        if self._used_weight >= _WEIGHT_BACKOFF_THRESHOLD:
            logger.warning(
                "Binance weight near limit (%d), sleeping %ss",
                self._used_weight,
                _WEIGHT_BACKOFF_SLEEP,
            )
            await asyncio.sleep(_WEIGHT_BACKOFF_SLEEP)

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = _MAX_KLINES_PER_REQUEST,
    ) -> list[list[Any]]:
        """Fetch up to *limit* klines from /api/v3/klines."""
        assert self._client is not None, "Use BinanceClient as an async context manager."

        await self._maybe_backoff()

        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, _MAX_KLINES_PER_REQUEST),
        }
        if start_time is not None:
            params["startTime"] = int(start_time.timestamp() * 1000)
        if end_time is not None:
            params["endTime"] = int(end_time.timestamp() * 1000)

        response = await self._client.get("/api/v3/klines", params=params)
        self._update_weight(response)
        await self._maybe_backoff()

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", _WEIGHT_BACKOFF_SLEEP))
            logger.warning("Rate limited by Binance, sleeping %ss", retry_after)
            await asyncio.sleep(retry_after)
            response.raise_for_status()

        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def get_server_time(self) -> datetime:
        """Return current Binance server time as a UTC datetime."""
        assert self._client is not None
        response = await self._client.get("/api/v3/time")
        response.raise_for_status()
        ms: int = response.json()["serverTime"]
        return datetime.fromtimestamp(ms / 1000, tz=UTC)

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_ticker_24h(self, symbol: str) -> dict[str, Any]:
        """Fetch 24-hour rolling ticker for *symbol* from /api/v3/ticker/24hr.

        Returns last price, 24h price change, % change, high/low, volume, etc.
        Endpoint weight is 2, suitable for polling every few seconds.
        """
        assert self._client is not None, "Use BinanceClient as an async context manager."
        response = await self._client.get(
            "/api/v3/ticker/24hr",
            params={"symbol": symbol.upper()},
        )
        self._update_weight(response)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
