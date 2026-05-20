#!/usr/bin/env python
"""SEALED TEST — runs winner strategy on 2025-01-01 → today. Execute only once.

Run inside the backend container:
    python scripts/rsi2_sealed_test.py [--symbol BTCUSDT]

WARNING: This script is irreversible in the scientific sense — once run,
the test period result is the result. Do not re-run to cherry-pick outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel

console = Console()

TEST_START = datetime(2025, 1, 1, tzinfo=UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description="RSI-2 sealed test (run once)")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/raw"))
    parser.add_argument("--models-dir", type=Path, default=Path("/app/data/models/rsi2"))
    parser.add_argument("--force", action="store_true", help="Re-run even if report already exists")
    args = parser.parse_args()

    report_path = args.models_dir / "sealed_test_report.json"
    if report_path.exists() and not args.force:
        console.print(Panel(
            "[yellow]Sealed test already run. Results:[/yellow]\n"
            + report_path.read_text(),
            title="[bold]Sealed Test — Already Complete[/bold]",
            border_style="yellow",
        ))
        sys.exit(0)

    console.print(Panel(
        "[bold red]⚠ SEALED TEST — This runs once. Result is the result.[/bold red]\n"
        f"Period: {TEST_START.date()} → {datetime.now(tz=UTC).date()}",
        title="RSI-2 Sealed Test",
        border_style="red",
    ))

    from bitpredict.strategies.rsi2.engine import run_backtest
    from bitpredict.strategies.rsi2.features import build_features, load_15m_parquet
    from bitpredict.strategies.rsi2.meta_labeling import _build_feature_matrix
    from bitpredict.strategies.rsi2.metrics import full_report
    from bitpredict.strategies.rsi2.optimizer import _slice_period
    from bitpredict.strategies.rsi2.persistence import load_model_b, load_params_a, load_winner, save_sealed_report
    from bitpredict.strategies.rsi2.reports import print_backtest_summary
    from bitpredict.strategies.rsi2.signals import generate_signals
    from bitpredict.data.funding import load_funding

    test_end = datetime.now(tz=UTC)

    # Load winner config
    winner_info = load_winner(args.models_dir)
    winner = winner_info["winner"]
    console.print(f"Winner variant: [bold cyan]{winner}[/bold cyan]")

    # Load data
    params_a = load_params_a(args.models_dir)
    raw_df = load_15m_parquet(symbol=args.symbol, data_dir=args.data_dir)
    feature_df = build_features(raw_df)
    test_df = _slice_period(feature_df, TEST_START, test_end)

    console.print(f"Test bars: [cyan]{len(test_df):,}[/cyan]")

    funding_df = load_funding(symbol=args.symbol, data_dir=args.data_dir)
    funding_series = []
    if not funding_df.is_empty():
        for row in funding_df.iter_rows(named=True):
            ts = row["funding_time"]
            ts_aware = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
            funding_series.append((ts_aware, float(row["funding_rate"])))

    signals = generate_signals(test_df, params_a)
    meta_mask = None

    if winner == "A+B":
        model_b, threshold = load_model_b(args.models_dir)
        if model_b is not None:
            df_rows = test_df.to_dicts()
            X_test = _build_feature_matrix(signals, feature_df, df_rows)
            probas = model_b.predict_proba(X_test)[:, 1]
            meta_mask = [float(p) >= (threshold or 0.55) for p in probas]
            console.print(f"Meta-mask: [cyan]{sum(meta_mask)}/{len(signals)}[/cyan] signals pass threshold={threshold:.2f}")

    result = run_backtest(test_df, signals, params_a, funding_series, meta_mask=meta_mask)
    print_backtest_summary(result, title=f"Sealed Test ({TEST_START.date()} → {test_end.date()})")

    # Distribution by hour UTC and weekday
    if result.trades:
        hours = {}
        weekdays = {}
        sides = {"long": 0, "short": 0}
        for t in result.trades:
            h = t.entry_time.hour
            w = t.entry_time.weekday()
            hours[h] = hours.get(h, 0) + 1
            weekdays[w] = weekdays.get(w, 0) + 1
            sides[t.side] = sides.get(t.side, 0) + 1

        console.print(f"\nTrade distribution by side: Long={sides['long']} Short={sides['short']}")

    # Build and save report
    report = full_report(result)
    report["period_start"] = str(TEST_START.date())
    report["period_end"] = str(test_end.date())
    report["winner"] = winner
    report["n_signals_generated"] = len(signals)
    report["n_signals_after_filter"] = sum(meta_mask) if meta_mask else len(signals)

    out = save_sealed_report(report, args.models_dir)
    console.print(f"\n[green]✓ Report saved: {out}[/green]")
    console.rule("[bold green]Sealed test complete[/bold green]")


if __name__ == "__main__":
    main()
