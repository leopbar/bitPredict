"""FastAPI router for RSI-2 strategy endpoints."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rsi2", tags=["RSI-2 Strategy"])

_MODELS_DIR = Path("/app/data/models/rsi2")
_DATA_DIR = Path("/app/data/raw")

# ---------------------------------------------------------------------------
# In-memory job store (same pattern as training.py)
# ---------------------------------------------------------------------------

_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()
_SEMAPHORE = threading.Semaphore(1)  # one RSI-2 job at a time


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------


class Rsi2SignalResponse(BaseModel):
    side: str
    entry_price: float | None
    stop_price: float | None
    rsi2_value: float | None
    meta_proba: float | None
    signal_time: datetime
    params_version: str
    reason: str


class Rsi2TradeHistoryItem(BaseModel):
    entry_time: datetime
    exit_time: datetime
    side: str
    entry_price: float
    exit_price: float
    stop_price: float
    gross_pnl_pct: float
    net_pnl_pct: float
    exit_reason: str
    bars_held: int


class Rsi2MetricsResponse(BaseModel):
    exists: bool
    winner: str | None
    score_a_validation: float | None
    score_b_validation: float | None
    sealed_report: dict[str, Any] | None


class Rsi2JobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    message: str


class Rsi2JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress: float
    message: str


class Rsi2JobResultResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    result: dict[str, Any] | None
    error: str | None


class OptimizeRequest(BaseModel):
    n_trials: int = 500


class SealedTestRequest(BaseModel):
    force: bool = False


# ---------------------------------------------------------------------------
# Job runner helpers
# ---------------------------------------------------------------------------


def _make_job(job_type: str) -> tuple[str, dict[str, Any]]:
    job_id = str(uuid.uuid4())
    job: dict[str, Any] = {
        "job_type": job_type,
        "status": "queued",
        "progress": 0.0,
        "message": "Na fila...",
        "result": None,
        "error": None,
        "created_at": datetime.now(tz=UTC).isoformat(),
    }
    return job_id, job


def _update(job_id: str, **kwargs: Any) -> None:
    with _LOCK:
        for k, v in kwargs.items():
            _JOBS[job_id][k] = v


def _acquire_or_fail(job_id: str) -> bool:
    acquired = _SEMAPHORE.acquire(blocking=False)
    if not acquired:
        with _LOCK:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["error"] = (
                "Outro job RSI-2 está em andamento. Aguarde e tente novamente."
            )
        return False
    return True


# ---------------------------------------------------------------------------
# Ingest job
# ---------------------------------------------------------------------------


def _run_ingest_job(job_id: str) -> None:
    if not _acquire_or_fail(job_id):
        return
    try:
        _run_ingest_inner(job_id)
    finally:
        _SEMAPHORE.release()


def _run_ingest_inner(job_id: str) -> None:
    import asyncio
    from datetime import timedelta

    import polars as pl

    from bitpredict.data.binance_client import BinanceClient
    from bitpredict.data.funding import download_funding_history

    _update(job_id, status="running", progress=0.02, message="Iniciando download de klines 15min...")

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)

    symbol = "BTCUSDT"
    interval = "15m"
    interval_delta = timedelta(minutes=15)
    max_per_page = 1000
    out_path = _DATA_DIR / f"{symbol.lower()}_{interval}.parquet"

    _SCHEMA = {
        "open_time": pl.Datetime("us", "UTC"),
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "volume": pl.Float64,
        "close_time": pl.Datetime("us", "UTC"),
        "quote_volume": pl.Float64,
        "trades": pl.Int64,
        "taker_buy_base": pl.Float64,
        "taker_buy_quote": pl.Float64,
    }

    def _raw_to_row(raw: list) -> dict:
        return {
            "open_time": datetime.fromtimestamp(raw[0] / 1000, tz=UTC),
            "open": float(raw[1]),
            "high": float(raw[2]),
            "low": float(raw[3]),
            "close": float(raw[4]),
            "volume": float(raw[5]),
            "close_time": datetime.fromtimestamp(raw[6] / 1000, tz=UTC),
            "quote_volume": float(raw[7]),
            "trades": int(raw[8]),
            "taker_buy_base": float(raw[9]),
            "taker_buy_quote": float(raw[10]),
        }

    async def _download_15m(start: datetime, end: datetime) -> pl.DataFrame:
        frames: list[pl.DataFrame] = []
        current_start = start
        page = 0

        async with BinanceClient() as client:
            while current_start < end:
                raw = await client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    start_time=current_start,
                    end_time=end,
                    limit=max_per_page,
                )
                if not raw:
                    break

                rows = [_raw_to_row(r) for r in raw]
                frames.append(pl.DataFrame(rows, schema=_SCHEMA))
                page += 1
                total_rows = sum(len(f) for f in frames)

                _update(
                    job_id,
                    message=f"Klines 15min: página {page} ({total_rows:,} linhas)...",
                    progress=min(0.5, 0.02 + page * 0.005),
                )

                last_ts: datetime = rows[-1]["open_time"]
                next_start = last_ts + interval_delta
                if next_start >= end or len(raw) < max_per_page:
                    break
                current_start = next_start

        if not frames:
            return pl.DataFrame(schema=_SCHEMA)

        result = pl.concat(frames)
        timestamps = result["open_time"].to_list()
        epoch_us = [int(ts.timestamp() * 1_000_000) for ts in timestamps]
        seen: set[int] = set()
        keep: list[int] = []
        for idx in sorted(range(len(epoch_us)), key=lambda i: epoch_us[i]):
            if epoch_us[idx] not in seen:
                seen.add(epoch_us[idx])
                keep.append(idx)
        return result[keep]

    # Determine start point (resume if data exists)
    start_15m = datetime(2018, 1, 1, tzinfo=UTC)
    end_15m = datetime.now(tz=UTC)
    existing = pl.DataFrame(schema=_SCHEMA)

    if out_path.exists():
        try:
            existing = pl.read_parquet(out_path)
            times = existing["open_time"].to_list()
            if times:
                last_ts = max(t.replace(tzinfo=UTC) if t.tzinfo is None else t for t in times)
                start_15m = last_ts + interval_delta
                _update(job_id, message=f"Retomando de {start_15m.date().isoformat()}...")
        except Exception:
            pass

    # Download klines
    try:
        new_df = asyncio.run(_download_15m(start_15m, end_15m))
    except Exception as e:
        logger.exception("15min klines download failed")
        _update(job_id, status="failed", error=f"Erro no download de klines: {e}")
        return

    total_rows = 0
    if not new_df.is_empty():
        if not existing.is_empty():
            combined = pl.concat([existing, new_df])
            timestamps_all = combined["open_time"].to_list()
            epoch_us = [int(t.timestamp() * 1_000_000) for t in timestamps_all]
            seen2: set[int] = set()
            keep2: list[int] = []
            for idx in sorted(range(len(epoch_us)), key=lambda i: epoch_us[i]):
                if epoch_us[idx] not in seen2:
                    seen2.add(epoch_us[idx])
                    keep2.append(idx)
            combined = combined[keep2]
        else:
            combined = new_df
        tmp_path = out_path.with_suffix(".tmp")
        combined.write_parquet(tmp_path)
        tmp_path.replace(out_path)  # atomic rename — prevents corrupt reads
        total_rows = len(combined)
        _update(job_id, progress=0.6, message=f"✓ Klines 15min: {total_rows:,} linhas salvas. Baixando funding rates...")
    else:
        total_rows = len(existing)
        _update(job_id, progress=0.6, message="Sem novos dados de klines. Baixando funding rates...")

    # Download funding rates
    async def _do_funding() -> int:
        funding_df = await download_funding_history(symbol=symbol, data_dir=_DATA_DIR)
        return len(funding_df)

    funding_count = 0
    try:
        funding_count = asyncio.run(_do_funding())
        _update(job_id, progress=0.9, message=f"✓ Funding rates: {funding_count:,} entradas")
    except Exception as e:
        logger.warning("Funding download failed: %s", e)
        _update(job_id, progress=0.9, message=f"⚠ Funding rates falhou: {e} (continuando sem funding)")

    _update(
        job_id,
        status="done",
        progress=1.0,
        message=f"✓ Ingestão completa — {total_rows:,} klines, {funding_count:,} funding rates",
        result={"klines_rows": total_rows, "funding_rows": funding_count, "symbol": symbol, "interval": interval},
    )


# ---------------------------------------------------------------------------
# Optimize job (Caminho A — Optuna)
# ---------------------------------------------------------------------------


def _run_optimize_job(job_id: str, n_trials: int) -> None:
    if not _acquire_or_fail(job_id):
        return
    try:
        _run_optimize_inner(job_id, n_trials)
    finally:
        _SEMAPHORE.release()


def _run_optimize_inner(job_id: str, n_trials: int) -> None:
    from bitpredict.strategies.rsi2.optimizer import run_optimization

    _update(job_id, status="running", progress=0.02, message=f"Carregando dados para otimização ({n_trials} trials)...")

    def _progress_cb(study: Any, trial: Any, done: int, total: int) -> None:
        pct = done / total
        best = study.best_value if study.best_value > 0 else 0.0
        _update(
            job_id,
            progress=max(0.02, pct * 0.85),  # 0–85% for trials; 85–100% for val selection
            message=f"Trial {done}/{total} ({pct:.0%}) — melhor score: {best:.4f}",
        )

    try:
        best_params = run_optimization(
            symbol="BTCUSDT",
            n_trials=n_trials,
            data_dir=_DATA_DIR,
            funding_dir=_DATA_DIR,
            models_dir=_MODELS_DIR,
            progress_callback=_progress_cb,
        )
        _update(
            job_id,
            status="done",
            progress=1.0,
            message=f"✓ Otimização concluída — {n_trials} trials",
            result=best_params.model_dump(),
        )
    except FileNotFoundError as e:
        _update(job_id, status="failed", error=f"Dados não encontrados: {e}. Execute a ingestão primeiro.")
    except Exception as e:
        logger.exception("Optimize job failed")
        _update(job_id, status="failed", error=str(e))


# ---------------------------------------------------------------------------
# Train meta job (Caminho B — XGBoost)
# ---------------------------------------------------------------------------


def _run_train_meta_job(job_id: str) -> None:
    if not _acquire_or_fail(job_id):
        return
    try:
        _run_train_meta_inner(job_id)
    finally:
        _SEMAPHORE.release()


def _run_train_meta_inner(job_id: str) -> None:
    from bitpredict.strategies.rsi2.meta_labeling import train_meta_model

    _update(job_id, status="running", progress=0.02, message="Iniciando treinamento do modelo XGBoost (Caminho B)...")

    def _progress_cb(pct: float, msg: str) -> None:
        _update(job_id, progress=pct, message=msg)

    try:
        train_roc_auc, val_score, best_threshold = train_meta_model(
            symbol="BTCUSDT",
            data_dir=_DATA_DIR,
            funding_dir=_DATA_DIR,
            models_dir=_MODELS_DIR,
            progress_callback=_progress_cb,
        )
        _update(
            job_id,
            status="done",
            progress=1.0,
            message=f"✓ Caminho B treinado — AUC: {train_roc_auc:.3f} | score val: {val_score:.4f} | threshold: {best_threshold:.2f}",
            result={"roc_auc": train_roc_auc, "val_score_b": val_score, "threshold": best_threshold},
        )
    except FileNotFoundError as e:
        _update(job_id, status="failed", error=f"Parâmetros não encontrados: {e}. Execute a otimização primeiro.")
    except Exception as e:
        logger.exception("Train meta job failed")
        _update(job_id, status="failed", error=str(e))


# ---------------------------------------------------------------------------
# Select winner job (A vs A+B)
# ---------------------------------------------------------------------------


def _run_select_job(job_id: str) -> None:
    if not _acquire_or_fail(job_id):
        return
    try:
        _run_select_inner(job_id)
    finally:
        _SEMAPHORE.release()


def _run_select_inner(job_id: str) -> None:
    from bitpredict.strategies.rsi2.selector import select_winner

    _update(job_id, status="running", progress=0.02, message="Iniciando comparação Caminho A vs A+B...")

    def _progress_cb(pct: float, msg: str) -> None:
        _update(job_id, progress=pct, message=msg)

    try:
        winner = select_winner(
            symbol="BTCUSDT",
            data_dir=_DATA_DIR,
            funding_dir=_DATA_DIR,
            models_dir=_MODELS_DIR,
            progress_callback=_progress_cb,
        )
        import json
        winner_data = json.loads((_MODELS_DIR / "winner.json").read_text()) if (_MODELS_DIR / "winner.json").exists() else {}
        score_a = winner_data.get("score_a_validation", 0.0)
        score_b = winner_data.get("score_b_validation")
        _update(
            job_id,
            status="done",
            progress=1.0,
            message=f"✓ Winner selecionado: Caminho {winner} (A={score_a:.4f}" + (f" | A+B={score_b:.4f}" if score_b else "") + ")",
            result={"winner": winner, "val_score_a": score_a, "val_score_b": score_b},
        )
    except FileNotFoundError as e:
        _update(job_id, status="failed", error=f"Arquivos não encontrados: {e}. Execute a otimização primeiro.")
    except Exception as e:
        logger.exception("Select winner job failed")
        _update(job_id, status="failed", error=str(e))


# ---------------------------------------------------------------------------
# Sealed test job
# ---------------------------------------------------------------------------


def _run_sealed_test_job(job_id: str, force: bool) -> None:
    if not _acquire_or_fail(job_id):
        return
    try:
        _run_sealed_test_inner(job_id, force)
    finally:
        _SEMAPHORE.release()


def _run_sealed_test_inner(job_id: str, force: bool) -> None:
    import json

    from bitpredict.data.funding import load_funding
    from bitpredict.strategies.rsi2.engine import run_backtest
    from bitpredict.strategies.rsi2.features import build_features, load_15m_parquet
    from bitpredict.strategies.rsi2.meta_labeling import _build_feature_matrix
    from bitpredict.strategies.rsi2.metrics import full_report
    from bitpredict.strategies.rsi2.optimizer import _slice_period
    from bitpredict.strategies.rsi2.persistence import load_model_b, load_params_a, load_winner, save_sealed_report
    from bitpredict.strategies.rsi2.signals import generate_signals

    report_path = _MODELS_DIR / "sealed_test_report.json"

    if report_path.exists() and not force:
        existing_report = json.loads(report_path.read_text())
        _update(
            job_id,
            status="done",
            progress=1.0,
            message="✓ Teste lacrado já executado. Use force=true para re-executar.",
            result=existing_report,
        )
        return

    _update(job_id, status="running", progress=0.05, message="Carregando configuração do winner...")

    try:
        winner_info = load_winner(_MODELS_DIR)
        winner = winner_info["winner"]
    except FileNotFoundError as e:
        _update(job_id, status="failed", error=f"winner.json não encontrado: {e}. Execute a seleção primeiro.")
        return

    test_start = datetime(2025, 1, 1, tzinfo=UTC)
    test_end = datetime.now(tz=UTC)

    _update(job_id, progress=0.1, message=f"Carregando dados de {test_start.date()} → {test_end.date()}...")

    try:
        params_a = load_params_a(_MODELS_DIR)
        raw_df = load_15m_parquet(symbol="BTCUSDT", data_dir=_DATA_DIR)
        feature_df = build_features(raw_df)
        test_df = _slice_period(feature_df, test_start, test_end)
    except Exception as e:
        _update(job_id, status="failed", error=f"Erro ao carregar dados: {e}")
        return

    _update(job_id, progress=0.3, message=f"Dados: {len(test_df):,} barras. Carregando funding rates...")

    funding_df = load_funding(symbol="BTCUSDT", data_dir=_DATA_DIR)
    funding_series: list[tuple[datetime, float]] = []
    if not funding_df.is_empty():
        for row in funding_df.iter_rows(named=True):
            ts = row["funding_time"]
            ts_aware = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
            funding_series.append((ts_aware, float(row["funding_rate"])))

    _update(job_id, progress=0.4, message="Gerando sinais...")

    signals = generate_signals(test_df, params_a)
    meta_mask = None

    if winner == "A+B":
        _update(job_id, progress=0.5, message="Aplicando filtro Caminho B...")
        model_b, threshold = load_model_b(_MODELS_DIR)
        if model_b is not None:
            df_rows = test_df.to_dicts()
            X_test = _build_feature_matrix(signals, feature_df, df_rows)
            probas = model_b.predict_proba(X_test)[:, 1]
            meta_mask = [float(p) >= (threshold or 0.55) for p in probas]

    _update(job_id, progress=0.7, message="Executando backtest no período lacrado...")

    result = run_backtest(test_df, signals, params_a, funding_series, meta_mask=meta_mask)

    _update(job_id, progress=0.9, message="Calculando métricas e salvando relatório...")

    report = full_report(result)
    report["period_start"] = str(test_start.date())
    report["period_end"] = str(test_end.date())
    report["winner"] = winner
    report["n_signals_generated"] = len(signals)
    report["n_signals_after_filter"] = sum(meta_mask) if meta_mask else len(signals)
    report["equity_final"] = round(float(result.equity[-1]), 6) if len(result.equity) > 0 else 1.0
    # aliases for frontend display
    report["calmar"] = report.get("calmar_ratio", 0.0)
    report["max_drawdown"] = report.get("max_drawdown_pct", 0.0) / 100

    save_sealed_report(report, _MODELS_DIR)

    _update(
        job_id,
        status="done",
        progress=1.0,
        message=f"✓ Teste lacrado completo — {len(result.trades)} trades, winner={winner}",
        result=report,
    )


# ---------------------------------------------------------------------------
# Data query endpoints (reads directly from Parquet, no DB required)
# ---------------------------------------------------------------------------


class Kline15mItem(BaseModel):
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Kline15mInfoResponse(BaseModel):
    total_rows: int
    first_open_time: datetime | None
    last_open_time: datetime | None
    symbol: str
    interval: str
    parquet_exists: bool
    gap_count: int
    missing_candles: int


@router.get("/data/info", response_model=Kline15mInfoResponse)
async def get_data_info(symbol: str = Query(default="BTCUSDT")) -> Kline15mInfoResponse:
    """Return summary stats for the 15min Parquet dataset."""
    path = _DATA_DIR / f"{symbol.lower()}_15m.parquet"
    if not path.exists():
        return Kline15mInfoResponse(
            total_rows=0,
            first_open_time=None,
            last_open_time=None,
            symbol=symbol,
            interval="15m",
            parquet_exists=False,
            gap_count=0,
            missing_candles=0,
        )

    import polars as pl
    from datetime import timedelta

    df = pl.read_parquet(path, columns=["open_time"])
    times = df["open_time"].to_list()
    if not times:
        return Kline15mInfoResponse(
            total_rows=0,
            first_open_time=None,
            last_open_time=None,
            symbol=symbol,
            interval="15m",
            parquet_exists=True,
            gap_count=0,
            missing_candles=0,
        )

    times_aware = [t.replace(tzinfo=UTC) if t.tzinfo is None else t for t in times]
    times_sorted = sorted(times_aware)
    delta = timedelta(minutes=15)
    gap_count = 0
    missing_candles = 0
    for i in range(1, len(times_sorted)):
        diff = times_sorted[i] - times_sorted[i - 1]
        if diff > delta * 1.5:
            gap_count += 1
            missing_candles += int(diff / delta) - 1

    return Kline15mInfoResponse(
        total_rows=len(times),
        first_open_time=times_sorted[0],
        last_open_time=times_sorted[-1],
        symbol=symbol,
        interval="15m",
        parquet_exists=True,
        gap_count=gap_count,
        missing_candles=missing_candles,
    )


@router.get("/data/klines", response_model=list[Kline15mItem])
async def get_15m_klines(
    symbol: str = Query(default="BTCUSDT"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[Kline15mItem]:
    """Return 15min OHLCV candles from the Parquet file."""
    from datetime import timedelta

    import polars as pl

    path = _DATA_DIR / f"{symbol.lower()}_15m.parquet"
    if not path.exists():
        raise HTTPException(status_code=404, detail="15min data not found. Run ingestion first.")

    df = pl.read_parquet(path, columns=["open_time", "open", "high", "low", "close", "volume"])

    if end is None:
        end = datetime.now(tz=UTC)
    if start is None:
        start = end - timedelta(minutes=15 * limit)

    # Filter by date range (Python-level to avoid timezone issues on Windows)
    rows_out: list[Kline15mItem] = []
    for row in df.iter_rows(named=True):
        ts = row["open_time"]
        ts_aware = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
        if start <= ts_aware <= end:
            rows_out.append(
                Kline15mItem(
                    open_time=ts_aware,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )

    # Return the last `limit` rows in the filtered window
    return rows_out[-limit:]


# ---------------------------------------------------------------------------
# Signal and history endpoints
# ---------------------------------------------------------------------------


@router.get("/signal", response_model=Rsi2SignalResponse)
async def get_current_signal() -> Rsi2SignalResponse:
    """Return the RSI-2 signal for the current (latest completed) 15min bar."""
    try:
        from bitpredict.strategies.rsi2.inference import run_inference
        result = run_inference(models_dir=_MODELS_DIR, data_dir=_DATA_DIR)
        return Rsi2SignalResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")


@router.get("/history", response_model=list[Rsi2SignalResponse])
async def get_signal_history(limit: int = 50) -> list[Rsi2SignalResponse]:
    """Return recent RSI-2 signals from the database."""
    try:
        from sqlalchemy import select, desc
        from bitpredict.db import get_session
        from bitpredict.db_models import Rsi2Signal

        db = get_session()
        try:
            rows = (
                db.execute(
                    select(Rsi2Signal)
                    .order_by(desc(Rsi2Signal.signal_time))
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [
                Rsi2SignalResponse(
                    side=r.side,
                    entry_price=float(r.entry_price) if r.entry_price is not None else None,
                    stop_price=float(r.stop_price) if r.stop_price is not None else None,
                    rsi2_value=float(r.rsi2_value) if r.rsi2_value is not None else None,
                    meta_proba=float(r.meta_proba) if r.meta_proba is not None else None,
                    signal_time=r.signal_time,
                    params_version=r.params_version,
                    reason="",
                )
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades", response_model=list[Rsi2TradeHistoryItem])
async def get_trade_history(limit: int = 100) -> list[Rsi2TradeHistoryItem]:
    """Return completed RSI-2 trades from the database."""
    try:
        from sqlalchemy import select, desc
        from bitpredict.db import get_session
        from bitpredict.db_models import Rsi2Trade

        db = get_session()
        try:
            rows = (
                db.execute(
                    select(Rsi2Trade)
                    .order_by(desc(Rsi2Trade.entry_time))
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [
                Rsi2TradeHistoryItem(
                    entry_time=r.entry_time,
                    exit_time=r.exit_time,
                    side=r.side,
                    entry_price=float(r.entry_price),
                    exit_price=float(r.exit_price),
                    stop_price=float(r.stop_price),
                    gross_pnl_pct=float(r.gross_pnl_pct),
                    net_pnl_pct=float(r.net_pnl_pct),
                    exit_reason=r.exit_reason,
                    bars_held=r.bars_held,
                )
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/params")
async def get_params() -> dict:
    """Return current best strategy parameters."""
    try:
        from bitpredict.strategies.rsi2.persistence import load_params_a
        params = load_params_a(_MODELS_DIR)
        return params.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No optimized params found. Run optimization first.")


@router.get("/metrics", response_model=Rsi2MetricsResponse)
async def get_metrics() -> Rsi2MetricsResponse:
    """Return optimization results and sealed test report if available."""
    import json

    winner_path = _MODELS_DIR / "winner.json"
    sealed_path = _MODELS_DIR / "sealed_test_report.json"

    winner_data: dict = {}
    sealed_data: dict | None = None

    if winner_path.exists():
        winner_data = json.loads(winner_path.read_text())
    if sealed_path.exists():
        sealed_data = json.loads(sealed_path.read_text())

    return Rsi2MetricsResponse(
        exists=winner_path.exists(),
        winner=winner_data.get("winner"),
        score_a_validation=winner_data.get("score_a_validation"),
        score_b_validation=winner_data.get("score_b_validation"),
        sealed_report=sealed_data,
    )


# ---------------------------------------------------------------------------
# Job management endpoints
# ---------------------------------------------------------------------------


@router.post("/jobs/ingest", response_model=Rsi2JobResponse, status_code=202)
def start_ingest(background_tasks: BackgroundTasks) -> Rsi2JobResponse:
    """Start a background job to download/update 15min klines + funding rates."""
    job_id, job = _make_job("ingest")
    with _LOCK:
        _JOBS[job_id] = job
    background_tasks.add_task(_run_ingest_job, job_id)
    return Rsi2JobResponse(
        job_id=job_id,
        job_type="ingest",
        status="queued",
        message="Job de ingestão enviado com sucesso",
    )


@router.post("/jobs/optimize", response_model=Rsi2JobResponse, status_code=202)
def start_optimize(body: OptimizeRequest, background_tasks: BackgroundTasks) -> Rsi2JobResponse:
    """Start Optuna hyperparameter optimization (Caminho A)."""
    job_id, job = _make_job("optimize")
    with _LOCK:
        _JOBS[job_id] = job
    background_tasks.add_task(_run_optimize_job, job_id, body.n_trials)
    return Rsi2JobResponse(
        job_id=job_id,
        job_type="optimize",
        status="queued",
        message=f"Otimização com {body.n_trials} trials enviada",
    )


@router.post("/jobs/train-meta", response_model=Rsi2JobResponse, status_code=202)
def start_train_meta(background_tasks: BackgroundTasks) -> Rsi2JobResponse:
    """Train the XGBoost meta-labeling model (Caminho B)."""
    job_id, job = _make_job("train-meta")
    with _LOCK:
        _JOBS[job_id] = job
    background_tasks.add_task(_run_train_meta_job, job_id)
    return Rsi2JobResponse(
        job_id=job_id,
        job_type="train-meta",
        status="queued",
        message="Treinamento do modelo XGBoost enviado",
    )


@router.post("/jobs/select", response_model=Rsi2JobResponse, status_code=202)
def start_select(background_tasks: BackgroundTasks) -> Rsi2JobResponse:
    """Compare Caminho A vs A+B on validation and select the winner."""
    job_id, job = _make_job("select")
    with _LOCK:
        _JOBS[job_id] = job
    background_tasks.add_task(_run_select_job, job_id)
    return Rsi2JobResponse(
        job_id=job_id,
        job_type="select",
        status="queued",
        message="Seleção de winner enviada",
    )


@router.post("/jobs/sealed-test", response_model=Rsi2JobResponse, status_code=202)
def start_sealed_test(body: SealedTestRequest, background_tasks: BackgroundTasks) -> Rsi2JobResponse:
    """Run the sealed test (2025-01-01 → today). Irreversible by convention."""
    job_id, job = _make_job("sealed-test")
    with _LOCK:
        _JOBS[job_id] = job
    background_tasks.add_task(_run_sealed_test_job, job_id, body.force)
    return Rsi2JobResponse(
        job_id=job_id,
        job_type="sealed-test",
        status="queued",
        message="Teste lacrado enviado" + (" (forçado)" if body.force else ""),
    )


def _disk_fallback_jobs() -> dict[str, dict[str, Any]]:
    """Synthesize 'done' job entries from disk artifacts for jobs not in memory."""
    import json as _json

    fallback: dict[str, dict[str, Any]] = {}

    # optimize → best_params_A.json
    params_path = _MODELS_DIR / "best_params_A.json"
    if params_path.exists():
        try:
            params_data = _json.loads(params_path.read_text())
            fallback["optimize"] = {
                "job_id": "disk-optimize",
                "job_type": "optimize",
                "status": "done",
                "progress": 1.0,
                "message": "✓ Parâmetros carregados do disco",
                "error": None,
                "created_at": "",
                "result": params_data,
            }
        except Exception:
            pass

    # train-meta → best_threshold.json
    threshold_path = _MODELS_DIR / "best_threshold.json"
    if threshold_path.exists():
        try:
            thr_data = _json.loads(threshold_path.read_text())
            fallback["train-meta"] = {
                "job_id": "disk-train-meta",
                "job_type": "train-meta",
                "status": "done",
                "progress": 1.0,
                "message": "✓ Modelo Caminho B carregado do disco",
                "error": None,
                "created_at": "",
                "result": {"roc_auc": None, "val_score_b": None, "threshold": thr_data.get("threshold")},
            }
        except Exception:
            pass

    # select → winner.json
    winner_path = _MODELS_DIR / "winner.json"
    if winner_path.exists():
        try:
            w = _json.loads(winner_path.read_text())
            score_a = w.get("score_a_validation", 0.0)
            score_b = w.get("score_b_validation")
            winner = w.get("winner", "A")
            msg = f"✓ Winner selecionado: Caminho {winner} (A={score_a:.4f}" + (f" | A+B={score_b:.4f}" if score_b else "") + ")"
            fallback["select"] = {
                "job_id": "disk-select",
                "job_type": "select",
                "status": "done",
                "progress": 1.0,
                "message": msg,
                "error": None,
                "created_at": "",
                "result": {"winner": winner, "val_score_a": score_a, "val_score_b": score_b},
            }
        except Exception:
            pass

    # sealed-test → sealed_test_report.json
    sealed_path = _MODELS_DIR / "sealed_test_report.json"
    if sealed_path.exists():
        try:
            report = _json.loads(sealed_path.read_text())
            n_trades = report.get("n_trades", 0)
            winner = report.get("winner", "A")
            fallback["sealed-test"] = {
                "job_id": "disk-sealed-test",
                "job_type": "sealed-test",
                "status": "done",
                "progress": 1.0,
                "message": f"✓ Teste lacrado completo — {n_trades} trades, winner={winner}",
                "error": None,
                "created_at": "",
                "result": report,
            }
        except Exception:
            pass

    return fallback


@router.get("/trials")
def get_trials() -> dict:
    """Return all Optuna trials from the last optimization run, sorted by composite score."""
    study_path = _MODELS_DIR / "optuna_study.db"
    if not study_path.exists():
        raise HTTPException(status_code=404, detail="Nenhum estudo Optuna encontrado. Execute a otimização primeiro.")

    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        storage = f"sqlite:///{study_path}"
        study = optuna.load_study(study_name="rsi2_caminho_a", storage=storage)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar estudo Optuna: {e}")

    rows = []
    for t in study.trials:
        if t.value is None:
            continue
        row: dict[str, Any] = {
            "trial": t.number,
            "score": round(t.value, 4),
            # params
            "body_min_pct": round(t.params.get("body_min_pct", 0), 3),
            "close_pos_min": round(t.params.get("close_pos_min", 0), 3),
            "stop_type": t.params.get("stop_type", ""),
            "stop_lookback": t.params.get("stop_lookback"),
            "atr_k": round(t.params.get("atr_k", 0), 2),
            "timeout_bars": t.params.get("timeout_bars"),
            "target_r_multiple": round(t.params.get("target_r_multiple", 0), 2),
            # user attrs (only present for runs after this feature was added)
            "n_trades": t.user_attrs.get("n_trades"),
            "win_rate": t.user_attrs.get("win_rate"),
            "profit_factor": t.user_attrs.get("profit_factor"),
            "calmar": t.user_attrs.get("calmar"),
            "max_dd_pct": t.user_attrs.get("max_dd_pct"),
        }
        rows.append(row)

    rows.sort(key=lambda r: r["score"], reverse=True)
    return {"total": len(rows), "trials": rows}


@router.get("/jobs/recent")
def get_recent_jobs() -> dict[str, Any]:
    """Return the most recent job per type (any status). Used by the frontend to restore state on page refresh.
    Falls back to disk artifacts when the backend was restarted and _JOBS is empty."""
    with _LOCK:
        by_type: dict[str, dict[str, Any]] = {}
        for jid, j in _JOBS.items():
            jtype = j["job_type"]
            if jtype not in by_type or j.get("created_at", "") > by_type[jtype].get("created_at", ""):
                by_type[jtype] = {"job_id": jid, **j}

    # Fill missing job types from disk artifacts
    disk_jobs = _disk_fallback_jobs()
    for jtype, disk_job in disk_jobs.items():
        if jtype not in by_type:
            by_type[jtype] = disk_job

    return by_type


@router.get("/jobs/active")
def get_active_jobs() -> dict[str, Any]:
    """Return all currently queued or running RSI-2 jobs."""
    with _LOCK:
        running = [
            {"job_id": jid, **{k: v for k, v in j.items() if k != "result"}}
            for jid, j in _JOBS.items()
            if j["status"] in ("queued", "running")
        ]
    return {"running": len(running) > 0, "jobs": running}


@router.get("/jobs/{job_id}/status", response_model=Rsi2JobStatusResponse)
def get_job_status(job_id: str) -> Rsi2JobStatusResponse:
    """Poll the status of a RSI-2 job."""
    with _LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return Rsi2JobStatusResponse(
        job_id=job_id,
        job_type=job["job_type"],
        status=job["status"],
        progress=job.get("progress", 0.0),
        message=job.get("message", ""),
    )


@router.get("/jobs/{job_id}/results", response_model=Rsi2JobResultResponse)
def get_job_results(job_id: str) -> Rsi2JobResultResponse:
    """Retrieve completed results of a RSI-2 job."""
    with _LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] in ("queued", "running"):
        raise HTTPException(status_code=409, detail=f"Job ainda em execução: {job['status']}")
    return Rsi2JobResultResponse(
        job_id=job_id,
        job_type=job["job_type"],
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
    )
