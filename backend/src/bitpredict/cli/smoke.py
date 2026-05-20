"""Infrastructure smoke test — verifies Postgres and Redis are reachable."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

import redis
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text

from bitpredict.config import get_settings
from bitpredict.db import get_engine
from bitpredict.logging import configure_logging


@dataclass(frozen=True)
class CheckResult:
    service: str
    endpoint: str
    ok: bool
    detail: str


def _check_postgres() -> CheckResult:
    settings = get_settings()
    endpoint = str(settings.database_url)
    try:
        engine = get_engine()
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar_one()
            timescale_version = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
            ).scalar_one_or_none()
        pg_short = version.split(",")[0] if version else "unknown"
        if timescale_version is None:
            return CheckResult(
                "Postgres", endpoint, False, f"{pg_short}; TimescaleDB extension NOT installed"
            )
        return CheckResult(
            "Postgres",
            endpoint,
            True,
            f"{pg_short}; TimescaleDB {timescale_version}",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Postgres", endpoint, False, f"{type(exc).__name__}: {exc}")


def _check_redis() -> CheckResult:
    settings = get_settings()
    endpoint = str(settings.redis_url)
    try:
        client = redis.Redis.from_url(endpoint, socket_connect_timeout=3)
        start = time.perf_counter()
        pong = client.ping()
        latency_ms = (time.perf_counter() - start) * 1000
        if not pong:
            return CheckResult("Redis", endpoint, False, "PING returned falsy response")
        return CheckResult("Redis", endpoint, True, f"PONG in {latency_ms:.1f} ms")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Redis", endpoint, False, f"{type(exc).__name__}: {exc}")


def run_smoke_test() -> None:
    configure_logging()
    console = Console()

    console.print(
        Panel.fit(
            "[bold cyan]bitPredict[/bold cyan] — Infrastructure Smoke Test\n"
            "[dim]Verifying connectivity to Postgres and Redis…[/dim]",
            border_style="cyan",
        )
    )

    results = [_check_postgres(), _check_redis()]

    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        title="Service connectivity",
        title_style="bold",
        title_justify="left",
    )
    table.add_column("Service", style="bold")
    table.add_column("Endpoint", overflow="fold")
    table.add_column("Status", justify="center")
    table.add_column("Detail", overflow="fold")

    for r in results:
        status = "[bold green]✓ OK[/bold green]" if r.ok else "[bold red]✗ FAIL[/bold red]"
        table.add_row(r.service, r.endpoint, status, r.detail)

    console.print(table)

    if all(r.ok for r in results):
        console.print(
            "\n[bold green]All services healthy. Infrastructure is ready.[/bold green]"
        )
        sys.exit(0)

    console.print(
        "\n[bold red]One or more services failed. Inspect the table above for details.[/bold red]"
    )
    sys.exit(1)
