"""Database management CLI commands: migrations, status, data loading."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from sqlalchemy import text

console = Console()

db_app = typer.Typer(
    name="db",
    help="Database management: run migrations, inspect status, and load data.",
    no_args_is_help=True,
)


@db_app.command("init")
def init() -> None:
    """Apply all pending Alembic migrations (upgrade head)."""
    console.print(Panel.fit("Running Alembic migrations…", border_style="cyan"))
    result = subprocess.run(["alembic", "upgrade", "head"])
    if result.returncode != 0:
        console.print("[bold red]✗ Migration failed.[/bold red]")
        raise typer.Exit(code=1)
    console.print("[bold green]✓ All migrations applied.[/bold green]")


@db_app.command("status")
def status() -> None:
    """Show row counts, table types, and TimescaleDB chunk counts."""
    from bitpredict.db import get_engine

    engine = get_engine()

    table_names = ["klines", "predictions", "model_runs", "alerts", "parameters", "reports"]

    tbl = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        title="Database Status",
        title_style="bold",
        title_justify="left",
    )
    tbl.add_column("Table", style="bold")
    tbl.add_column("Type", justify="center")
    tbl.add_column("Rows", justify="right")
    tbl.add_column("Chunks / Info", justify="right")

    with engine.connect() as conn:
        hypertables: set[str] = {
            row[0]
            for row in conn.execute(
                text("SELECT hypertable_name FROM timescaledb_information.hypertables")
            )
        }

        for name in table_names:
            try:
                row_count: int = conn.execute(
                    text(f"SELECT COUNT(*) FROM {name}")  # noqa: S608
                ).scalar_one()
                rows_str = f"{row_count:,}"
            except Exception as exc:  # noqa: BLE001
                rows_str = "[red]error[/red]"
                console.print(f"[dim]Could not query {name}: {exc}[/dim]")
                row_count = -1

            if name in hypertables:
                tbl_type = "[cyan]hypertable[/cyan]"
                chunks: int = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM timescaledb_information.chunks "
                        "WHERE hypertable_name = :n"
                    ),
                    {"n": name},
                ).scalar_one()
                info = f"{chunks} chunks"
            else:
                tbl_type = "regular"
                info = "—"

            tbl.add_row(name, tbl_type, rows_str, info)

    console.print(tbl)


@db_app.command("load-historical")
def load_historical(
    path: Path = typer.Option(
        Path("/app/data/raw/btcusdt_1h.parquet"),
        "--path",
        "-p",
        help="Path to the Parquet file to load.",
        show_default=True,
    ),
    symbol: str = typer.Option("BTCUSDT", "--symbol", "-s", help="Trading pair symbol."),
    interval: str = typer.Option("1h", "--interval", "-i", help="Candle interval."),
) -> None:
    """Bulk-load historical klines from a Parquet file into the klines hypertable."""
    from bitpredict.data.loader import load_parquet_to_db

    if not path.exists():
        console.print(f"[bold red]File not found:[/bold red] {path}")
        raise typer.Exit(code=1)

    import polars as pl

    df_meta = pl.read_parquet(path, n_rows=1)
    total_rows = pl.read_parquet(path).height

    console.print(
        Panel.fit(
            f"[bold]Loading historical klines[/bold]\n"
            f"File   : [cyan]{path}[/cyan]\n"
            f"Symbol : [yellow]{symbol}[/yellow]   Interval: [yellow]{interval}[/yellow]\n"
            f"Rows   : [bold]{total_rows:,}[/bold]",
            border_style="cyan",
        )
    )

    rows_sent = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Copying rows to PostgreSQL…", total=total_rows)

        def _on_progress(sent: int, total: int) -> None:
            nonlocal rows_sent
            delta = sent - rows_sent
            rows_sent = sent
            progress.advance(task, delta)

        loaded = load_parquet_to_db(path, symbol=symbol, interval=interval, on_progress=_on_progress)
        progress.update(task, completed=total_rows)

    console.print(
        f"[bold green]✓ Done.[/bold green] "
        f"Processed [bold]{loaded:,}[/bold] rows into [bold]klines[/bold]."
    )


@db_app.command("reset")
def reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Drop and recreate the entire schema (DESTRUCTIVE — all data is lost)."""
    if not yes:
        confirmed = typer.confirm(
            "⚠ This will DROP all tables and permanently delete all data. Proceed?",
            default=False,
        )
        if not confirmed:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit()

    console.print("[yellow]Downgrading to base…[/yellow]")
    r1 = subprocess.run(["alembic", "downgrade", "base"])
    if r1.returncode != 0:
        console.print("[bold red]✗ Downgrade failed.[/bold red]")
        raise typer.Exit(code=1)

    console.print("[yellow]Re-applying migrations…[/yellow]")
    r2 = subprocess.run(["alembic", "upgrade", "head"])
    if r2.returncode != 0:
        console.print("[bold red]✗ Re-migration failed.[/bold red]")
        raise typer.Exit(code=1)

    console.print("[bold green]✓ Schema reset complete.[/bold green]")


def register(parent: typer.Typer) -> None:
    parent.add_typer(db_app)
