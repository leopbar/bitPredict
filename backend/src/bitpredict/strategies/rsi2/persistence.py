"""Save and load RSI-2 strategy artifacts (params, model, winner config)."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from bitpredict.strategies.rsi2.config import Rsi2MetaParams, Rsi2Params

_DEFAULT_MODELS_DIR = Path("/app/data/models/rsi2")


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_params_a(params: Rsi2Params, models_dir: Path = _DEFAULT_MODELS_DIR) -> Path:
    _ensure_dir(models_dir)
    out = models_dir / "best_params_A.json"
    out.write_text(params.model_dump_json(indent=2))
    return out


def load_params_a(models_dir: Path = _DEFAULT_MODELS_DIR) -> Rsi2Params:
    path = models_dir / "best_params_A.json"
    if not path.exists():
        raise FileNotFoundError(f"best_params_A.json not found at {path}")
    return Rsi2Params.model_validate_json(path.read_text())


def save_model_b(model, threshold: float, models_dir: Path = _DEFAULT_MODELS_DIR) -> None:
    _ensure_dir(models_dir)
    (models_dir / "model_B.pkl").write_bytes(pickle.dumps(model))
    (models_dir / "best_threshold.json").write_text(json.dumps({"threshold": threshold}, indent=2))


def load_model_b(models_dir: Path = _DEFAULT_MODELS_DIR):
    pkl_path = models_dir / "model_B.pkl"
    if not pkl_path.exists():
        return None, None
    model = pickle.loads(pkl_path.read_bytes())
    threshold_path = models_dir / "best_threshold.json"
    threshold = json.loads(threshold_path.read_text())["threshold"] if threshold_path.exists() else 0.55
    return model, threshold


def save_winner(
    winner: str,
    score_a: float,
    score_b: float | None,
    models_dir: Path = _DEFAULT_MODELS_DIR,
) -> Path:
    """winner = 'A' | 'A+B'."""
    _ensure_dir(models_dir)
    data = {"winner": winner, "score_a_validation": score_a, "score_b_validation": score_b}
    out = models_dir / "winner.json"
    out.write_text(json.dumps(data, indent=2))
    return out


def load_winner(models_dir: Path = _DEFAULT_MODELS_DIR) -> dict:
    path = models_dir / "winner.json"
    if not path.exists():
        raise FileNotFoundError(f"winner.json not found at {path}. Run rsi2_select.py first.")
    return json.loads(path.read_text())


def save_sealed_report(report: dict, models_dir: Path = _DEFAULT_MODELS_DIR) -> Path:
    _ensure_dir(models_dir)
    out = models_dir / "sealed_test_report.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    return out
