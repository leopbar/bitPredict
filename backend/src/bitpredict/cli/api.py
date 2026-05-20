"""CLI command: demo tour of the REST API endpoints."""

from __future__ import annotations

import json

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()

_BASE_URL = "http://localhost:8000"


def _show(title: str, method: str, path: str, payload: dict | None, response: httpx.Response) -> None:
    console.rule(f"[bold cyan]{title}[/bold cyan]")
    req_str = f"{method} {path}"
    if payload:
        req_str += f"\n{json.dumps(payload, indent=2)}"
    console.print(Syntax(req_str, "http", theme="monokai"))

    try:
        body = json.dumps(response.json(), indent=2)
    except Exception:
        body = response.text
    color = "green" if response.status_code < 300 else "red"
    console.print(f"[{color}]HTTP {response.status_code}[/{color}]")
    console.print(Syntax(body[:1000], "json", theme="monokai"))
    console.print()


def demo(
    base_url: str = typer.Option(_BASE_URL, help="API base URL"),
    api_key: str = typer.Option("dev-secret-key", help="X-API-Key value"),
) -> None:
    """Interactive tour of all API endpoints with coloured JSON output."""
    headers = {"X-API-Key": api_key}

    console.print(
        Panel(
            f"[bold cyan]bitPredict API Demo[/bold cyan]\n"
            f"[dim]Target: {base_url}[/dim]\n"
            f"[dim]Auth:   X-API-Key: {api_key}[/dim]",
            border_style="cyan",
        )
    )

    with httpx.Client(base_url=base_url, headers=headers, timeout=30.0) as client:
        # Health
        r = client.get("/health")
        _show("1 — Liveness probe", "GET", "/health", None, r)

        r = client.get("/ready")
        _show("2 — Readiness probe", "GET", "/ready", None, r)

        # Models
        r = client.get("/models")
        _show("3 — List models", "GET", "/models", None, r)

        # Parameters
        r = client.get("/parameters")
        _show("4 — List parameters", "GET", "/parameters", None, r)

        # Prediction
        payload = {"model_name": "ensemble", "horizon_hours": 24}
        console.print("[yellow]Running inference (may take 10-30 seconds)…[/yellow]")
        r = client.post("/predictions", json=payload, timeout=120.0)
        _show("5 — Run prediction", "POST", "/predictions", payload, r)

        # History
        r = client.get("/predictions/history?limit=5")
        _show("6 — Prediction history", "GET", "/predictions/history?limit=5", None, r)

        # Klines
        r = client.get("/klines?limit=5")
        _show("7 — Klines (last 5h)", "GET", "/klines?limit=5", None, r)

        # Alerts
        alert_body = {
            "name": "Demo — BTC above $100k",
            "condition": {"type": "price_above", "threshold": 100000},
            "channel": "dashboard",
        }
        r = client.post("/alerts", json=alert_body)
        _show("8 — Create alert", "POST", "/alerts", alert_body, r)

        r = client.get("/alerts")
        _show("9 — List alerts", "GET", "/alerts", None, r)

    console.print(
        Panel(
            f"[bold green]Demo complete![/bold green]\n"
            f"[dim]Open the full Swagger UI → {base_url}/docs[/dim]",
            border_style="green",
        )
    )


def register(app: typer.Typer) -> None:
    api_group = typer.Typer(name="api", help="API utilities", no_args_is_help=True)
    api_group.command(name="demo", help="Tour all API endpoints with Rich output.")(demo)
    app.add_typer(api_group)
