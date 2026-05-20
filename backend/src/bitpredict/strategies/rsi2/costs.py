"""Trade cost model: fee, differentiated slippage, funding accrual."""

from __future__ import annotations

from datetime import datetime

from bitpredict.strategies.rsi2.config import Rsi2Params


def entry_cost(entry_price: float, params: Rsi2Params) -> float:
    """Net entry price after fee + slippage (both sides increase cost)."""
    # For long: we pay more; for short: we effectively receive less
    # Return price adjusted upward (long) or downward (short).
    # We use a single effective adjustment: fee + slippage on entry.
    return entry_price * (1.0 + params.fee_pct + params.slippage_normal_pct)


def exit_cost_target(exit_price: float, side: str, params: Rsi2Params) -> float:
    """Net exit price at target (normal slippage)."""
    if side == "long":
        return exit_price * (1.0 - params.fee_pct - params.slippage_normal_pct)
    else:
        return exit_price * (1.0 + params.fee_pct + params.slippage_normal_pct)


def exit_cost_stop(stop_price: float, side: str, params: Rsi2Params) -> float:
    """Net exit price at stop hit (higher slippage — flying candle scenario)."""
    if side == "long":
        return stop_price * (1.0 - params.fee_pct - params.slippage_stop_pct)
    else:
        return stop_price * (1.0 + params.fee_pct + params.slippage_stop_pct)


def accrued_funding(
    entry_time: datetime,
    exit_time: datetime,
    side: str,
    funding_rate_avg: float,
    params: Rsi2Params,
) -> float:
    """Funding cost as a fraction of notional (negative = cost, positive = income).

    Funding is paid/received every 8h. Longs pay if funding > 0; shorts receive.
    Returns the net P&L impact as a fraction of position size.
    """
    hours_held = (exit_time - entry_time).total_seconds() / 3600.0
    n_funding_periods = hours_held / params.funding_interval_hours

    if side == "long":
        return -funding_rate_avg * n_funding_periods
    else:
        return funding_rate_avg * n_funding_periods


def compute_net_pnl_pct(
    side: str,
    entry_price_raw: float,
    exit_price_raw: float,
    exit_reason: str,
    entry_time: datetime,
    exit_time: datetime,
    funding_rate_avg: float,
    params: Rsi2Params,
) -> tuple[float, float]:
    """Compute (gross_pnl_pct, net_pnl_pct) for a completed trade.

    Returns pct values relative to raw entry price (e.g. 0.02 = +2%).
    Costs are round-trip: entry fee+slippage + exit fee+slippage.
    """
    if side == "long":
        gross_pnl_pct = (exit_price_raw - entry_price_raw) / entry_price_raw
    else:
        gross_pnl_pct = (entry_price_raw - exit_price_raw) / entry_price_raw

    # Round-trip cost: entry (normal) + exit (normal or stop slippage)
    entry_cost = params.fee_pct + params.slippage_normal_pct
    if exit_reason == "stop":
        exit_cost = params.fee_pct + params.slippage_stop_pct
    else:
        exit_cost = params.fee_pct + params.slippage_normal_pct

    net_pnl_pct = gross_pnl_pct - entry_cost - exit_cost

    funding_impact = accrued_funding(entry_time, exit_time, side, funding_rate_avg, params)
    net_pnl_pct += funding_impact

    return gross_pnl_pct, net_pnl_pct
