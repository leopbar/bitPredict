#!/usr/bin/env python
"""Train Caminho B XGBoost meta-labeling model with Purged K-Fold.

Run inside the backend container:
    python scripts/rsi2_train_meta.py [--symbol BTCUSDT]

Requires: best_params_A.json must exist (run rsi2_optimize.py first).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="RSI-2 Caminho B — meta-labeling training")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/raw"))
    parser.add_argument("--models-dir", type=Path, default=Path("/app/data/models/rsi2"))
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--embargo-bars", type=int, default=10)
    parser.add_argument("--n-folds", type=int, default=5)
    args = parser.parse_args()

    console.rule("[bold cyan]RSI-2 Caminho B — Meta-Labeling Training[/bold cyan]")

    from bitpredict.strategies.rsi2.config import Rsi2MetaParams
    from bitpredict.strategies.rsi2.meta_labeling import train_meta_model

    meta_params = Rsi2MetaParams(
        n_estimators=args.n_estimators,
        embargo_bars=args.embargo_bars,
        n_folds=args.n_folds,
    )

    try:
        roc_auc, val_score = train_meta_model(
            symbol=args.symbol,
            data_dir=args.data_dir,
            models_dir=args.models_dir,
            meta_params=meta_params,
        )
    except ImportError:
        console.print("[red]Error: xgboost not installed. Run: pip install xgboost[/red]")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    console.print("\n[bold green]Meta-labeling training complete:[/bold green]")
    console.print(f"  Purged CV ROC-AUC: [cyan]{roc_auc:.4f}[/cyan]")
    console.print(f"  Validation composite score (A+B): [cyan]{val_score:.4f}[/cyan]")

    if roc_auc < 0.55:
        console.print(
            "\n[yellow]⚠ ROC-AUC below 0.55 — Caminho B may not outperform A on validation. "
            "Run rsi2_select.py to confirm winner.[/yellow]"
        )
    else:
        console.print("\n[green]✓ Model shows predictive signal. Run rsi2_select.py to select winner.[/green]")

    console.rule("[bold green]Done[/bold green]")
    console.print(f"[dim]model_B.pkl + best_threshold.json saved to {args.models_dir}[/dim]")


if __name__ == "__main__":
    main()
