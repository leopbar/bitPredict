"""Caminho B: XGBoost meta-labeling classifier with Purged K-Fold + embargo."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import numpy as np
import polars as pl
from sklearn.metrics import roc_auc_score

from bitpredict.strategies.rsi2.config import Rsi2MetaParams, Rsi2Params
from bitpredict.strategies.rsi2.engine import BacktestResult, TradeResult, run_backtest
from bitpredict.strategies.rsi2.features import build_features, load_15m_parquet
from bitpredict.strategies.rsi2.metrics import composite_score
from bitpredict.strategies.rsi2.optimizer import TRAIN_END, TRAIN_START, VAL_END, VAL_START, _slice_period
from bitpredict.strategies.rsi2.persistence import load_params_a, save_model_b
from bitpredict.strategies.rsi2.signals import SignalRow, generate_signals

logger = logging.getLogger(__name__)

# Context features used by the meta-learner
_META_FEATURES = [
    "hour_utc",
    "weekday",
    "atr_pct",
    "vol_relative",
    "ema50_slope_5",
    "ema200_slope_5",
    "price_vs_ema50_pct",
    "price_vs_ema200_pct",
    "rsi_2_prev",
    "body_pct",
    "close_pos",
]


def _build_feature_matrix(
    signals: list[SignalRow],
    feature_df: pl.DataFrame,
    df_rows: list[dict],
) -> np.ndarray:
    """Build (n_signals, n_features) matrix from signal bar_indices."""
    n_features = len(_META_FEATURES)
    X = np.zeros((len(signals), n_features), dtype=np.float32)

    for i, sig in enumerate(signals):
        row = df_rows[sig.bar_index]
        for j, feat in enumerate(_META_FEATURES):
            val = row.get(feat)
            X[i, j] = float(val) if val is not None else 0.0

        # Add side as binary feature (long=1, short=0)
        # Append it by extending the last dimension via direction
        # (direction already encoded via body_pct sign, but explicit is cleaner)

    # Append direction column
    direction = np.array([[1.0 if s.side == "long" else 0.0] for s in signals], dtype=np.float32)
    return np.hstack([X, direction])


def _purged_kfold_splits(
    signals: list[SignalRow],
    n_folds: int,
    embargo_bars: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Generate train/test index arrays with purging and embargo.

    Signals are already ordered by bar_index. We split them into n_folds
    chronological folds. For each fold used as test:
    - Training signals whose bar_index overlaps with the test period (within embargo)
      are removed (purging).
    """
    n = len(signals)
    if n == 0:
        return []

    fold_size = n // n_folds
    splits = []

    for fold in range(n_folds):
        test_start = fold * fold_size
        test_end = test_start + fold_size if fold < n_folds - 1 else n
        test_idx = np.arange(test_start, test_end)

        test_bar_min = signals[test_start].bar_index
        test_bar_max = signals[test_end - 1].bar_index

        # Purge: remove train signals within embargo of the test window
        train_indices = []
        for i in range(n):
            if test_start <= i < test_end:
                continue
            bar = signals[i].bar_index
            if bar >= test_bar_min - embargo_bars and bar <= test_bar_max + embargo_bars:
                continue  # too close to test window — purge
            train_indices.append(i)

        if len(train_indices) < 10:
            continue

        splits.append((np.array(train_indices), test_idx))

    return splits


