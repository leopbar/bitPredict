# Plan — bitPredict: Bitcoin Price Prediction System

## 📊 Execution Status (Last Updated: 2026-05-19)

### Summary

- **Phase A** (24h Deep Learning Forecaster): ❌ **DELETED** (2026-05-18) — replaced by Kronos
- **Phase B** (RSI-2 Mean Reversion): ✅ **COMPLETE** — untouched, in production
- **Phase C** (Kronos Integration): 🚀 **IN PROGRESS** — 5/7 stages complete

---

## Phase A — 24h BTC Forecaster (DELETED ❌)

**Status:** Removed on 2026-05-18.

**Reason:** Phase A was an exploratory deep learning project (4 models: LightGBM, LSTM, N-BEATS, TFT + ensemble). While technically complete and validated, it incurred high operational overhead (model retraining, drift monitoring, MLflow) for marginal forecasting gain vs. Kronos. The Kronos foundation model (102M params) requires zero retraining, covers 6 timeframes (not just 24h), and leverages stochastic sampling for natural confidence intervals.

**Deletion scope:**
- ✅ Alembic migrations dropped tables: `predictions`, `model_runs`, `alerts`, `reports`, `monitoring_metrics`
- ✅ Backend modules removed: `training/`, `backtesting/`, `alerts/`, `reporting/`, `monitoring/`, `models/` (LSTM, N-BEATS, TFT, ensemble, baselines)
- ✅ Backend routes removed: `predictions.py`, `alerts.py`, `reports.py`, `backtest.py`, `models.py`, `training.py`
- ✅ CLI commands removed: `train.py`, `backtest.py`, `predict.py`
- ✅ Celery tasks removed: retraining, ensemble refit, drift metrics, report generation
- ✅ MLflow service and database removed from infrastructure
- ✅ Frontend routes removed: `/predictions`, `/backtesting`, `/charts`, `/parameters`, `/training`, `/data`, `/alerts`, `/reports`, `/exports`, `/monitoring`
- ✅ Frontend sidebar: reduced from 12 items to 2 (Home, RSI-2)
- ✅ Dependencies removed: `lightgbm`, `torch`, `lightning`, `optuna`, `statsmodels`, `pmdarima`, `weasyprint`, `openpyxl`, `jinja2`, `mlflow`

---

## Phase B — RSI-2 Mean Reversion Strategy (COMPLETE ✅)

| Stage | Name | Status | Validated |
|-------|------|--------|-----------|
| B1 | Data foundation (15min ingest + funding) | ✅ | ✅ |
| B2 | Strategy core (signals, engine, metrics) | ✅ | ✅ |
| B3 | Optuna optimization — Caminho A (500 trials) | ✅ | ✅ |
| B4 | Caminho B — XGBoost meta-labeling | ✅ | ✅ |
| B5 | A vs A+B selection (winner.json) | ✅ | ✅ |
| B6 | Sealed test (2025-01-01 → today) | ✅ | ✅ |
| B7 | Inference loop + FastAPI /rsi2 routes | ✅ | ✅ |
| B8 | /rsi2 frontend dashboard | ✅ | ✅ |
| B9 | End-to-end verification | ✅ | ✅ |

**Status:** Production. All code in Portuguese per original design. **Untouched during Phase C refactor.**

---

## Phase C — Kronos Multi-Timeframe Integration (IN PROGRESS 🚀)

| Stage | Name | Status | Validated |
|-------|------|--------|-----------|
| 1 | Backend cleanup (delete Phase A) | ✅ | ✅ |
| 2 | Frontend cleanup (delete Phase A routes) | ✅ | ✅ |
| 3 | Kronos backend (multi-TF engine) | ✅ | ✅ |
| 4 | Kronos API (9 endpoints) | ✅ | ✅ |
| 5 | Kronos frontend dashboard | 🟡 **MOSTLY** | 🟡 |
| 6 | Backtest pipeline | 🟡 **PARTIAL** | ❓ |
| 7 | E2E verification + polish | ⏳ | ⏳ |

### Stage 1 ✅ Backend Cleanup (2026-05-18)

**What was done:**
- Deleted 5 modules: training, backtesting, alerts, reporting, monitoring
- Deleted 6 API routes: predictions, alerts, reports, backtest, models, training
- Deleted 3 CLI commands: train, backtest, predict
- Deleted 7 Celery tasks: retraining, ensemble refit, drift, report generation
- Deleted MLflow service, database, volume from docker-compose
- Updated requirements.txt: removed 9 large packages (torch, lightning, optuna, lightgbm, etc.)
- Created Alembic migration 0004 to drop Phase A tables
- Validated: `bitpredict smoke` passes, `/docs` shows only surviving endpoints

