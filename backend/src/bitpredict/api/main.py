"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bitpredict.api.routes import data, health, parameters
from bitpredict.api.routes import kronos as kronos_routes
from bitpredict.api.routes import rsi2 as rsi2_routes
from bitpredict.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("bitPredict API starting (env=%s)", settings.environment)
    yield
    logger.info("bitPredict API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="bitPredict API",
        description="Bitcoin price forecasting powered by Kronos foundation model.",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    origins = [o.strip() for o in settings.api_cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def _log_requests(request: Request, call_next) -> Response:  # type: ignore[return]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health.router)
    app.include_router(parameters.router)
    app.include_router(data.router)
    app.include_router(rsi2_routes.router)
    app.include_router(kronos_routes.router)

    return app


app = create_app()
