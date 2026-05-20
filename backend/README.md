# bitPredict — Backend

Python backend for the bitPredict Kronos forecasting system.

## Stack

- **FastAPI** — REST API with API key auth
- **Celery + Redis** — async task queue; two worker pools (`predictions`, `backtests`)
- **Celery Beat** — scheduled kline ingestion and Kronos predictions per timeframe
- **SQLAlchemy 2.0 + Alembic** — ORM and migrations
- **TimescaleDB** — hypertable for `klines` and `kronos_predictions`
- **Kronos (NeoQuasar)** — 102M-param foundation model loaded via HuggingFace Hub

## Running

From the project root:

```bash
docker compose up -d
docker compose exec backend bitpredict smoke        # infra health
docker compose exec backend bitpredict kronos smoke  # model health + data freshness
```

## Key modules

| Path | Purpose |
|---|---|
| `api/routes/kronos.py` | Kronos prediction, history, scoreboard, progress, trigger endpoints |
| `api/routes/data.py` | Klines endpoints including `POST /klines/ensure/{tf}` |
| `kronos/` | loader, inference, service, tasks, backtest, timeframes |
| `scheduling/tasks.py` | `ingest_klines`, `rsi2_inference_tick`, etc. |
| `scheduling/beat_schedule.py` | Cron schedules for all 6 timeframes |

## Code layout

```
src/bitpredict/
  api/          FastAPI app and routes
  kronos/       Kronos model integration
  data/         Binance data ingestion
  scheduling/   Celery app, tasks, beat schedule
  db_models.py  SQLAlchemy ORM models
  cli/          Typer CLI commands
```