**Critical**: Backend still has phase A residue in code — logs, comments, variable names. Need varredura on Stage 7.

### Stage 2 ✅ Frontend Cleanup (2026-05-18)

**What was done:**
- Deleted 11 routes: `/predictions`, `/backtesting`, `/charts`, `/parameters`, `/training`, `/data`, `/alerts`, `/reports`, `/exports`, `/monitoring`
- Deleted 12 components from `components/dashboard/`
- Deleted 6 hooks: use-prediction, use-backtest, use-parameters, use-models, use-training, use-alerts
- Removed 8 API client methods: predictionsApi, backtestApi, parametersApi, trainingApi, alertsApi, modelsApi, reportsApi
- Sidebar minimized: only Home + RSI-2
- Placeholder `/`: "Kronos dashboard under construction"
- Validated: `localhost:3000` loads, `/rsi2` intact, `/` shows placeholder in English

### Stage 3 ✅ Kronos Backend — Multi-TF Engine (2026-05-18)

**What was done:**
- Created `backend/src/bitpredict/kronos/` module (6 files):
  - `loader.py` — loads Kronos + KronosTokenizer from `/app/data/kronos`, caches by variant
  - `inference.py` — `run_inference(timeframe, context_candles, sample_count, model_variant, temperature)` → OHLCV medians + Q10/Q90 + prob_bullish + raw_samples
  - `timeframes.py` — `Timeframe` enum (M15, H1, H4, H8, D1, W1) with methods for interval conversion, next boundary, backtest windows
  - `service.py` — orchestration: loads → infers → persists
  - `tasks.py` — Celery tasks `run_kronos_prediction(timeframe)` + `run_kronos_backtest(timeframe)` with progress callbacks
  - `backtest.py` — `select_sample_candles()`, `run_single_backtest_point()`, `aggregate_backtest_results()`
- Extended `data/historical.py` to accept `timeframe` parameter (ingest any TF: 15m/1h/4h/8h/1d/1w)
- Created Alembic migration 0005 + 0006 for `kronos_predictions` + `kronos_backtests` tables
- Added generic `ingest_klines(timeframe)` task to replace Phase A ingest
- Updated Celery beat schedule: 10 tasks running on cadence (15m predictions every 15min, 1h every hour, etc.)
- Celery queues: `predictions` (high priority) + `backtests` (low priority)
- Redis `visibility_timeout=21600` (6h) to support 2h+ backtests
- Validated: CLI runs predictions, scheduler active in Flower, backtest task persists results

### Stage 4 ✅ Kronos API — 9 Endpoints (2026-05-18)

**Endpoints:**
- `GET /kronos/prediction/{timeframe}` — active prediction (medians, Q10/Q90, prob_bullish, target_candle, model_variant)
- `GET /kronos/history/{timeframe}` — paginated prediction history + actual + error + direction
- `GET /kronos/backtest/{timeframe}` — most recent backtest metrics
- `GET /kronos/backtest/{timeframe}/history` — temporal evolution (Advanced mode)
- `GET /kronos/health` — aggregate status: worker state, last prediction/ingest per TF
- `POST /kronos/prediction/{timeframe}/trigger` — manual prediction (now)
- `POST /kronos/prediction/{timeframe}/stop` — soft-stop running task
- `POST /kronos/backtest/{timeframe}/trigger` — manual backtest
- `GET /kronos/progress/{timeframe}` — task state + progress (step, current/total, ETA, sim_current/sim_total)

**Schemas:** All Zod + Pydantic validated. Auth via existing API key dependency.

**Validated:** `/docs` shows all 9 endpoints, curl returns real data, status codes correct

### Stage 5 🟡 Kronos Frontend Dashboard (2026-05-19)

**Status:** Layout reorganization **JUST COMPLETED** 🎉

**What was done:**
- **Written** `analyst-distribution-chart.tsx` — SVG-based histogram (10 gradient buckets: red→emerald) + bezier smooth curve + Q10/Q90/median markers + summary stats row
- **Refactored** `prediction-panel.tsx` → two named exports:
  - `PriceTargetsCard` — Expected close (big), ConfidenceBadge, 80% range (Q10/Q90), OHLC grid
  - `ConsensusCard` — Direction arrow, % bullish/bearish (big), analyst count bar, analyst split bar (green/red halves), candle time progress bar + countdown