def train_meta_model(
    symbol: str = "BTCUSDT",
    data_dir: Path = Path("/app/data/raw"),
    funding_dir: Path = Path("/app/data/raw"),
    models_dir: Path = Path("/app/data/models/rsi2"),
    meta_params: Rsi2MetaParams | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> tuple[float, float]:
    """Train XGBoost meta-labeling model on training period. Returns (train_roc_auc, val_score).

    val_score is the composite score of A+B on validation period.
    """
    def _cb(pct: float, msg: str) -> None:
        if progress_callback is not None:
            progress_callback(pct, msg)

    try:
        import xgboost as xgb
    except ImportError:
        raise ImportError("xgboost is required: pip install xgboost")

    from bitpredict.data.funding import load_funding

    if meta_params is None:
        meta_params = Rsi2MetaParams()

    _cb(0.05, "Carregando parâmetros do Caminho A...")
    params_a = load_params_a(models_dir)
    logger.info("Loaded Caminho A params: %s", params_a.model_dump())

    _cb(0.10, "Carregando dados históricos e calculando features...")
    raw_df = load_15m_parquet(symbol=symbol, data_dir=data_dir)
    feature_df = build_features(raw_df)
    df_rows = feature_df.to_dicts()

    # Load funding
    funding_df = load_funding(symbol=symbol, data_dir=funding_dir)
    funding_series: list[tuple[datetime, float]] = []
    if not funding_df.is_empty():
        for row in funding_df.iter_rows(named=True):
            ts = row["funding_time"]
            ts_aware = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
            funding_series.append((ts_aware, float(row["funding_rate"])))

    train_df = _slice_period(feature_df, TRAIN_START, TRAIN_END)
    val_df = _slice_period(feature_df, VAL_START, VAL_END)

    _cb(0.15, "Gerando sinais de treino e rodando backtest para criar rótulos...")
    train_signals = generate_signals(train_df, params_a)
    if len(train_signals) < 30:
        logger.warning("Only %d training signals — meta-labeling may not be reliable", len(train_signals))

    # Run backtest to get labels
    train_result = run_backtest(train_df, train_signals, params_a, funding_series)
    completed_trades = train_result.trades

    if len(completed_trades) < 30:
        logger.warning("Only %d completed trades for meta-labeling", len(completed_trades))

    # Align signals with trades (signals are sequential; trades may skip due to one-at-a-time rule)
    # Re-index: signals that became trades vs those that were skipped
    # We label each signal that entered: 1=win, 0=loss.
    # Signals that were skipped (position was occupied) get no label.
    # Build a lookup: signal bar_index → label
    trade_signal_map: dict[int, int] = {}
    for trade in completed_trades:
        for sig in train_signals:
            if sig.open_time == trade.entry_time and sig.side == trade.side:
                trade_signal_map[sig.bar_index] = trade.label
                break

    labeled_signals = [(sig, trade_signal_map[sig.bar_index])
                       for sig in train_signals if sig.bar_index in trade_signal_map]

    if len(labeled_signals) < 30:
        raise ValueError(f"Too few labeled signals ({len(labeled_signals)}) for meta-labeling")

    signals_only = [ls[0] for ls in labeled_signals]
    labels = np.array([ls[1] for ls in labeled_signals])

    X = _build_feature_matrix(signals_only, feature_df, df_rows)
    logger.info("Meta-labeling dataset: %d samples, %d features, label balance=%.2f",
                len(labels), X.shape[1], labels.mean())

    _cb(0.20, f"Dataset pronto: {len(labels)} amostras, {X.shape[1]} features. Iniciando Purged K-Fold...")

    # Purged K-Fold cross-validation
    splits = _purged_kfold_splits(signals_only, meta_params.n_folds, meta_params.embargo_bars)
    fold_aucs = []
    n_folds_done = len(splits)

    xgb_params = dict(
        n_estimators=meta_params.n_estimators,
        max_depth=meta_params.max_depth,
        learning_rate=meta_params.learning_rate,
        subsample=meta_params.subsample,
        colsample_bytree=meta_params.colsample_bytree,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    for fold_idx, (train_idx, test_idx) in enumerate(splits):
        X_tr, y_tr = X[train_idx], labels[train_idx]
        X_te, y_te = X[test_idx], labels[test_idx]

        if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) < 2:
            continue

        clf = xgb.XGBClassifier(**xgb_params)
        clf.fit(X_tr, y_tr, verbose=False)
        proba = clf.predict_proba(X_te)[:, 1]
        auc = roc_auc_score(y_te, proba)
        fold_aucs.append(auc)
        logger.info("Fold %d AUC: %.4f", fold_idx + 1, auc)

        fold_pct = 0.20 + (fold_idx + 1) / max(n_folds_done, 1) * 0.50
        _cb(fold_pct, f"Fold {fold_idx + 1}/{n_folds_done} — AUC: {auc:.4f}")

    mean_auc = float(np.mean(fold_aucs)) if fold_aucs else 0.0
    logger.info("Mean purged-CV AUC: %.4f", mean_auc)

    if mean_auc < 0.55:
        logger.warning(
            "Mean AUC %.4f < 0.55 threshold — Caminho B may not add value over A.",
            mean_auc,
        )

    _cb(0.75, f"K-Fold concluído — AUC médio: {mean_auc:.4f}. Treinando modelo final...")
    clf_final = xgb.XGBClassifier(**xgb_params)
    clf_final.fit(X, labels, verbose=False)

    _cb(0.85, "Modelo final treinado. Otimizando threshold na validação...")
    val_signals = generate_signals(val_df, params_a)
    if not val_signals:
        save_model_b(clf_final, meta_params.min_proba_threshold, models_dir)
        return mean_auc, 0.0, meta_params.min_proba_threshold

    val_df_rows = val_df.to_dicts()
    X_val = _build_feature_matrix(val_signals, feature_df, val_df_rows)
    val_probas = clf_final.predict_proba(X_val)[:, 1]

    best_threshold = meta_params.min_proba_threshold
    best_val_score = 0.0
    thresholds = list(np.arange(0.50, 0.85, 0.05))

    for t_idx, threshold in enumerate(thresholds):
        meta_mask = [float(p) >= threshold for p in val_probas]
        if sum(meta_mask) < 5:
            continue
        result = run_backtest(val_df, val_signals, params_a, funding_series, meta_mask=meta_mask)
        score = composite_score(result)
        logger.info("Threshold %.2f → val composite score=%.4f (%d signals)", threshold, score, sum(meta_mask))
        if score > best_val_score:
            best_val_score = score
            best_threshold = float(threshold)
        thr_pct = 0.85 + (t_idx + 1) / len(thresholds) * 0.10
        _cb(thr_pct, f"Threshold {threshold:.2f} → score: {score:.4f} ({sum(meta_mask)} sinais)")

    logger.info("Best threshold: %.2f → val score=%.4f", best_threshold, best_val_score)
    _cb(0.97, f"Salvando modelo — threshold ótimo: {best_threshold:.2f}, score val: {best_val_score:.4f}")
    save_model_b(clf_final, best_threshold, models_dir)
    return mean_auc, best_val_score, best_threshold


def predict_proba_signal(
    model,
    signal: SignalRow,
    df_row: dict,
) -> float:
    """Predict probability of win for a single candidate signal."""
    X = np.zeros((1, len(_META_FEATURES) + 1), dtype=np.float32)
    for j, feat in enumerate(_META_FEATURES):
        val = df_row.get(feat)
        X[0, j] = float(val) if val is not None else 0.0
    X[0, len(_META_FEATURES)] = 1.0 if signal.side == "long" else 0.0
    return float(model.predict_proba(X)[0, 1])
