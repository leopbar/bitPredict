#!/usr/bin/env python
"""Run Caminho A Optuna optimization (500 trials) and save best_params_A.json.

Run inside the backend container:
    python scripts/rsi2_optimize.py [--trials 500] [--symbol BTCUSDT]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="RSI-2 Caminho A optimization")
    parser.add_argument("--trials", type=int, default=500, help="Number of Optuna trials")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/raw"))
    parser.add_argument("--models-dir", type=Path, default=Path("/app/data/models/rsi2"))
    args = parser.parse_args()

    console.rule("[bold cyan]RSI-2 Caminho A — Optuna Optimization[/bold cyan]")
    console.print(f"Trials: {args.trials} | Symbol: {args.symbol}")

    from bitpredict.strategies.rsi2.optimizer import run_optimization
    from bitpredict.strategies.rsi2.reports import print_backtest_summary
    from bitpredict.strategies.rsi2.features import build_features, load_15m_parquet
    from bitpredict.strategies.rsi2.signals import generate_signals
    from bitpredict.strategies.rsi2.engine import run_backtest
    from bitpredict.strategies.rsi2.optimizer import VAL_START, VAL_END, _slice_period
    from bitpredict.data.funding import load_funding
    from datetime import UTC, datetime

    best_params = run_optimization(
        symbol=args.symbol,
        n_trials=args.trials,
        data_dir=args.data_dir,
        models_dir=args.models_dir,
    )

    console.print("\n[bold green]Best parameters (Caminho A):[/bold green]")
    for k, v in best_params.model_dump().items():
        console.print(f"  {k}: [cyan]{v}[/cyan]")

    # Print validation summary
    console.print("\n[bold]Validation period summary:[/bold]")
    raw_df = load_15m_parquet(symbol=args.symbol, data_dir=args.data_dir)
    feature_df = build_features(raw_df)
    val_df = _slice_period(feature_df, VAL_START, VAL_END)
    funding_df = load_funding(symbol=args.symbol, data_dir=args.data_dir)
    funding_series = []
    if not funding_df.is_empty():
        for row in funding_df.iter_rows(named=True):
            ts = row["funding_time"]
            ts_aware = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
            funding_series.append((ts_aware, float(row["funding_rate"])))

    val_signals = generate_signals(val_df, best_params)
    val_result = run_backtest(val_df, val_signals, best_params, funding_series)
    print_backtest_summary(val_result, title="Validation Period (2024)")

    console.rule("[bold green]Optimization complete[/bold green]")
    console.print(f"[dim]best_params_A.json saved to {args.models_dir}[/dim]")


if __name__ == "__main__":
    main()