- **Updated** `page.tsx` — new two-column grid:
  - **Left column:** top 3-card row (PriceTargetsCard, ConsensusCard, LiveCandleCard) → AnalystDistributionChart (full width) → HistoryTable
  - **Right column (280px):** ScoreboardCard + Alerts placeholder
- All text in **English** (zero PT-BR outside `/rsi2`)

**Hooks:**
- `useCountdown(targetIso)` — countdown to target candle close
- `useCandleProgress(openIso, closeIso)` — fills progress bar as current candle progresses (uses live candle times)
- `useKronosLiveCandle(timeframe)` — fetches current candle data for progress bar

**Validated:** Dashboard renders, polling works, cards stack responsively, all data flowing from API

**Pending in Stage 5:**
- ~~Timeframe selector~~ (not implemented yet — only hardcoded 15m)
- ~~Advanced mode dialog~~ (not implemented yet)
- UI polish, tooltips review, edge cases (no data, loading states)

### Stage 6 🟡 Backtest Pipeline (PARTIAL)

**Status:** Backend ~90% done, frontend UI ~60% done.

**What exists:**
- `backend/kronos/backtest.py` — full pipeline: sample selection, inference replay, metrics aggregation
- `kronos_backtests` table with 20+ columns (metrics + portfolio params/results)
- Task `run_kronos_backtest(timeframe)` with progress tracking (sample + sim level)
- API endpoint `POST /kronos/backtest/{timeframe}/trigger` + `GET /kronos/backtest/{timeframe}`
- Frontend `/app/backtest/page.tsx` — RunCard (inputs), ResultsCard (metrics), HistoryTable
- High-confidence calibration metric: `high_conf_accuracy`, `high_conf_count` (≥70% confidence threshold)

**Pending:**
- Integrate backtest UI into main dashboard (currently separate `/backtest` page)
- Manual trigger modal on main dashboard (Advanced mode)
- Backtest schedule weekly refresh (Celery beat)
- `/kronos/backtest/{tf}/history` endpoint for Advanced mode

### Stage 7 ⏳ E2E Verification + Polish (NOT STARTED)

**Planned tasks:**
- Rich CLI smoke tests: `bitpredict smoke` + `bitpredict kronos smoke`
- API surface audit: `/docs` coverage, no Phase A residue
- Per-timeframe validation: ingest, prediction, stop, progress, backtest
- Frontend: all TFs selectable, chart updates, stop works, Advanced accessible
- Sidebar: English only (grep -r PT-BR outside /rsi2 → zero)
- Backend code scan: logs, comments, identifiers in English
- Docker stack: bring up cleanly, all services healthy
- Performance: base model predicts <10min for 1h TF
- Scripts: `kronos_test.py`, `kronos_realtime.py` still work

---

## Repository

📦 **Public GitHub:** [github.com/leopbar/bitPredict](https://github.com/leopbar/bitPredict)

Last commit: 2026-05-19 — Initial commit (169 files, all Stages 1–5 completed)

---

## Architecture Summary

### Backend Stack
- **Framework:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic
- **Model:** Kronos foundation model (102M params, frozen)
- **Inference:** 30 stochastic simulations per prediction (sample_count configurable)
- **Data:** Postgres + TimescaleDB, 6 timeframes (15m/1h/4h/8h/1d/1w)
- **Task queue:** Celery (Redis broker) + Beat scheduler
- **Logging:** structlog + Rich

### Frontend Stack
- **Framework:** Next.js 16 (App Router) + React 19 + TS 5
- **Styling:** Tailwind 4 + OKLCH zinc palette + shadcn/ui
- **Charts:** lightweight-charts (OHLC) + custom SVG (analyst distribution)
- **State:** TanStack Query v5 (server state) + React hooks (UI state)
- **Data validation:** Zod

### Language
- **Code, comments, identifiers, logs:** English
- **UI:** English (global), except `/rsi2` (Portuguese for RSI-2 strategy)
- **User interaction:** Portuguese (user's preference, documented in memory)

---

## Key Decisions (Validated)

1. **Kronos replaces Phase A** — single frozen model, 6 timeframes, no retraining = production-ready
2. **Stochastic confidence** — 30 simulations per candle yield natural Q10/Q90 bands (vs. learned quantile regression)
3. **Phase B untouched** — RSI-2 remains in production, all Portuguese, no interference
4. **6 timeframes** — 15m/1h/4h/8h/1d/1w UTC for analyst flexibility
5. **Backtest weekly** — escalonated Sunday refresh to avoid concurrent runs
6. **Named volumes** — OneDrive constraint: `node_modules`, `.next`, `venv` in Docker volumes (not synced)

