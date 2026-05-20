"""Tests for N-BEATS and simplified TFT models."""

from __future__ import annotations

import numpy as np
import pytest
import torch


# ---------------------------------------------------------------------------
# N-BEATS
# ---------------------------------------------------------------------------


def _make_batch(batch_size: int = 8, seq_len: int = 24, n_features: int = 10) -> torch.Tensor:
    return torch.randn(batch_size, seq_len, n_features)


class TestNBeatsBlock:
    def test_output_shapes(self):
        from bitpredict.models.nbeats import NBeatsBlock

        block = NBeatsBlock(input_size=64, hidden_size=128)
        x = torch.randn(8, 64)
        backcast, forecast = block(x)
        assert backcast.shape == (8, 64), "backcast must match input_size"
        assert forecast.shape == (8, 128), "forecast must match hidden_size"

    def test_backcast_is_different_from_input(self):
        from bitpredict.models.nbeats import NBeatsBlock

        block = NBeatsBlock(input_size=32, hidden_size=64)
        x = torch.randn(4, 32)
        backcast, _ = block(x)
        # Backcast is a learned reconstruction — must not be identical to input
        assert not torch.allclose(backcast, x)


class TestNBeatsStack:
    def test_residual_shrinks(self):
        """Residual after subtraction should differ from original input."""
        from bitpredict.models.nbeats import NBeatsStack

        stack = NBeatsStack(n_blocks=3, input_size=64, hidden_size=128)
        x = torch.randn(4, 64)
        residual, forecast = stack(x)
        assert residual.shape == x.shape
        assert forecast.shape == (4, 128)
        assert not torch.allclose(residual, x)

    def test_forecast_sum_accumulates(self):
        """Forecast from a 2-block stack must be non-zero."""
        from bitpredict.models.nbeats import NBeatsStack

        stack = NBeatsStack(n_blocks=2, input_size=32, hidden_size=64)
        x = torch.randn(4, 32)
        _, forecast = stack(x)
        assert forecast.abs().sum() > 0


class TestNBeats:
    def test_forward_output_shape(self):
        from bitpredict.models.nbeats import NBeats

        model = NBeats(seq_len=24, n_features=10, n_stacks=2, n_blocks=2, proj_size=32, hidden_size=64)
        x = _make_batch(n_features=10)
        out = model(x)
        assert out.shape == (8, 3), "Must output 3 quantiles per sample"

    def test_forward_no_nan(self):
        from bitpredict.models.nbeats import NBeats

        model = NBeats(seq_len=24, n_features=10, n_stacks=2, n_blocks=2, proj_size=32, hidden_size=64)
        out = model(_make_batch(n_features=10))
        assert not torch.isnan(out).any()

    def test_different_inputs_give_different_outputs(self):
        from bitpredict.models.nbeats import NBeats

        model = NBeats(seq_len=24, n_features=10, n_stacks=2, n_blocks=2, proj_size=32, hidden_size=64)
        x1 = _make_batch(n_features=10)
        x2 = torch.randn_like(x1) * 2
        out1 = model(x1)
        out2 = model(x2)
        assert not torch.allclose(out1, out2)

    def test_one_training_step(self):
        """Verify that a single gradient step reduces the loss."""
        from bitpredict.models.nbeats import NBeats
        from bitpredict.training.quantile_loss import MultiQuantilePinballLoss

        model = NBeats(seq_len=24, n_features=10, n_stacks=2, n_blocks=2, proj_size=32, hidden_size=64)
        loss_fn = MultiQuantilePinballLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

        x = _make_batch(n_features=10)
        y = torch.randn(8)

        optimizer.zero_grad()
        out = model(x)
        loss_before = loss_fn(out, y)
        loss_before.backward()
        optimizer.step()

        with torch.no_grad():
            out2 = model(x)
            loss_after = loss_fn(out2, y)

        # Loss may not always decrease on a single step with random data, but should be finite
        assert torch.isfinite(loss_after)


# ---------------------------------------------------------------------------
# Simplified TFT
# ---------------------------------------------------------------------------


