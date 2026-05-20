"""Select winner between Caminho A (pure rules) and A+B (with meta-labeling)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from bitpredict.strategies.rsi2.engine import run_backtest
from bitpredict.strategies.rsi2.features import build_features, load_15m_parquet
from bitpredict.strategies.rsi2.meta_labeling import _build_feature_matrix, predict_proba_signal
from bitpredict.strategies.rsi2.metrics import composite_score
from bitpredict.strategies.rsi2.optimizer import VAL_END, VAL_START, _slice_period
from bitpredict.strategies.rsi2.persistence import (
    load_model_b,
    load_params_a,
    load_winner,
    save_winner,
)
from bitpredict.strategies.rsi2.signals import generate_signals

logger = logging.getLogger(__name__)


def select_winner(
    symbol: str = "BTCUSDT",
    data_dir: Path = Path("/app/data/raw"),
    funding_dir: Path = Path("/app/data/raw"),
    models_dir: Path = Path("/app/data/models/rsi2"),
    progress_callback: Callable[[float, str], None] | None = None,
) -> str:
    """Compare A vs A+B on validation period. Write winner.json. Returns 'A' or 'A+B'."""
    from bitpredict.data.funding import load_funding

    def _cb(pct: float, msg: str) -> None:
        if progress_callback is not None:
            progress_callback(pct, msg)

    _cb(0.05, "Carregando parâmetros e dados históricos...")
    params_a = load_params_a(models_dir)
    raw_df = load_15m_parquet(symbol=symbol, data_dir=data_dir)
    feature_df = build_features(raw_df)

    funding_df = load_funding(symbol=symbol, data_dir=funding_dir)
    funding_series: list[tuple[datetime, float]] = []
    if not funding_df.is_empty():
        for row in funding_df.iter_rows(named=True):
            ts = row["funding_time"]
            ts_aware = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
            funding_series.append((ts_aware, float(row["funding_rate"])))

    _cb(0.20, "Gerando sinais no período de validação (2024)...")
    val_df = _slice_period(feature_df, VAL_START, VAL_END)
    val_signals = generate_signals(val_df, params_a)

    if not val_signals:
        logger.warning("No validation signals — defaulting to winner=A")
        save_winner("A", 0.0, None, models_dir)
        return "A"

    _cb(0.40, f"{len(val_signals)} sinais gerados. Avaliando Caminho A...")
    result_a = run_backtest(val_df, val_signals, params_a, funding_series)
    score_a = composite_score(result_a)
    logger.info("Caminho A validation score: %.4f (%d trades)", score_a, len(result_a.trades))

    _cb(0.60, f"Caminho A: score={score_a:.4f} ({len(result_a.trades)} trades). Avaliando Caminho A+B...")
    model_b, threshold = load_model_b(models_dir)
    score_b: float | None = None

    if model_b is None:
        logger.info("No Caminho B model found. Winner = A by default.")
        _cb(0.95, "Nenhum modelo B encontrado. Vencedor: Caminho A")
        save_winner("A", score_a, None, models_dir)
        return "A"

    df_rows = val_df.to_dicts()
    X_val = _build_feature_matrix(val_signals, feature_df, df_rows)
    try:
        val_probas = model_b.predict_proba(X_val)[:, 1]
        meta_mask = [float(p) >= (threshold or 0.55) for p in val_probas]
        result_ab = run_backtest(val_df, val_signals, params_a, funding_series, meta_mask=meta_mask)
        score_b = composite_score(result_ab)
        logger.info(
            "Caminho A+B validation score: %.4f (%d trades filtered, threshold=%.2f)",
            score_b, sum(meta_mask), threshold or 0.55,
        )
        _cb(0.85, f"Caminho A+B: score={score_b:.4f} ({sum(meta_mask)} trades filtrados). Comparando...")
    except Exception as e:
        logger.error("Caminho B evaluation failed: %s — defaulting to A", e)
        save_winner("A", score_a, None, models_dir)
        return "A"

    winner = "A+B" if (score_b is not None and score_b > score_a) else "A"
    b_str = f"{score_b:.4f}" if score_b is not None else "N/A"
    _cb(0.95, f"Vencedor: Caminho {winner} (A={score_a:.4f} | A+B={b_str})")
    save_winner(winner, score_a, score_b, models_dir)
    logger.info(
        "Winner: %s (A=%.4f, A+B=%.4f)",
        winner, score_a, score_b if score_b is not None else 0.0,
    )
    return winner
