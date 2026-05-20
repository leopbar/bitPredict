"""CLI command: bitpredict monitoring status."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

app = typer.Typer(help="Model drift and health monitoring commands.")
console = Console()


@app.command("status")
def status() -> None:
    """Display drift PSI scores, model health, and next retrain schedule."""
    from bitpredict.db import get_session
    from bitpredict.monitoring.drift import compute_feature_drift
    from bitpredict.monitoring.model_health import compute_model_health
    from bitpredict.scheduling import beat_schedule  # registers schedules
    from bitpredict.scheduling.celery_app import celery_app

    db = get_session()
    try:
        console.print(
            Panel(
                "[bold cyan]bitPredict — Monitoring Status[/bold cyan]",
                border_style="cyan",
                expand=False,
            )
        )

        # ── Drift table ───────────────────────────────────────────────────────
        console.print("\n[bold]Feature Drift (PSI)[/bold]")
        drift_rows = compute_feature_drift(db)

        drift_table = Table(
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=False,
        )
        drift_table.add_column("Feature", style="white", min_width=18)
        drift_table.add_column("PSI Score", justify="right")
        drift_table.add_column("KS Stat", justify="right")
        drift_table.add_column("KS p-value", justify="right")
        drift_table.add_column("Status", justify="center")

        if drift_rows:
            for row in drift_rows:
                status_str = row["status"]
                if status_str == "alert":
                    status_cell = "[red bold]⚠ ALERT[/red bold]"
                elif status_str == "warning":
                    status_cell = "[yellow]⚡ WARNING[/yellow]"
                else:
                    status_cell = "[green]✓ OK[/green]"

                psi_color = "red" if row["psi"] >= 0.2 else ("yellow" if row["psi"] >= 0.1 else "green")
                drift_table.add_row(
                    row["feature"],
                    f"[{psi_color}]{row['psi']:.4f}[/{psi_color}]",
                    f"{row['ks_statistic']:.4f}",
                    f"{row['ks_pvalue']:.4f}",
                    status_cell,
                )
        else:
            drift_table.add_row("—", "Insufficient data", "", "", "—")

        console.print(drift_table)

        # ── Model health ──────────────────────────────────────────────────────
        console.print("\n[bold]Model Health (Rolling MAE)[/bold]")
        health = compute_model_health(db)

        health_table = Table(box=box.ROUNDED, header_style="bold cyan", show_lines=False)
        health_table.add_column("Metric", style="white", min_width=20)
        health_table.add_column("Value", justify="right")

        health_status = health["status"]
        status_color = {"healthy": "green", "warning": "yellow", "degraded": "red"}.get(
            health_status, "white"
        )

        health_table.add_row("Status", f"[{status_color} bold]{health_status.upper()}[/{status_color} bold]")
        health_table.add_row("MAE 7d (USD)", f"{health['mae_7d']:,.2f}" if health["mae_7d"] else "—")
        health_table.add_row("MAE 30d (USD)", f"{health['mae_30d']:,.2f}" if health["mae_30d"] else "—")
        if health["degradation_pct"] is not None:
            deg_color = "red" if health["degradation_pct"] > 20 else ("yellow" if health["degradation_pct"] > 0 else "green")
            sign = "+" if health["degradation_pct"] >= 0 else ""
            health_table.add_row(
                "Degradation vs 30d",
                f"[{deg_color}]{sign}{health['degradation_pct']:.1f}%[/{deg_color}]",
            )
        health_table.add_row("Next Retrain", health["next_retrain"])

        console.print(health_table)

        # ── Beat schedule ─────────────────────────────────────────────────────
        console.print("\n[bold]Celery Beat Schedule[/bold]")
        sched_table = Table(box=box.ROUNDED, header_style="bold cyan", show_lines=False)
        sched_table.add_column("Task", style="white", min_width=30)
        sched_table.add_column("Schedule", style="cyan")

        for name, config in celery_app.conf.beat_schedule.items():
            sched_table.add_row(name, str(config.get("schedule", "")))

        console.print(sched_table)
        console.print()

    finally:
        db.close()


@app.command("retrain")
def retrain(
    model: str = typer.Option("lightgbm", help="Model to retrain: lightgbm | lstm | nbeats | ensemble | all"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
) -> None:
    """Trigger an immediate model retrain via Celery."""
    if not force:
        confirmed = typer.confirm(f"Retrain [{model}] now?")
        if not confirmed:
            raise typer.Abort()

    from bitpredict.scheduling import tasks  # noqa: F401

    task_map = {
        "lightgbm": "tasks.retrain_lightgbm",
        "lstm": "tasks.retrain_deep_models",
        "nbeats": "tasks.retrain_deep_models",
        "ensemble": "tasks.refit_ensemble_weights",
    }

    from bitpredict.scheduling.celery_app import celery_app

    if model == "all":
        for task_name in ["tasks.retrain_lightgbm", "tasks.retrain_deep_models", "tasks.refit_ensemble_weights"]:
            result = celery_app.send_task(task_name)
            console.print(f"[green]✓[/green] Queued [{task_name}] → task_id={result.id}")
    elif model in task_map:
        result = celery_app.send_task(task_map[model])
        console.print(f"[green]✓[/green] Queued [{task_map[model]}] → task_id={result.id}")
    else:
        console.print(f"[red]Unknown model: {model}[/red]")
        raise typer.Exit(code=1)
