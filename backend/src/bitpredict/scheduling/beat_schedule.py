"""Celery Beat periodic schedule configuration."""

from __future__ import annotations

from celery.schedules import crontab

from bitpredict.scheduling.celery_app import celery_app

celery_app.conf.beat_schedule = {

    # ── Kronos 15m cycle: ingest → predict, guaranteed sequential ────────────
    "kronos-15m-cycle": {
        "task": "kronos.run_15m_cycle",
        "schedule": crontab(minute="1,16,31,46"),
    },

    # ── Kronos 1h cycle: ingest → predict, offset by 1 min to avoid CPU clash ─
    "kronos-1h-cycle": {
        "task": "kronos.run_1h_cycle",
        "schedule": crontab(minute=2),
    },

    # ── Kronos 1d cycle: fires at 00:03 UTC after the daily candle closes ────
    "kronos-1d-cycle": {
        "task": "kronos.run_1d_cycle",
        "schedule": crontab(hour=0, minute=3),
    },

    # ── Kronos actuals fill (every 5 min) ────────────────────────────────────
    "kronos-fill-actuals": {
        "task": "kronos.fill_actuals",
        "schedule": crontab(minute="*/5"),
    },

    # ── RSI-2 Strategy (untouched) ────────────────────────────────────────────
    "ingest-15min-klines": {
        "task": "tasks.ingest_15min_klines",
        "schedule": crontab(minute="*/15"),
        "args": ("BTCUSDT",),
    },
    "rsi2-inference-tick": {
        "task": "tasks.rsi2_inference_tick",
        "schedule": crontab(minute="*/15"),
        "args": ("BTCUSDT",),
    },
    "ingest-funding-rates": {
        "task": "tasks.ingest_funding_rates",
        "schedule": crontab(hour="*/8", minute=5),
        "args": ("BTCUSDT",),
    },
}
