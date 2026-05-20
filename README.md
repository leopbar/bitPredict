# bitPredict

Bitcoin price forecasting dashboard powered by **Kronos** — NeoQuasar's 102M-parameter foundation model for financial time series.

## Overview

**bitPredict** is a multi-timeframe BTC forecasting system with two independent strategies:

1. **Kronos Dashboard** (main, `/`) — 30 stochastic simulations × 6 timeframes, confidence bands, backtest engine
2. **RSI-2 Strategy** (`/rsi2`) — Mean-reversion signal + equity curve, independent of Kronos

All code in **English**. UI in English (except `/rsi2` which remains in Portuguese for legacy reasons).

---

## What Kronos Does

For each of 6 timeframes (15m · 1h · 4h · 8h · 1d · 1w UTC), Kronos:

1. **Ingests** last 512 candles as context
2. **Runs 30 stochastic simulations** (temperature=0.8, sample_count=30)
3. **Produces** for the next candle:
   - Predicted **OHLCV** (median of 30 runs)
   - **Q10 / Q90 confidence band** for close price
   - **% Bullish** — fraction of simulations with close > open
   - **Analyst distribution histogram** — 10-bucket distribution of all 30 closes

4. **Validates** automatically after candle closes:
   - Direction correctness (bullish vs bearish)
   - Close price error %
   - High-confidence calibration (when ≥70% confident, how often correct?)

---

## Architecture

### Backend

```
bitpredict/
├── kronos/              ← Kronos inference + backtest engine
│   ├── loader.py       ← Model loading + caching
│   ├── inference.py    ← Stochastic simulation
│   ├── timeframes.py   ← TF enum + conversions
│   ├── service.py      ← Orchestration
│   ├── tasks.py        ← Celery tasks
│   └── backtest.py     ← Historical backtesting
├── strategies/rsi2/    ← RSI-2 mean-reversion (untouched)
├── api/routes/
│   ├── kronos.py       ← 9 prediction/backtest endpoints
│   └── rsi2.py         ← RSI-2 signals + trades
├── scheduling/         ← Celery Beat scheduler
└── ...
```

**Key features:**
- 6 timeframes, independent task queue lanes (predictions vs backtests)
- Soft-stop mechanism via Redis key
- Per-sample + per-simulation progress tracking
- Portfolio simulation in backtest (initial capital, position %, compound interest)

### Frontend

```
frontend/
├── app/
│   ├── page.tsx        ← Kronos dashboard (main)
│   ├── backtest/       ← Backtest UI
│   └── rsi2/           ← RSI-2 dashboard (Portuguese)
├── components/kronos/
│   ├── analyst-distribution-chart.tsx  ← SVG histogram
│   ├── prediction-panel.tsx             ← Price targets + consensus cards
│   ├── live-candle-card.tsx
│   ├── scoreboard-card.tsx
│   └── ... (8 more cards)
└── lib/hooks/
    ├── use-kronos.ts   ← 10+ query hooks + mutations
    └── use-klines.ts
```

**Layout:** Two-column grid (main content + right sidebar), responsive to mobile. All metrics with tooltips (layperson-friendly language, no jargon).

### Data

- **Postgres 16 + TimescaleDB** — hypertable for klines + kronos_predictions + kronos_backtests
- **Redis** — Celery broker + beat scheduler
- **Binance** — Live 15m/1h/4h/8h/1d/1w candles via REST API

### Scheduling

| Task | Frequency | Purpose |
|------|-----------|---------|
| `ingest_klines(15m)` | Every 15 min | Download latest candles |
| `ingest_klines(1h/4h/8h/1d/1w)` | Per-timeframe intervals | Multi-TF data freshness |
| `run_kronos_prediction(15m)` | Every 15 min | Inference |
| `run_kronos_prediction(1h/4h/...)` | Per-TF intervals | All 6 timeframes active |
| `fill_actuals()` | Every 5 min | Backfill actuals when candles close |
| `run_kronos_backtest(tf)` | Weekly (Sunday, staggered) | Historical validation |

---

## Stack

