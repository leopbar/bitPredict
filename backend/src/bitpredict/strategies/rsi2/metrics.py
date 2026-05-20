"""Performance metrics for the RSI-2 strategy backtest results."""

from __future__ import annotations

import numpy as np

from bitpredict.strategies.rsi2.engine import BacktestResult, TradeResult


def calmar_ratio(result: BacktestResult, periods_per_year: float = 35040.0) -> float:
    """Calmar = annualized return / max drawdown. periods_per_year for 15min = 4*24*365."""
    if not result.trades:
        return 0.0

    equity = result.equity
    total_return = equity[-1] / equity[0] - 1.0
    n_bars = len(equity)
    years = n_bars / periods_per_year
    ann_return = (1.0 + total_return) ** (1.0 / max(years, 0.01)) - 1.0

    max_dd = _max_drawdown(equity)
    if abs(max_dd) < 1e-9:
        return 0.0
    return ann_return / abs(max_dd)


def _max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / (peak + 1e-12)
    return float(dd.min())


def profit_factor(trades: list[TradeResult]) -> float:
    gains = sum(t.net_pnl_pct for t in trades if t.net_pnl_pct > 0)
    losses = abs(sum(t.net_pnl_pct for t in trades if t.net_pnl_pct <= 0))
    return gains / losses if losses > 1e-9 else 0.0


def win_rate(trades: list[TradeResult]) -> float:
    if not trades:
        return 0.0
    return sum(1 for t in trades if t.net_pnl_pct > 0) / len(trades)


def sharpe_ratio(result: BacktestResult, periods_per_year: float = 35040.0) -> float:
    equity = result.equity
    if len(equity) < 2:
        return 0.0
    returns = np.diff(equity) / (equity[:-1] + 1e-12)
    if returns.std() < 1e-9:
        return 0.0
    ann_factor = np.sqrt(periods_per_year)
    return float(returns.mean() / returns.std() * ann_factor)


def composite_score(
    result: BacktestResult,
    min_win_rate: float = 0.35,
    min_trades: int = 200,
) -> float:
    """Composite score = Calmar × min(WR/min_wr, 1) × min(N/min_trades, 1)."""
    n = len(result.trades)
    if n == 0:
        return 0.0
    calmar = calmar_ratio(result)
    if calmar <= 0:
        return 0.0
    wr = win_rate(result.trades)
    wr_factor = min(wr / min_win_rate, 1.0)
    n_factor = min(n / min_trades, 1.0)
    return calmar * wr_factor * n_factor


def monte_carlo_max_dd(
    trades: list[TradeResult],
    n_simulations: int = 1000,
    percentile: float = 95.0,
    seed: int = 42,
) -> dict[str, float]:
    """Bootstrap max drawdown via Monte Carlo shuffling of trade returns."""
    if not trades:
        return {"p50": 0.0, "p95": 0.0}

    rng = np.random.default_rng(seed)
    returns = np.array([t.net_pnl_pct for t in trades])
    max_dds: list[float] = []

    for _ in range(n_simulations):
        shuffled = rng.choice(returns, size=len(returns), replace=True)
        equity = np.cumprod(1.0 + shuffled)
        equity = np.concatenate([[1.0], equity])
        max_dds.append(abs(_max_drawdown(equity)))

    arr = np.array(max_dds)
    return {
        "p50": float(np.percentile(arr, 50)),
        f"p{int(percentile)}": float(np.percentile(arr, percentile)),
    }


def full_report(result: BacktestResult) -> dict:
    """Build a comprehensive metrics dictionary from a BacktestResult."""
    trades = result.trades
    if not trades:
        return {"n_trades": 0}

    net_returns = [t.net_pnl_pct for t in trades]
    mc = monte_carlo_max_dd(trades)

    return {
        "n_trades": len(trades),
        "n_long": result.n_long,
        "n_short": result.n_short,
        "win_rate": round(win_rate(trades), 4),
        "profit_factor": round(profit_factor(trades), 4),
        "calmar_ratio": round(calmar_ratio(result), 4),
        "sharpe_ratio": round(sharpe_ratio(result), 4),
        "composite_score": round(composite_score(result), 4),
        "total_return_pct": round((result.equity[-1] - 1.0) * 100, 4),
        "max_drawdown_pct": round(abs(_max_drawdown(result.equity)) * 100, 4),
        "avg_net_pnl_pct": round(float(np.mean(net_returns)) * 100, 4),
        "std_net_pnl_pct": round(float(np.std(net_returns)) * 100, 4),
        "avg_bars_held": round(float(np.mean([t.bars_held for t in trades])), 2),
        "pct_target": round(sum(1 for t in trades if t.exit_reason == "target") / len(trades), 4),
        "pct_stop": round(sum(1 for t in trades if t.exit_reason == "stop") / len(trades), 4),
        "pct_timeout": round(sum(1 for t in trades if t.exit_reason == "timeout") / len(trades), 4),
        "mc_max_dd_p50_pct": round(mc["p50"] * 100, 4),
        "mc_max_dd_p95_pct": round(mc.get("p95", 0.0) * 100, 4),
    }
