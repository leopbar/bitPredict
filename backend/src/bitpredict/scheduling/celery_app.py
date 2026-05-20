"""Celery application instance for bitPredict background tasks."""

from __future__ import annotations

from celery import Celery

from bitpredict.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "bitpredict",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["bitpredict.scheduling.tasks", "bitpredict.kronos.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        result_expires=86400,  # 24h
        # Prevent re-delivery of long-running tasks (backtests can take 2h+).
        # Default Redis visibility_timeout is 1h, which causes duplicate execution.
        broker_transport_options={"visibility_timeout": 21600},  # 6h
        task_routes={
            "kronos.run_prediction": {"queue": "predictions"},
            "kronos.run_backtest":   {"queue": "backtests"},
        },
    )
    return app


celery_app = create_celery_app()
