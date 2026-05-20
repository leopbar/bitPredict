"""CLI command: bitpredict download — historical OHLCV download with Rich progress."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from bitpredict.data.historical import download_historical, parquet_summary

console = Console()

_DEFAULT_DATA_DIR = Path("/app/data/raw")
_DEFAULT_START = "2017-08-17"


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


def run_download(
    symbol: str,
    interval: str,
    start: str,
    end: str | None,
) -> None:
    start_dt = _parse_date(start)
    end_dt = _parse_date(end) if end else datetime.now(tz=UTC)

    console.print(
        Panel.fit(
            f"[bold cyan]bitPredict[/bold cyan] — Historical Download\n"
            f"[dim]Symbol:[/dim] [bold]{symbol}[/bold]  "
            f"[dim]Interval:[/dim] [bold]{interval}[/bold]  "
            f"[dim]From:[/dim] [bold]{start}[/bold]  "
            f"[dim]To:[/dim] [bold]{end or 'now'}[/bold]",
            border_style="cyan",
        )
    )

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]rows"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )

    task_id: TaskID | None = None

    total_hours = int((end_dt - start_dt).total_seconds() / 3600)

    with progress:
        task_id = progress.add_task("Downloading candles…", total=total_hours)

        def on_page(page: int, total_rows: int) -> None:
            progress.update(
                task_id,  # type: ignore[arg-type]
                completed=min(total_rows, total_hours),
                description=f"Downloading… page {page} ({total_rows:,} rows)",
            )

        df = asyncio.run(
            download_historical(
                symbol=symbol,
                interval=interval,
                start=start_dt,
                end=end_dt,
                data_dir=_DEFAULT_DATA_DIR,
                on_page=on_page,
            )
        )

    out_path = _DEFAULT_DATA_DIR / f"{symbol.lower()}_{interval}.parquet"
    summary = parquet_summary(df, symbol, interval, out_path)

    table = Table(
        title="Download Summary",
        title_style="bold",
        title_justify="left",
        border_style="dim",
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Symbol", summary["symbol"])  # type: ignore[arg-type]
    table.add_row("Interval", summary["interval"])  # type: ignore[arg-type]
    table.add_row("Total candles", f"{summary['rows']:,}")  # type: ignore[arg-type]
    table.add_row("Period start", str(summary["start"]))
    table.add_row("Period end", str(summary["end"]))
    table.add_row("Gaps detected", str(summary["gap_count"]))
    table.add_row("Missing candles", str(summary["missing_candles"]))
    table.add_row("Parquet size", f"{summary['file_size_mb']} MB")
    table.add_row("Output path", str(out_path))

    console.print()
    console.print(table)

    if summary["gap_count"] == 0:
        console.print("\n[bold green]✓ No gaps detected. Series is complete.[/bold green]")
    else:
        console.print(
            f"\n[bold yellow]⚠ {summary['gap_count']} gap(s) found "
            f"({summary['missing_candles']} missing candles).[/bold yellow]"
        )


def register(app: typer.Typer) -> None:
    @app.command(name="download", help="Download historical OHLCV klines from Binance.")
    def download(
        symbol: str = typer.Option("BTCUSDT", "--symbol", "-s", help="Trading pair symbol."),
        interval: str = typer.Option("1h", "--interval", "-i", help="Candle interval."),
        start: str = typer.Option(_DEFAULT_START, "--start", help="Start date (YYYY-MM-DD)."),
        end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD). Defaults to now."),
    ) -> None:
        run_download(symbol=symbol, interval=interval, start=start, end=end)
