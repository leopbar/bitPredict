# bitPredict

Bitcoin price forecasting dashboard powered by **Kronos** — NeoQuasar's 102M-parameter foundation model for financial time series.

## What it does

For each of 6 timeframes (15m · 1h · 4h · 8h · 1d · 1w), Kronos runs 30 independent stochastic simulations using the last 512 candles as context and produces:

- **Predicted OHLCV** (median of 30 runs)
- **Q10 / Q90 confidence band** for the close
- **% Bullish** — fraction of simulations predicting a higher close
- **Historical accuracy scoreboard** — directional accuracy and close error % filled in automatically after each candle closes

A second dashboard (`/rsi2`) runs an independent RSI-2 mean-reversion strategy on BTC 15m candles.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Celery, SQLAlchemy 2.0, Alembic |
| Model | Kronos (NeoQuasar) via HuggingFace Hub |
| Database | PostgreSQL + TimescaleDB |
| Queue | Redis + Celery Beat |
| Frontend | Next.js 15, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui, lightweight-charts |

## Quickstart

```bash
# 1. Copy and fill in environment variables
cp backend/.env.example backend/.env

# 2. Start all services
docker compose up -d

# 3. Verify infrastructure
docker compose exec backend bitpredict smoke

# 4. Verify Kronos models and data freshness
docker compose exec backend bitpredict kronos smoke
```

## Services

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Flower (queue monitor) | http://localhost:5555 |
