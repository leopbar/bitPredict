"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_KEYS = {"dev-secret-key", "secret", "changeme", "password", "test"}
_MIN_KEY_LENGTH = 32


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

    @model_validator(mode="after")
    def _reject_insecure_key_in_prod(self) -> "Settings":
        if self.environment != "prod":
            return self
        if self.api_key.lower() in _INSECURE_KEYS:
            raise ValueError(
                "API_KEY is set to a known insecure default. "
                "Set a strong random key before starting in production."
            )
        if len(self.api_key) < _MIN_KEY_LENGTH:
            raise ValueError(
                f"API_KEY must be at least {_MIN_KEY_LENGTH} characters in production."
            )
        return self

    # Reporting
    reports_dir: str = "/app/data/reports"

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
