"""FastAPI dependency injection providers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from bitpredict.config import Settings, get_settings
from bitpredict.db import get_session


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, closing it after the request."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def settings() -> Settings:
    return get_settings()
