"""CLI command: start the FastAPI server with uvicorn."""

from __future__ import annotations

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel

console = Console()


def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(False, help="Auto-reload on file changes (dev only)"),
    workers: int = typer.Option(1, help="Number of worker processes"),
) -> None:
    """Start the bitPredict REST API server."""
    console.print(
        Panel(
            f"[bold cyan]bitPredict API[/bold cyan]\n"
            f"[dim]http://{host}:{port}[/dim]\n"
            f"[dim]Swagger UI → http://{host}:{port}/docs[/dim]",
            title="Starting server",
            border_style="cyan",
        )
    )
    uvicorn.run(
        "bitpredict.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level="info",
    )


def register(app: typer.Typer) -> None:
    app.command(name="serve", help="Start the REST API server.")(serve)