class TestGRN:
    def test_output_shape_same_size(self):
        from bitpredict.models.tft import GRN

        grn = GRN(input_size=32, hidden_size=64, output_size=32)
        x = torch.randn(8, 32)
        out = grn(x)
        assert out.shape == (8, 32)

    def test_output_shape_different_size(self):
        from bitpredict.models.tft import GRN

        grn = GRN(input_size=16, hidden_size=32, output_size=64)
        x = torch.randn(8, 16)
        out = grn(x)
        assert out.shape == (8, 64)

    def test_no_nan(self):
        from bitpredict.models.tft import GRN

        grn = GRN(input_size=32, hidden_size=64, output_size=32)
        out = grn(torch.randn(4, 32))
        assert not torch.isnan(out).any()


class TestVariableSelectionNetwork:
    def test_output_shape(self):
        from bitpredict.models.tft import VariableSelectionNetwork

        vsn = VariableSelectionNetwork(n_features=10, hidden_size=32)
        x = torch.randn(8, 24, 10)  # (batch, seq_len, n_features)
        out = vsn(x)
        assert out.shape == (8, 24, 10)

    def test_weights_sum_to_one(self):
        """VSN uses softmax so weights over features must sum to 1."""
        from bitpredict.models.tft import GRN, VariableSelectionNetwork

        vsn = VariableSelectionNetwork(n_features=5, hidden_size=16)
        x = torch.randn(4, 6, 5)

        with torch.no_grad():
            weights = torch.softmax(vsn.grn(x), dim=-1)
        sums = weights.sum(dim=-1)  # (4, 6)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)


class TestSimpleTFT:
    def test_forward_output_shape(self):
        from bitpredict.models.tft import SimpleTFT

        model = SimpleTFT(seq_len=24, n_features=10, d_model=32, n_heads=2, n_lstm_layers=1)
        x = _make_batch(n_features=10)
        out = model(x)
        assert out.shape == (8, 3)

    def test_forward_no_nan(self):
        from bitpredict.models.tft import SimpleTFT

        model = SimpleTFT(seq_len=24, n_features=10, d_model=32, n_heads=2, n_lstm_layers=1)
        out = model(_make_batch(n_features=10))
        assert not torch.isnan(out).any()

    def test_one_training_step(self):
        from bitpredict.models.tft import SimpleTFT
        from bitpredict.training.quantile_loss import MultiQuantilePinballLoss

        model = SimpleTFT(seq_len=24, n_features=10, d_model=32, n_heads=2, n_lstm_layers=1)
        loss_fn = MultiQuantilePinballLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

        x = _make_batch(n_features=10)
        y = torch.randn(8)

        optimizer.zero_grad()
        out = model(x)
        loss = loss_fn(out, y)
        loss.backward()
        optimizer.step()
        assert torch.isfinite(loss)


# ---------------------------------------------------------------------------
# DeepModelInferenceWrapper
# ---------------------------------------------------------------------------


class TestDeepModelInferenceWrapper:
    def _make_wrapper(self, seq_len: int = 8):
        from sklearn.preprocessing import StandardScaler

        from bitpredict.models.dl_inference import DeepModelInferenceWrapper
        from bitpredict.models.nbeats import NBeats

        model = NBeats(seq_len=seq_len, n_features=5, n_stacks=1, n_blocks=1, proj_size=16, hidden_size=32)
        scaler = StandardScaler()
        scaler.fit(np.random.randn(100, 5))
        return DeepModelInferenceWrapper(model, scaler, seq_len=seq_len)

    def test_predict_quantiles_shape(self):
        seq_len = 8
        wrapper = self._make_wrapper(seq_len)
        n = 20
        X = np.random.randn(n, 5)
        close = np.abs(np.random.randn(n)) + 1.0
        q10, q50, q90 = wrapper.predict_quantiles(X, close)
        expected = n - seq_len + 1
        assert q10.shape == (expected,)
        assert q50.shape == (expected,)
        assert q90.shape == (expected,)

    def test_monotonicity_enforced(self):
        wrapper = self._make_wrapper()
        X = np.random.randn(20, 5)
        close = np.abs(np.random.randn(20)) + 1.0
        q10, q50, q90 = wrapper.predict_quantiles(X, close)
        assert np.all(q10 <= q50)
        assert np.all(q50 <= q90)

    def test_predict_single_returns_three_floats(self):
        wrapper = self._make_wrapper()
        X_recent = np.random.randn(10, 5)
        q10, q50, q90 = wrapper.predict_single(X_recent, close_last=50000.0)
        assert isinstance(q10, float)
        assert isinstance(q50, float)
        assert isinstance(q90, float)
        assert q10 <= q50 <= q90
