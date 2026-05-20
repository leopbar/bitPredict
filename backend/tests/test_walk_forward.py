"""Tests for BacktestEngine, metrics, equity_curve, and WalkForwardBacktest (offline)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from bitpredict.backtesting.engine import BacktestEngine, BacktestResult, Trade
from bitpredict.backtesting.equity_curve import sparkline
from bitpredict.backtesting.metrics import (
    avg_trade_duration_hours,
    buy_hold_return,
    compute_all,
    excess_return,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    total_return,
    win_rate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _times(n: int, start: datetime | None = None) -> list[datetime]:
    base = start or datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [base + timedelta(hours=i) for i in range(n)]


def _run(prices, signals, capital=10_000.0):
    engine = BacktestEngine(initial_capital=capital, fee_rate=0.001, slippage=0.0005)
    return engine.run(
        prices=np.array(prices, dtype=float),
        signals=np.array(signals, dtype=int),
        times=_times(len(prices)),
    )


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------

class TestBacktestEngine:
    def test_equity_length_equals_price_length(self):
        result = _run([100] * 10, [0] * 10)
        assert len(result.equity) == 10

    def test_all_cash_equity_stays_flat(self):
        result = _run([100, 110, 120, 90, 80], [0, 0, 0, 0, 0])
        np.testing.assert_allclose(result.equity, 10_000.0)
        assert result.trades == []

    def test_single_profitable_trade(self):
        # Buy at t=0 (executes at price[1]=120), sell at t=2 (executes at price[3]=150)
        result = _run([100, 120, 130, 150, 160], [1, 1, 0, 0, 0])
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.net_pnl > 0

    def test_single_losing_trade(self):
        result = _run([100, 120, 90, 80, 70], [1, 1, 0, 0, 0])
        assert len(result.trades) == 1
        assert result.trades[0].net_pnl < 0

    def test_final_capital_matches_equity_last(self):
        result = _run([100, 110, 120, 130, 140], [1, 1, 1, 0, 0])
        assert result.final_capital == pytest.approx(result.equity[-1], rel=1e-6)

    def test_buy_hold_final_correct(self):
        prices = [100, 110, 120, 130, 200]
        result = _run(prices, [0] * 5, capital=10_000.0)
        expected = 10_000.0 * (200 / 100)
        assert result.buy_hold_final == pytest.approx(expected, rel=1e-6)

    def test_open_position_closed_at_end(self):
        # Signal stays 1 → position held until last bar
        result = _run([100, 110, 120, 130, 140], [1, 1, 1, 1, 1])
        assert len(result.trades) == 1
        assert result.trades[0].exit_time == _times(5)[-1]

    def test_multiple_round_trips(self):
        # Two separate buy/sell cycles
        result = _run(
            [100, 110, 120, 115, 130, 140, 135, 160],
            [1,   1,   0,   1,   1,   0,   0,   0],
        )
        assert len(result.trades) == 2

    def test_equity_never_negative(self):
        # Prices collapse to near-zero
        prices = [100, 50, 20, 10, 5, 1]
        result = _run(prices, [1, 1, 1, 1, 0, 0])
        assert np.all(result.equity >= 0)

    def test_fees_reduce_capital(self):
        # With fees, final equity must be less than a no-fee scenario
        result_fee = _run([100, 120, 100], [1, 0, 0], capital=10_000.0)
        engine_nofee = BacktestEngine(initial_capital=10_000.0, fee_rate=0.0, slippage=0.0)
        result_nofee = engine_nofee.run(
            prices=np.array([100, 120, 100], dtype=float),
            signals=np.array([1, 0, 0], dtype=int),
            times=_times(3),
        )
        assert result_fee.final_capital < result_nofee.final_capital


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _make_result(equity, prices=None, capital=10_000.0, trades=None):
    n = len(equity)
    if prices is None:
        prices = np.ones(n) * 100.0
    return BacktestResult(
        equity=np.array(equity, dtype=float),
        times=_times(n),
        prices=np.array(prices, dtype=float),
        signals=np.zeros(n, dtype=int),
        trades=trades or [],
        initial_capital=capital,
        final_capital=float(equity[-1]),
        buy_hold_final=capital * (prices[-1] / prices[0]),
    )


class TestMetrics:
    def test_total_return_positive(self):
        r = _make_result([10_000, 10_500, 11_000])
        assert total_return(r) == pytest.approx(10.0, rel=1e-4)

    def test_total_return_negative(self):
        r = _make_result([10_000, 9_500, 9_000])
        assert total_return(r) == pytest.approx(-10.0, rel=1e-4)

    def test_buy_hold_return(self):
        r = _make_result([10_000, 10_000, 10_000], prices=[100, 100, 200])
        assert buy_hold_return(r) == pytest.approx(100.0, rel=1e-4)

    def test_excess_return(self):
        r = _make_result([10_000, 11_000, 12_000], prices=[100, 100, 110])
        strat = total_return(r)
        bh = buy_hold_return(r)
        assert excess_return(r) == pytest.approx(strat - bh, rel=1e-6)

    def test_sharpe_flat_equity_is_zero(self):
        r = _make_result([10_000] * 100)
        assert sharpe_ratio(r) == 0.0

    def test_sharpe_rising_equity_positive(self):
        equity = np.linspace(10_000, 15_000, 200)
        r = _make_result(equity)
        assert sharpe_ratio(r) > 0

    def test_max_drawdown_flat(self):
        r = _make_result([10_000] * 50)
        assert max_drawdown(r) == pytest.approx(0.0, abs=1e-6)

    def test_max_drawdown_is_negative(self):
        r = _make_result([10_000, 12_000, 8_000, 9_000])
        assert max_drawdown(r) < 0

    def test_max_drawdown_magnitude(self):
        # Peak 12_000 → trough 8_000 = -33.3%
        r = _make_result([10_000, 12_000, 8_000, 9_000])
        assert max_drawdown(r) == pytest.approx(-100 * (12_000 - 8_000) / 12_000, rel=1e-4)

    def test_win_rate_all_wins(self):
        def _t(pnl):
            return Trade(
                entry_time=_times(2)[0], exit_time=_times(2)[1],
                entry_price=100.0, exit_price=110.0,
                quantity=1.0, gross_pnl=pnl, net_pnl=pnl, return_pct=pnl,
            )
        trades = [_t(10.0), _t(5.0), _t(3.0)]
        assert win_rate(trades) == pytest.approx(100.0)

    def test_win_rate_no_trades(self):
        assert win_rate([]) == 0.0

    def test_profit_factor_all_wins(self):
        def _t(pnl):
            return Trade(
                entry_time=_times(2)[0], exit_time=_times(2)[1],
                entry_price=100.0, exit_price=110.0,
                quantity=1.0, gross_pnl=pnl, net_pnl=pnl, return_pct=pnl,
            )
        trades = [_t(10.0), _t(5.0)]
        assert profit_factor(trades) == float("inf")

    def test_avg_trade_duration(self):
        t = Trade(
            entry_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            exit_time=datetime(2025, 1, 1, 6, tzinfo=timezone.utc),
            entry_price=100.0, exit_price=106.0,
            quantity=1.0, gross_pnl=6.0, net_pnl=5.0, return_pct=5.0,
        )
        assert avg_trade_duration_hours([t]) == pytest.approx(6.0)

    def test_compute_all_returns_expected_keys(self):
        result = _run([100, 110, 120, 115, 100], [1, 1, 0, 0, 0])
        metrics = compute_all(result)
        expected_keys = {
            "total_return_pct", "buy_hold_return_pct", "excess_return_pct",
            "sharpe", "max_drawdown_pct", "calmar", "win_rate_pct",
            "profit_factor", "n_trades", "avg_trade_duration_h",
            "initial_capital", "final_capital", "buy_hold_final",
        }
        assert expected_keys == set(metrics.keys())


# ---------------------------------------------------------------------------
# Equity curve sparkline
# ---------------------------------------------------------------------------

class TestSparkline:
    def test_empty_returns_empty_string(self):
        assert sparkline(np.array([])) == ""

    def test_output_length_equals_width(self):
        values = np.linspace(100, 200, 200)
        s = sparkline(values, width=60)
        assert len(s) == 60

    def test_flat_series_all_same_char(self):
        values = np.full(50, 100.0)
        s = sparkline(values, width=20)
        assert len(set(s)) == 1

    def test_contains_only_block_chars(self):
        valid = set(" ▁▂▃▄▅▆▇█")
        values = np.linspace(100, 200, 100)
        s = sparkline(values, width=40)
        assert set(s).issubset(valid)
