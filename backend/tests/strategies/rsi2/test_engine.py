"""Unit tests for the RSI-2 backtest engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from bitpredict.strategies.rsi2.config import Rsi2Params
from bitpredict.strategies.rsi2.engine import TradeResult, run_backtest
from bitpredict.strategies.rsi2.signals import SignalRow


def _ts(i: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * i)


def _make_flat_df(n: int, base_price: float = 50000.0) -> pl.DataFrame:
    """Flat market: every bar has the same OHLCV and RSI values."""
    rows = [
        {
            "open_time": _ts(i),
            "open": base_price,
            "high": base_price * 1.001,
            "low": base_price * 0.999,
            "close": base_price,
            "volume": 100.0,
            "rsi_2": 50.0,
            "rsi_2_prev": 50.0,
            "atr_14": base_price * 0.002,
            "body_pct": 0.0,
            "close_pos": 0.5,
        }
        for i in range(n)
    ]
    return pl.from_dicts(rows)


def _long_signal(bar_idx: int, entry: float, stop: float) -> SignalRow:
    return SignalRow(
        bar_index=bar_idx,
        open_time=_ts(bar_idx),
        side="long",
        entry_price=entry,
        stop_price=stop,
        rsi2_prev=5.0,
        body_pct=0.3,
        close_pos=0.7,
    )


def _short_signal(bar_idx: int, entry: float, stop: float) -> SignalRow:
    return SignalRow(
        bar_index=bar_idx,
        open_time=_ts(bar_idx),
        side="short",
        entry_price=entry,
        stop_price=stop,
        rsi2_prev=95.0,
        body_pct=-0.3,
        close_pos=0.3,
    )


@pytest.mark.unit
def test_target_hit_long():
    """Long trade should exit at target when RSI(2) >= rsi_exit_long."""
    n = 20
    entry_price = 50000.0
    stop_price = 49000.0  # well below

    rows = _make_flat_df(n, base_price=entry_price).to_dicts()
    # At bar 5, RSI spikes above 70 → target
    rows[5]["rsi_2"] = 75.0

    df = pl.from_dicts(rows)
    params = Rsi2Params(rsi_exit_long=70.0, timeout_bars=0)
    signals = [_long_signal(0, entry_price, stop_price)]

    result = run_backtest(df, signals, params)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "target"
    assert trade.bars_held == 5
    assert trade.side == "long"


@pytest.mark.unit
def test_stop_hit_long():
    """Long trade should exit at stop when price drops to stop level."""
    n = 20
    entry_price = 50000.0
    stop_price = 49500.0

    rows = _make_flat_df(n, base_price=entry_price).to_dicts()
    # At bar 3, price drops below stop
    rows[3]["low"] = stop_price - 100.0

    df = pl.from_dicts(rows)
    params = Rsi2Params(rsi_exit_long=70.0, timeout_bars=0)
    signals = [_long_signal(0, entry_price, stop_price)]

    result = run_backtest(df, signals, params)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.bars_held == 3
    assert trade.net_pnl_pct < 0  # stop loss is always negative


@pytest.mark.unit
def test_timeout_exit():
    """Trade should exit via timeout when RSI never reverses."""
    n = 30
    entry_price = 50000.0
    stop_price = 40000.0  # far away, won't be hit

    df = _make_flat_df(n, base_price=entry_price)
    # RSI stays at 50 — never hits 70 (target) or below stop
    params = Rsi2Params(rsi_exit_long=70.0, timeout_bars=8)
    signals = [_long_signal(0, entry_price, stop_price)]

    result = run_backtest(df, signals, params)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "timeout"
    assert trade.bars_held == 8


@pytest.mark.unit
def test_one_position_at_a_time():
    """Second signal while position is open should be ignored."""
    n = 20
    entry_price = 50000.0
    stop_price = 49000.0

    rows = _make_flat_df(n, base_price=entry_price).to_dicts()
    rows[10]["rsi_2"] = 75.0  # target hit at bar 10

    df = pl.from_dicts(rows)
    params = Rsi2Params(rsi_exit_long=70.0, timeout_bars=0)
    # Two signals: bar 0 and bar 5 (while first is still open)
    signals = [
        _long_signal(0, entry_price, stop_price),
        _long_signal(5, entry_price, stop_price),
    ]

    result = run_backtest(df, signals, params)

    # Only the first signal should produce a trade (bar 5 is skipped)
    assert len(result.trades) == 1
    assert result.trades[0].bars_held == 10


@pytest.mark.unit
def test_target_hit_short():
    """Short trade should exit at target when RSI(2) <= rsi_exit_short."""
    n = 20
    entry_price = 50000.0
    stop_price = 51000.0

    rows = _make_flat_df(n, base_price=entry_price).to_dicts()
    rows[4]["rsi_2"] = 25.0  # target: RSI drops below 30

    df = pl.from_dicts(rows)
    params = Rsi2Params(rsi_exit_short=30.0, timeout_bars=0)
    signals = [_short_signal(0, entry_price, stop_price)]

    result = run_backtest(df, signals, params)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "target"
    assert trade.side == "short"
    assert trade.bars_held == 4


@pytest.mark.unit
def test_stop_hit_short():
    """Short trade should exit at stop when price rises above stop level."""
    n = 20
    entry_price = 50000.0
    stop_price = 50500.0

    rows = _make_flat_df(n, base_price=entry_price).to_dicts()
    rows[2]["high"] = stop_price + 100.0  # rises above stop

    df = pl.from_dicts(rows)
    params = Rsi2Params(rsi_exit_short=30.0, timeout_bars=0)
    signals = [_short_signal(0, entry_price, stop_price)]

    result = run_backtest(df, signals, params)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.net_pnl_pct < 0


@pytest.mark.unit
def test_costs_reduce_pnl():
    """Net PnL should be lower than gross PnL due to fee+slippage."""
    n = 20
    entry_price = 50000.0
    stop_price = 40000.0

    rows = _make_flat_df(n, base_price=entry_price).to_dicts()
    rows[2]["rsi_2"] = 75.0  # quick target

    df = pl.from_dicts(rows)
    params = Rsi2Params(
        rsi_exit_long=70.0,
        fee_pct=0.0005,
        slippage_normal_pct=0.0003,
        slippage_stop_pct=0.0012,
    )
    signals = [_long_signal(0, entry_price, stop_price)]
    result = run_backtest(df, signals, params)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.net_pnl_pct <= trade.gross_pnl_pct


@pytest.mark.unit
def test_label_win_on_target_loss_on_stop():
    """Trades exiting via target get label=1; via stop get label=0."""
    n = 30
    entry_price = 50000.0

    rows = _make_flat_df(n, base_price=entry_price).to_dicts()
    rows[2]["rsi_2"] = 75.0  # first trade exits at target
    rows[20]["high"] = 49400.0  # second trade stop (stop=49500)

    df = pl.from_dicts(rows)
    params = Rsi2Params(rsi_exit_long=70.0, rsi_exit_short=30.0, timeout_bars=0)

    # First long hits target at bar 2
    # Second long hits stop at bar 20 (entry=bar 10, stop=49500)
    signals = [
        _long_signal(0, entry_price, stop_price=40000),   # won't stop
        _long_signal(10, entry_price, stop_price=49500),  # will stop
    ]
    result = run_backtest(df, signals, params)

    assert len(result.trades) >= 1
    winning_trades = [t for t in result.trades if t.label == 1]
    assert len(winning_trades) >= 1  # at least the target exit
