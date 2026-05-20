"""Optuna hyperparameter optimizer for Caminho A (pure rules)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import optuna
import polars as pl

from bitpredict.strategies.rsi2.config import Rsi2Params
from bitpredict.strategies.rsi2.engine import run_backtest
from bitpredict.strategies.rsi2.features import build_features, load_15m_parquet
from bitpredict.strategies.rsi2.metrics import composite_score
from bitpredict.strategies.rsi2.persistence import save_params_a
from bitpredict.strategies.rsi2.signals import generate_signals

logger = logging.getLogger(__name__)

# Training and validation periods
TRAIN_START = datetime(2018, 1, 1, tzinfo=UTC)
TRAIN_END = datetime(2024, 1, 1, tzinfo=UTC)
VAL_START = datetime(2024, 1, 1, tzinfo=UTC)
VAL_END = datetime(2025, 1, 1, tzinfo=UTC)

_OPTUNA_STUDY_PATH = Path("/app/data/models/rsi2/optuna_study.db")


def _slice_period(df: pl.DataFrame, start: datetime, end: datetime) -> pl.DataFrame:
    times = df["open_time"].to_list()
    keep = []
    for i, t in enumerate(times):
        t_aware = t.replace(tzinfo=UTC) if t.tzinfo is None else t
        if start <= t_aware < end:
            keep.append(i)
    if not keep:
        return df[:0]
    return df[keep[0] : keep[-1] + 1]


def _build_objective(
    train_df: pl.DataFrame,
    funding_series: list[tuple[datetime, float]],
) -> Callable[[optuna.Trial], float]:
    def objective(trial: optuna.Trial) -> float:
        params = Rsi2Params(
            # body filter is the key discriminant: 0.3-2% is the viable range
            body_min_pct=trial.suggest_float("body_min_pct", 0.3, 2.0),
            close_pos_min=trial.suggest_float("close_pos_min", 0.0, 0.8),
            stop_type=trial.suggest_categorical("stop_type", ["structural", "atr"]),
            stop_lookback=trial.suggest_int("stop_lookback", 3, 20),  # tight structural stops
            atr_k=trial.suggest_float("atr_k", 1.0, 2.5),
            # timeout is essential — cuts losing trades early; 8-32 bars shown effective
            timeout_bars=trial.suggest_categorical("timeout_bars", [8, 16, 24, 32]),
            # R=1.0-2.0; higher R + timeout gives asymmetric wins vs cuts
            target_r_multiple=trial.suggest_float("target_r_multiple", 1.0, 2.5),
        )

        try:
            signals = generate_signals(train_df, params)
            if len(signals) == 0:
                return 0.0
            result = run_backtest(train_df, signals, params, funding_series)
            score = composite_score(result)

            # Store extra metrics as user attributes for the trials table
            from bitpredict.strategies.rsi2.metrics import win_rate as _wr, profit_factor as _pf, calmar_ratio as _cr, _max_drawdown
            n = len(result.trades)
            wr = _wr(result.trades)
            pf = _pf(result.trades)
            calmar = _cr(result)
            max_dd = abs(_max_drawdown(result.equity)) * 100 if len(result.equity) else 0.0
            trial.set_user_attr("n_trades", n)
            trial.set_user_attr("win_rate", round(wr, 4))
            trial.set_user_attr("profit_factor", round(pf, 4))
            trial.set_user_attr("calmar", round(calmar, 4))
            trial.set_user_attr("max_dd_pct", round(max_dd, 4))

            return score
        except Exception as e:
            logger.debug("Trial %d failed: %s", trial.number, e)
            return 0.0

    return objective


def run_optimization(
    symbol: str = "BTCUSDT",
    n_trials: int = 500,
    data_dir: Path = Path("/app/data/raw"),
    funding_dir: Path = Path("/app/data/raw"),
    models_dir: Path = Path("/app/data/models/rsi2"),
    mlflow_experiment: str = "rsi2_optimization",
    progress_callback: Callable[[Any, Any, int, int], None] | None = None,
) -> Rsi2Params:
    """Run Optuna study, select best params on validation, save to disk."""
    import mlflow
    from bitpredict.config import get_settings
    from bitpredict.data.funding import load_funding

    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(mlflow_experiment)

    # Load and build features
    logger.info("Loading 15min klines...")
    raw_df = load_15m_parquet(symbol=symbol, data_dir=data_dir)
    feature_df = build_features(raw_df)
    logger.info("Feature DataFrame: %d rows", len(feature_df))

    # Load funding rates
    funding_df = load_funding(symbol=symbol, data_dir=funding_dir)
    funding_series: list[tuple[datetime, float]] = []
    if not funding_df.is_empty():
        for row in funding_df.iter_rows(named=True):
            ts = row["funding_time"]
            ts_aware = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
            funding_series.append((ts_aware, float(row["funding_rate"])))

    # Slice train period
    train_df = _slice_period(feature_df, TRAIN_START, TRAIN_END)
    val_df = _slice_period(feature_df, VAL_START, VAL_END)
    logger.info("Train: %d rows | Val: %d rows", len(train_df), len(val_df))

    # Create Optuna study — always fresh so n_trials is exactly what the user requested
    models_dir.mkdir(parents=True, exist_ok=True)
    if _OPTUNA_STUDY_PATH.exists():
        _OPTUNA_STUDY_PATH.unlink()
        logger.info("Deleted previous Optuna study to start fresh.")
    storage = f"sqlite:///{_OPTUNA_STUDY_PATH}"
    study = optuna.create_study(
        study_name="rsi2_caminho_a",
        storage=storage,
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    objective = _build_objective(train_df, funding_series)

    # Wrap callback to track count within THIS run only
    trials_done = [0]
    def _wrapped_cb(s: optuna.Study, t: optuna.trial.FrozenTrial) -> None:
        trials_done[0] += 1
        if progress_callback is not None:
            progress_callback(s, t, trials_done[0], n_trials)

    with mlflow.start_run(run_name="optuna_caminho_a"):
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True, callbacks=[_wrapped_cb])
        mlflow.log_param("n_trials", n_trials)
        mlflow.log_metric("best_train_score", study.best_value)

    logger.info("Best train score: %.4f", study.best_value)

    # Take top-10 by train score and re-evaluate on validation
    trials = sorted(study.trials, key=lambda t: t.value or 0.0, reverse=True)[:10]
    best_val_score = -1.0
    best_params: Rsi2Params | None = None

    for trial in trials:
        params = Rsi2Params(**{k: v for k, v in trial.params.items()})
        signals = generate_signals(val_df, params)
        if not signals:
            continue
        result = run_backtest(val_df, signals, params, funding_series)
        val_score = composite_score(result)
        logger.info(
            "Trial %d → val score=%.4f (train=%.4f)",
            trial.number, val_score, trial.value or 0.0,
        )
        if val_score > best_val_score:
            best_val_score = val_score
            best_params = params

    if best_params is None:
        logger.warning("No valid params found; using study best trial params")
        best_params = Rsi2Params(**{k: v for k, v in study.best_params.items()})

    out = save_params_a(best_params, models_dir)
    logger.info("Best params saved to %s (val score=%.4f)", out, best_val_score)
    return best_params