| Layer | Technology | Version |
|---|---|---|
| **Language** | Python 3.12 | latest |
| **Backend** | FastAPI | 0.100+ |
| **ORM** | SQLAlchemy | 2.0 |
| **Migrations** | Alembic | — |
| **Model** | Kronos (NeoQuasar) | via HuggingFace Hub |
| **Task queue** | Celery | 5.3+ |
| **Broker** | Redis | 7+ |
| **Database** | PostgreSQL 16 | + TimescaleDB extension |
| **Frontend** | Next.js | 15 (App Router) |
| **UI Framework** | React | 19 |
| **Styling** | Tailwind CSS | 4 |
| **Components** | shadcn/ui | — |
| **Charts** | lightweight-charts + custom SVG | — |
| **State** | TanStack Query | 5 |
| **Validation** | Zod (client), Pydantic v2 (server) | — |

---

## Getting Started

### Prerequisites

- Docker + Docker Compose (or local Python 3.12, Postgres 16, Redis 7, Node 20)
- Binance API credentials (optional, defaults to free tier)
- HuggingFace token (for Kronos model download)

### Quick Start

```bash
# 1. Copy environment template
cp backend/.env.example backend/.env

# 2. Start all services
docker compose up -d

# 3. Verify infrastructure
docker compose exec backend bitpredict smoke

# 4. Verify Kronos and data freshness
docker compose exec backend bitpredict kronos smoke

# 5. Monitor Celery tasks
open http://localhost:5555  # Flower

# 6. Open dashboard
open http://localhost:3000
```

### Local Development (without Docker)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements-dev.txt
export $(cat .env | grep -v '^#')
bitpredict api

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Services

| Service | URL | Purpose |
|---|---|---|
| **Dashboard** | http://localhost:3000 | Kronos + RSI-2 UI |
| **API Docs** | http://localhost:8000/docs | Swagger interactive |
| **Flower** | http://localhost:5555 | Celery task monitor |
| **Postgres** | localhost:5432 | Database |
| **Redis** | localhost:6379 | Cache + broker |

---

## Dashboards

### Kronos (Main Dashboard, `/`)

**Timeframes:** 15m · 1h · 4h · 8h · 1d · 1w (UTC)

**Cards:**
1. **Price Targets** — Expected close + confidence badge + Q10/Q90 range + OHLC
2. **Consensus** — Directional arrow + % bullish/bearish + analyst split bar + candle progress
3. **Live Candle** — Current candle open/close/high/low + live price ticker
4. **Analyst Distribution** — SVG histogram (10 buckets) + bezier curve + band markers
5. **Scoreboard** — Directional accuracy + MAPE + calibration metrics
6. **History Table** — Last 50 predictions (time · TF · predicted vs actual · error % · direction ✓/✗)

**Progress Card** (while running):
- Sample progress (X/Y samples)
- Per-sample simulation progress (X/Y sims)
- ETA based on rolling average
- Stop button (soft-cancel)

### RSI-2 Strategy (`/rsi2`)

Independent mean-reversion signal on 15m BTC. All in Portuguese (legacy). Includes:
- Signal state (buy/sell/hold)
- Equity curve + drawdown
- Trade history + metrics

**Note:** RSI-2 is untouched during Kronos refactor; remains production-ready.

---

## API Endpoints

### Kronos

```
GET  /kronos/prediction/{timeframe}         → Active prediction
GET  /kronos/history/{timeframe}            → Last 50 predictions + actuals
GET  /kronos/backtest/{timeframe}           → Last backtest metrics
GET  /kronos/health                         → Worker/scheduler status
POST /kronos/prediction/{timeframe}/trigger → Start inference now
POST /kronos/prediction/{timeframe}/stop    → Cancel running task
POST /kronos/backtest/{timeframe}/trigger   → Start backtest now
GET  /kronos/progress/{timeframe}           → Task progress (step, ETA, %)
```

### RSI-2

```
GET  /rsi2/signal/{timeframe}
GET  /rsi2/trades
GET  /rsi2/health
```

### System

```
GET  /health
GET  /readiness
GET  /docs (Swagger)
```

---

## Metrics Explained

### Directional Accuracy
% of times Kronos correctly predicted whether close > open (bullish) or close ≤ open (bearish).

### MAPE (Mean Absolute Percentage Error)
Average % deviation of predicted vs actual close. Lower is better. Shown separately for close/high/low/volume.

### High-Confidence Calibration
When Kronos was ≥70% confident (either bullish or bearish), how often was it correct? Shown as:
- % accuracy (e.g., 71%)
- Count of samples where it was that confident (e.g., 38/50)

Example: "Acertou 63% das direções, mas quando teve ≥70% de convicção acertou 71% — e isso aconteceu em 38 das 50 amostras."

