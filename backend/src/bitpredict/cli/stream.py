"""CLI command: bitpredict stream — real-time kline stream with Rich Live table."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from bitpredict.data.streaming import KlineEvent, KlineStreamer

console = Console()

_MAX_ROWS = 20


def _make_table(events: list[KlineEvent]) -> Table:
    table = Table(
        title="Live Binance Kline Stream",
        title_style="bold cyan",
        title_justify="left",
        border_style="dim",
        show_lines=False,
        header_style="bold",
    )
    table.add_column("Time (UTC)", style="dim", min_width=20)
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right", style="green")
    table.add_column("Low", justify="right", style="red")
    table.add_column("Close", justify="right", style="bold")
    table.add_column("Volume", justify="right", style="dim")
    table.add_column("Trades", justify="right", style="dim")
    table.add_column("Closed", justify="center")

    for ev in reversed(events[-_MAX_ROWS:]):
        change = ev.close - ev.open
        close_style = "bold green" if change >= 0 else "bold red"
        closed_mark = "[green]✓[/green]" if ev.is_closed else "[yellow]…[/yellow]"
        table.add_row(
            ev.open_time.strftime("%Y-%m-%d %H:%M"),
            f"{ev.open:,.2f}",
            f"{ev.high:,.2f}",
            f"{ev.low:,.2f}",
            f"[{close_style}]{ev.close:,.2f}[/{close_style}]",
            f"{ev.volume:,.3f}",
            str(ev.trades),
            closed_mark,
        )
    return table


def run_stream(symbol: str, interval: str, duration: int | None) -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]bitPredict[/bold cyan] — Live Kline Stream\n"
            f"[dim]Symbol:[/dim] [bold]{symbol}[/bold]  "
            f"[dim]Interval:[/dim] [bold]{interval}[/bold]  "
            f"[dim]Duration:[/dim] [bold]{'∞' if duration is None else f'{duration}s'}[/bold]\n"
            f"[dim]Press Ctrl+C to stop.[/dim]",
            border_style="cyan",
        )
    )

    events: list[KlineEvent] = []
    streamer = KlineStreamer(symbol=symbol, interval=interval)

    async def _run() -> None:
        deadline = (
            asyncio.get_event_loop().time() + duration if duration else float("inf")
        )
        with Live(console=console, refresh_per_second=4, screen=False) as live:
            async for event in streamer.stream():
                events.append(event)
                live.update(_make_table(events))
                if asyncio.get_event_loop().time() >= deadline:
                    break

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[dim]Stream stopped.[/dim]")

    console.print(f"\n[bold green]✓ Received {len(events)} events.[/bold green]")


def register(app: typer.Typer) -> None:
    @app.command(name="stream", help="Stream real-time klines from Binance WebSocket.")
    def stream(
        symbol: str = typer.Option("BTCUSDT", "--symbol", "-s", help="Trading pair symbol."),
        interval: str = typer.Option("1h", "--interval", "-i", help="Candle interval."),
        duration: int | None = typer.Option(
            None, "--duration", "-d", help="Stop after N seconds. Omit for infinite."
        ),
    ) -> None:
        run_stream(symbol=symbol, interval=interval, duration=duration)
