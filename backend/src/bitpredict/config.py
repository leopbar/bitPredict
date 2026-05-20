"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: PostgresDsn
    redis_url: RedisDsn
    mlflow_tracking_uri: str

    binance_base_url: str = "https://api.binance.com"
    log_level: str = "INFO"
    environment: Literal["dev", "prod"] = "dev"

    api_key: str = "dev-secret-key"
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Reporting
    reports_dir: str = "/app/data/reports"

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
