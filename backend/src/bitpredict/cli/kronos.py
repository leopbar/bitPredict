"""Kronos smoke test — verifies model loading, inference, and data freshness."""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _timedelta_for_interval(interval: str) -> timedelta:
    mapping = {
        "15m": timedelta(minutes=15),
        "1h":  timedelta(hours=1),
        "4h":  timedelta(hours=4),
        "8h":  timedelta(hours=8),
        "1d":  timedelta(days=1),
        "1w":  timedelta(weeks=1),
    }
    return mapping.get(interval, timedelta(hours=1))


def _check_model_load(variant: str) -> tuple[bool, str]:
    try:
        t0 = time.perf_counter()
        from bitpredict.kronos.loader import get_predictor
        get_predictor(variant)
        elapsed = time.perf_counter() - t0
        return True, f"loaded in {elapsed:.1f}s"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _check_quick_inference(variant: str) -> tuple[bool, str]:
    try:
        import pandas as pd
        from bitpredict.kronos.loader import get_predictor
        from bitpredict.kronos.timeframes import Timeframe

        predictor = get_predictor(variant)
        # Minimal synthetic context (10 candles)
        n = 10
        prices = [50000.0 + i * 10 for i in range(n)]
        df = pd.DataFrame({
            "open":   prices,
            "high":   [p + 50 for p in prices],
            "low":    [p - 50 for p in prices],
            "close":  prices,
            "volume": [100.0] * n,
        })
        ts = pd.Series([
            datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=i)
            for i in range(n)
        ])
        y_ts = pd.Series([datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=n)])

        t0 = time.perf_counter()
        pred = predictor.predict(
            df=df,
            x_timestamp=ts,
            y_timestamp=y_ts,
            pred_len=1,
            T=0.8,
            top_p=0.9,
            sample_count=1,
            verbose=False,
        )
        elapsed = time.perf_counter() - t0
        close = float(pred["close"].iloc[0])
        return True, f"close={close:,.0f} in {elapsed:.1f}s"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _check_klines_freshness(db, timeframe_value: str) -> tuple[bool, str]:
    from sqlalchemy import select
    from bitpredict.db_models import Kline
    from bitpredict.kronos.timeframes import Timeframe

    tf = Timeframe(timeframe_value)
    interval = tf.to_binance_interval()
    max_staleness = _timedelta_for_interval(interval) * 2

    last_row = db.execute(
        select(Kline.open_time)
        .where(Kline.symbol == "BTCUSDT", Kline.interval == interval)
        .order_by(Kline.open_time.desc())
        .limit(1)
    ).scalar_one_or_none()

    if last_row is None:
        return False, "no klines in DB"

    last_dt = last_row if last_row.tzinfo else last_row.replace(tzinfo=UTC)
    staleness = datetime.now(tz=UTC) - last_dt
    if staleness > max_staleness:
        return False, f"stale: last={last_dt.strftime('%Y-%m-%d %H:%M')} ({staleness})"
    return True, f"last={last_dt.strftime('%Y-%m-%d %H:%M')} ({staleness})"


def _check_prediction_freshness(db, timeframe_value: str) -> tuple[bool, str]:
    from sqlalchemy import select
    from bitpredict.db_models import KronosPrediction
    from bitpredict.kronos.timeframes import Timeframe

    tf = Timeframe(timeframe_value)
    interval = tf.to_binance_interval()
    # Prediction is stale if older than 3× candle period
    max_staleness = _timedelta_for_interval(interval) * 3

    last_row = db.execute(
        select(KronosPrediction.predicted_at, KronosPrediction.status)
        .where(
            KronosPrediction.timeframe == timeframe_value,
            KronosPrediction.status == "done",
        )
        .order_by(KronosPrediction.predicted_at.desc())
        .limit(1)
    ).first()

    if last_row is None:
        return False, "no predictions in DB"

    pred_at, _ = last_row
    pred_at = pred_at if pred_at.tzinfo else pred_at.replace(tzinfo=UTC)
    staleness = datetime.now(tz=UTC) - pred_at
    if staleness > max_staleness:
        return False, f"stale: last={pred_at.strftime('%Y-%m-%d %H:%M')} ({staleness})"
    return True, f"last={pred_at.strftime('%Y-%m-%d %H:%M')} ({staleness})"


def run_kronos_smoke() -> None:
    from bitpredict.db import get_session
    from bitpredict.logging import configure_logging
    configure_logging()

    console.print(
        Panel.fit(
            "[bold cyan]bitPredict · Kronos[/bold cyan] — Smoke Test\n"
            "[dim]Model loading, quick inference, data freshness checks…[/dim]",
            border_style="cyan",
        )
    )

    all_ok = True
    checks: list[tuple[str, str, bool, str]] = []

    # ── Model checks ──────────────────────────────────────────────────────────
    for variant in ("small", "base"):
        ok, detail = _check_model_load(variant)
        checks.append(("Model", f"Kronos-{variant} load", ok, detail))
        all_ok &= ok

    for variant in ("small", "base"):
        ok, detail = _check_quick_inference(variant)
        checks.append(("Inference", f"Kronos-{variant} predict(1)", ok, detail))
        all_ok &= ok

    # ── DB freshness ──────────────────────────────────────────────────────────
    db = get_session()
    try:
        for tf in ("15m", "1h", "4h", "8h", "1d", "1w"):
            ok, detail = _check_klines_freshness(db, tf)
            checks.append(("Klines", f"{tf} freshness", ok, detail))
            # Don't fail overall for stale — just warn

        for tf in ("15m", "1h", "4h", "8h", "1d", "1w"):
            ok, detail = _check_prediction_freshness(db, tf)
            checks.append(("Prediction", f"{tf} freshness", ok, detail))
            # Don't fail overall for no predictions — just warn
    finally:
        db.close()

    # ── Report ────────────────────────────────────────────────────────────────
    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        title="Kronos smoke checks",
        title_style="bold",
        title_justify="left",
    )
    table.add_column("Category", style="bold")
    table.add_column("Check")
    table.add_column("Status", justify="center")
    table.add_column("Detail", overflow="fold")

    for category, check, ok, detail in checks:
        status = "[bold green]✓ OK[/bold green]" if ok else "[bold yellow]⚠ WARN[/bold yellow]"
        table.add_row(category, check, status, detail)

    console.print(table)

    if all_ok:
        console.print("\n[bold green]Kronos models healthy and inference working.[/bold green]")
        sys.exit(0)
    else:
        console.print("\n[bold red]One or more Kronos model checks failed.[/bold red]")
        sys.exit(1)


def register(app) -> None:  # type: ignore[type-arg]
    import typer

    kronos_app = typer.Typer(name="kronos", help="Kronos model tools.", no_args_is_help=True)

    @kronos_app.command(name="smoke", help="Verify Kronos model loading, inference, and data freshness.")
    def smoke() -> None:
        run_kronos_smoke()

    app.add_typer(kronos_app)
