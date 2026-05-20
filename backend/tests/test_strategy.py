"""Tests for QuantileStrategy signal generation."""

from __future__ import annotations

import numpy as np
import pytest

from bitpredict.backtesting.strategy import QuantileStrategy, RiskLevel


def _strat(level: str) -> QuantileStrategy:
    return QuantileStrategy(RiskLevel(level))


# ---------------------------------------------------------------------------
# Single-signal helpers
# ---------------------------------------------------------------------------

class TestConservative:
    strat = _strat("conservative")

    def test_buy_when_q10_above_threshold(self):
        # q10 > price * 1.01 → BUY
        assert self.strat.signal(q10=102.0, q50=105.0, q90=110.0, current_price=100.0) == 1

    def test_hold_when_q10_below_threshold(self):
        # q10 = 100.5 < 100 * 1.01 = 101 → CASH
        assert self.strat.signal(q10=100.5, q50=105.0, q90=110.0, current_price=100.0) == 0

    def test_boundary_exact_threshold(self):
        # q10 == price * 1.01 → CASH (not strictly greater)
        assert self.strat.signal(q10=101.0, q50=105.0, q90=110.0, current_price=100.0) == 0


class TestModerate:
    strat = _strat("moderate")

    def test_buy_when_both_conditions_met(self):
        # q50 > price * 1.005 AND q10 > price
        assert self.strat.signal(q10=101.0, q50=101.0, q90=110.0, current_price=100.0) == 1

    def test_cash_when_q50_too_low(self):
        # q50 = 100.4 < 100 * 1.005 = 100.5
        assert self.strat.signal(q10=101.0, q50=100.4, q90=110.0, current_price=100.0) == 0

    def test_cash_when_q10_below_price(self):
        # q10 < price despite q50 OK
        assert self.strat.signal(q10=99.0, q50=101.0, q90=110.0, current_price=100.0) == 0


class TestAggressive:
    strat = _strat("aggressive")

    def test_buy_when_q50_above_price(self):
        assert self.strat.signal(q10=95.0, q50=101.0, q90=110.0, current_price=100.0) == 1

    def test_cash_when_q50_below_price(self):
        assert self.strat.signal(q10=95.0, q50=99.0, q90=110.0, current_price=100.0) == 0

    def test_cash_when_q50_equal_price(self):
        assert self.strat.signal(q10=95.0, q50=100.0, q90=110.0, current_price=100.0) == 0


# ---------------------------------------------------------------------------
# Vectorised signals()
# ---------------------------------------------------------------------------

class TestVectorisedSignals:
    def test_output_length_matches_input(self):
        strat = _strat("moderate")
        n = 50
        q10 = np.full(n, 101.0)
        q50 = np.full(n, 102.0)
        q90 = np.full(n, 105.0)
        prices = np.full(n, 100.0)
        sigs = strat.signals(q10, q50, q90, prices)
        assert len(sigs) == n

    def test_all_buy_when_conditions_always_met(self):
        strat = _strat("aggressive")
        n = 20
        sigs = strat.signals(
            q10=np.full(n, 99.0),
            q50=np.full(n, 102.0),
            q90=np.full(n, 110.0),
            prices=np.full(n, 100.0),
        )
        assert np.all(sigs == 1)

    def test_all_cash_when_conditions_never_met(self):
        strat = _strat("conservative")
        n = 20
        sigs = strat.signals(
            q10=np.full(n, 100.5),
            q50=np.full(n, 101.0),
            q90=np.full(n, 102.0),
            prices=np.full(n, 100.0),
        )
        assert np.all(sigs == 0)

    def test_mixed_signals(self):
        strat = _strat("aggressive")
        prices = np.array([100.0, 100.0, 100.0, 100.0])
        q50 = np.array([101.0, 99.0, 102.0, 98.0])
        sigs = strat.signals(
            q10=np.zeros(4),
            q50=q50,
            q90=np.zeros(4),
            prices=prices,
        )
        expected = np.array([1, 0, 1, 0])
        np.testing.assert_array_equal(sigs, expected)

    def test_output_dtype_is_integer(self):
        strat = _strat("moderate")
        sigs = strat.signals(
            q10=np.array([101.0]),
            q50=np.array([101.0]),
            q90=np.array([105.0]),
            prices=np.array([100.0]),
        )
        assert sigs.dtype in (np.int32, np.int64, int) or np.issubdtype(sigs.dtype, np.integer)
