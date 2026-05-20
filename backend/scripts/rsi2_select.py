#!/usr/bin/env python
"""Compare Caminho A vs A+B on validation period and write winner.json.

Run inside the backend container:
    python scripts/rsi2_select.py [--symbol BTCUSDT]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="RSI-2 winner selection")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/raw"))
    parser.add_argument("--models-dir", type=Path, default=Path("/app/data/models/rsi2"))
    args = parser.parse_args()

    console.rule("[bold cyan]RSI-2 — Winner Selection[/bold cyan]")

    from bitpredict.strategies.rsi2.selector import select_winner
    from bitpredict.strategies.rsi2.persistence import load_winner

    winner = select_winner(
        symbol=args.symbol,
        data_dir=args.data_dir,
        funding_dir=args.data_dir,
        models_dir=args.models_dir,
    )

    info = load_winner(args.models_dir)
    console.print(f"\n[bold]Winner:[/bold] [{'green' if winner=='A+B' else 'cyan'}]{winner}[/{'green' if winner=='A+B' else 'cyan'}]")
    console.print(f"  Caminho A  validation score: [cyan]{info['score_a_validation']:.4f}[/cyan]")
    if info['score_b_validation'] is not None:
        console.print(f"  Caminho A+B validation score: [cyan]{info['score_b_validation']:.4f}[/cyan]")
    else:
        console.print("  Caminho A+B: [dim]not available[/dim]")

    if winner == "A":
        console.print("\n[cyan]Production will use pure rules (Caminho A).[/cyan]")
    else:
        console.print("\n[green]Production will use rules + ML filter (Caminho A+B).[/green]")

    console.rule("[bold green]Selection complete[/bold green]")
    console.print(f"[dim]winner.json saved to {args.models_dir}[/dim]")


if __name__ == "__main__":
    main()