---

## Project Structure

```
bitPredict/
├── backend/
│   ├── src/bitpredict/
│   │   ├── kronos/                 ← New (Phase C)
│   │   ├── strategies/rsi2/        ← Existing (Phase B)
│   │   ├── api/
│   │   ├── scheduling/
│   │   ├── data/
│   │   └── ...
│   ├── alembic/versions/           ← DB migrations
│   ├── scripts/                    ← Dev tools
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx                ← Kronos dashboard
│   │   ├── backtest/
│   │   └── rsi2/                   ← RSI-2 dashboard
│   ├── components/kronos/          ← 11 card components
│   ├── lib/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── plan.md                         ← Execution roadmap
├── PROGRESS.md                     ← Current session summary
└── README.md                       ← This file
```

---

## Key Design Decisions

1. **Kronos over ensemble** — Single frozen foundation model (no retraining) for 6 timeframes beats Phase A's 4-model ensemble (retraining overhead). Stochastic sampling replaces learned quantile regression.

2. **6 independent timeframes** — Each TF has its own task queue lane (predictions vs backtests) to avoid blocking.

3. **Phase B (RSI-2) untouched** — Different strategy, different audience, different language (PT-BR). No interference during Kronos integration.

4. **Soft-stop + progress tracking** — Celery tasks report per-sample + per-simulation progress; Stop button sets Redis key (task checks between simulations).

5. **Portfolio simulation in backtest** — Allows analysts to stress-test position sizing, compound interest, drawdown tolerance.

6. **Docker named volumes** — OneDrive constraint: `node_modules`, `.next`, `venv` live in Docker volumes (not synced), avoiding silent EACCES + stale bundles.

---

## Development

### Running Tests

```bash
# Backend unit tests
docker compose exec backend pytest -xvs

# Backend integration tests (requires services up)
docker compose exec backend pytest tests/integration -xvs

# Frontend type check
docker compose exec frontend npm run type-check

# Frontend linting
docker compose exec frontend npm run lint
```

### Monitoring

```bash
# Tail backend logs
docker compose logs -f backend

# Tail Celery worker logs
docker compose logs -f worker

# Watch Celery tasks in Flower
open http://localhost:5555

# Database: connect and inspect
psql -h localhost -U bitpredict -d bitpredict
```

### Adding a New Timeframe

Not currently exposed in UI (hardcoded 15m), but infrastructure supports it:

1. Add `M60 = "1h"` to `Timeframe` enum in `kronos/timeframes.py`
2. Create Alembic migration to add klines for that interval
3. Add Celery beat schedule for ingest + prediction
4. Restart beat scheduler

---

## Language

- **Code, comments, identifiers, logs** — English
- **UI text** — English (global)
- **Exception:** `/rsi2` dashboard remains Portuguese (legacy, untouched)

This separation lets Portuguese-speaking analysts work on RSI-2 while English-speaking developers maintain Kronos.

---

## Important Notes

### Phase A (24h Forecaster) — Deleted
The original deep learning ensemble (LightGBM + LSTM + N-BEATS + TFT) was deleted on 2026-05-18. Replaced by Kronos for better operational simplicity and multi-timeframe coverage.

### Phase B (RSI-2) — Active
Independent mean-reversion strategy. Untouched during Phase C refactor. Production-ready on `/rsi2`.

### Phase C (Kronos Integration) — In Progress
Stages 1–5 complete (backend + frontend layout). Stages 6–7 (backtest integration + E2E) pending.

---

## Troubleshooting

**Dashboard doesn't load?**
- Check backend: `docker compose logs backend | head -50`
- Check API health: `curl http://localhost:8000/health`
- Check frontend build: `docker compose logs frontend | grep -i error`

**Predictions not running?**
- Check Celery: `docker compose logs worker | head -50`
- Check Flower: http://localhost:5555
- Check Redis: `redis-cli ping`

**Backtest stuck in loading?**
- Worker may still be running (backtests take 1–2 hours for 1d TF)
- Check Flower for task state
- If truly stuck, restart worker: `docker compose restart worker_backtests`

---

## License

MIT

---

## Author

Developed as a production forecasting system integrating Kronos (NeoQuasar) with a custom backtest engine and interactive dashboard.

**Repository:** [github.com/leopbar/bitPredict](https://github.com/leopbar/bitPredict)
