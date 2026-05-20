"""Tests for WeightedQuantileEnsemble."""

from __future__ import annotations

import numpy as np
import pytest


def _make_preds(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    q50 = rng.uniform(40000, 80000, n)
    q10 = q50 * rng.uniform(0.85, 0.99, n)
    q90 = q50 * rng.uniform(1.01, 1.15, n)
    return q10, q50, q90


def _make_val_preds(n: int = 200) -> dict[str, tuple]:
    return {
        "lgbm": _make_preds(n, seed=1),
        "lstm": _make_preds(n, seed=2),
        "nbeats": _make_preds(n, seed=3),
        "tft": _make_preds(n, seed=4),
    }


class TestWeightedQuantileEnsemble:
    def test_fit_produces_valid_weights(self):
        from bitpredict.models.ensemble import WeightedQuantileEnsemble

        n = 100
        val_preds = _make_val_preds(n)
        y_val = np.random.default_rng(42).uniform(40000, 80000, n)

        ens = WeightedQuantileEnsemble()
        ens.fit(val_preds, y_val)

        assert hasattr(ens, "weights_")
        assert len(ens.weights_) == 4
        assert abs(ens.weights_.sum() - 1.0) < 1e-6, "Weights must sum to 1"
        assert np.all(ens.weights_ >= 0), "All weights must be non-negative"

    def test_fit_assigns_nonzero_weight_to_best_model(self):
        """If one model is clearly better, it should get a higher weight."""
        from bitpredict.models.ensemble import WeightedQuantileEnsemble

        rng = np.random.default_rng(0)
        n = 500
        y_val = rng.uniform(40000, 80000, n)

        # "good" model: tight intervals centred on truth
        q50_good = y_val * rng.uniform(0.995, 1.005, n)
        q10_good = q50_good * 0.98
        q90_good = q50_good * 1.02

        # "bad" models: random with wide intervals
        val_preds = {
            "good": (q10_good, q50_good, q90_good),
            "bad1": _make_preds(n, seed=10),
            "bad2": _make_preds(n, seed=11),
        }

        ens = WeightedQuantileEnsemble()
        ens.fit(val_preds, y_val)
        weights = ens.weights_dict()

        assert weights["good"] > weights["bad1"]
        assert weights["good"] > weights["bad2"]

    def test_predict_output_shape(self):
        from bitpredict.models.ensemble import WeightedQuantileEnsemble

        n_val, n_test = 100, 50
        val_preds = _make_val_preds(n_val)
        y_val = np.random.default_rng(0).uniform(40000, 80000, n_val)

        ens = WeightedQuantileEnsemble().fit(val_preds, y_val)

        test_preds = _make_val_preds(n_test)
        q10, q50, q90 = ens.predict(test_preds)

        assert q10.shape == (n_test,)
        assert q50.shape == (n_test,)
        assert q90.shape == (n_test,)

    def test_weights_dict_keys_match_models(self):
        from bitpredict.models.ensemble import WeightedQuantileEnsemble

        n = 80
        val_preds = _make_val_preds(n)
        y_val = np.random.default_rng(1).uniform(40000, 80000, n)

        ens = WeightedQuantileEnsemble().fit(val_preds, y_val)
        assert set(ens.weights_dict().keys()) == set(val_preds.keys())

    def test_uniform_init_constraint_satisfied(self):
        """SLSQP must satisfy sum-to-1 constraint from uniform initial weights."""
        from bitpredict.models.ensemble import WeightedQuantileEnsemble

        n = 60
        val_preds = {"a": _make_preds(n, 0), "b": _make_preds(n, 1)}
        y_val = np.random.default_rng(5).uniform(40000, 80000, n)

        ens = WeightedQuantileEnsemble().fit(val_preds, y_val)
        assert abs(ens.weights_.sum() - 1.0) < 1e-5
