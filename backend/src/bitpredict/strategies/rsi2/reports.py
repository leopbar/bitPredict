"""Rich CLI report rendering for RSI-2 strategy results."""

from __future__ import annotations

from datetime import datetime

import numpy as np
from rich.console import Console
from rich.table import Table
from rich import box

from bitpredict.strategies.rsi2.engine import BacktestResult, TradeResult
from bitpredict.strategies.rsi2.metrics import full_report

console = Console()


def _sparkline(values: list[float], width: int = 30) -> str:
    """ASCII sparkline from a list of values."""
    blocks = "▁▂▃▄▅▆▇█"
    if not values or len(values) < 2:
        return "─" * width
    mn, mx = min(values), max(values)
    rng = mx - mn or 1.0
    scaled = [(v - mn) / rng * (len(blocks) - 1) for v in values]
    step = max(1, len(scaled) // width)
    sampled = [scaled[i] for i in range(0, len(scaled), step)][:width]
    return "".join(blocks[min(int(v), len(blocks) - 1)] for v in sampled)


def print_backtest_summary(result: BacktestResult, title: str = "Backtest Summary") -> None:
    """Print a Rich-formatted backtest summary to stdout."""
    report = full_report(result)

    console.print(f"\n[bold cyan]══ {title} ══[/bold cyan]")

    if report.get("n_trades", 0) == 0:
        console.print("[yellow]No trades generated.[/yellow]")
        return

    # Metrics table
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim", width=30)
    table.add_column("Value", justify="right")

    rows = [
        ("Trades (Long / Short)", f"{report['n_long']} / {report['n_short']}"),
        ("Win Rate", f"{report['win_rate']:.1%}"),
        ("Profit Factor", f"{report['profit_factor']:.2f}"),
        ("Calmar Ratio", f"{report['calmar_ratio']:.3f}"),
        ("Sharpe Ratio", f"{report['sharpe_ratio']:.3f}"),
        ("Composite Score", f"{report['composite_score']:.4f}"),
        ("Total Return", f"{report['total_return_pct']:+.2f}%"),
        ("Max Drawdown", f"{report['max_drawdown_pct']:.2f}%"),
        ("MC Max DD p95", f"{report['mc_max_dd_p95_pct']:.2f}%"),
        ("Avg Net P&L / trade", f"{report['avg_net_pnl_pct']:+.4f}%"),
        ("Avg Bars Held", f"{report['avg_bars_held']:.1f}"),
        ("Exit: Target / Stop / Timeout",
         f"{report['pct_target']:.1%} / {report['pct_stop']:.1%} / {report['pct_timeout']:.1%}"),
    ]

    for k, v in rows:
        wr = report.get("win_rate", 0)
        color = "green" if wr >= 0.35 else "yellow"
        table.add_row(k, v)

    console.print(table)

    # Equity sparkline
    equity_values = result.equity.tolist()
    spark = _sparkline(equity_values)
    direction = "↑" if equity_values[-1] >= equity_values[0] else "↓"
    color = "green" if equity_values[-1] >= equity_values[0] else "red"
    console.print(f"\n[{color}]{direction} Equity curve: {spark}[/{color}]")
    console.print(
        f"   {equity_values[0]:.4f} → {equity_values[-1]:.4f}  "
        f"([bold]{(equity_values[-1]-1)*100:+.2f}%[/bold])\n"
    )


def print_gap_report(
    df,
    symbol: str,
    interval: str,
    rows_per_year: dict[int, int],
) -> None:
    """Print data coverage summary."""
    from bitpredict.data.gaps import detect_gaps, gap_summary

    table = Table(title=f"Data Coverage — {symbol} {interval}", box=box.SIMPLE_HEAVY)
    table.add_column("Year", style="cyan")
    table.add_column("Rows", justify="right")

    for year, count in sorted(rows_per_year.items()):
        table.add_row(str(year), str(count))

    console.print(table)

    gaps = detect_gaps(df, interval)
    gs = gap_summary(gaps, interval)
    if gs["gap_count"] == 0:
        console.print("[green]✓ No gaps detected.[/green]")
    else:
        console.print(
            f"[yellow]⚠ {gs['gap_count']} gaps, {gs['missing_candles']} missing candles.[/yellow]"
        )
