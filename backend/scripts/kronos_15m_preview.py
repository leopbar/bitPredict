"""
kronos_15m_preview.py — continuous stochastic forecaster for BTC/USDT 15m.

Cycle (repeats forever until Ctrl+C):
  1. Fetch last 512 closed candles from Binance
  2. Run N independent Kronos simulations → show each result live
  3. Show consensus (median / Q10 / Q90 / % bullish) + save to DB
  4. Monitor live: price updates every 5s, countdown, current candle OHLC
  5. When candle closes → fill actuals in DB → show result (✓/✗)
  6. Go to step 1 for the next candle

Context always comes from Binance (never from the application DB).
Results (predictions, actuals, scoreboard) are persisted to the DB.

Usage:
    docker compose exec backend python scripts/kronos_15m_preview.py
    docker compose exec backend python scripts/kronos_15m_preview.py --samples 10
    docker compose exec backend python scripts/kronos_15m_preview.py --temperature 0.6
    docker compose exec backend python scripts/kronos_15m_preview.py --model small
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from rich import box
from rich.console import Console, Group as RichGroup
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ── Kronos model path ─────────────────────────────────────────────────────────

KRONOS_PATH = Path("/app/data/kronos")
if not KRONOS_PATH.exists():
    print("ERROR: /app/data/kronos not found.")
    print("Run: docker compose exec -u root backend python scripts/kronos_setup.py")
    sys.exit(1)
sys.path.insert(0, str(KRONOS_PATH))

SYMBOL   = "BTCUSDT"
TF_VALUE = "15m"
CONTEXT  = 512

console = Console()


# ── Candle timing ─────────────────────────────────────────────────────────────

def _candle_open_now() -> datetime:
    now = datetime.now(tz=UTC)
    return now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)


def _next_candle_open() -> datetime:
    return _candle_open_now() + timedelta(minutes=15)


def _seconds_until_close(target_close: datetime | None = None) -> int:
    end = target_close if target_close is not None else _next_candle_open()
    return max(0, int((end - datetime.now(tz=UTC)).total_seconds()))


def _countdown(secs: int) -> str:
    m, s = divmod(secs, 60)
    return f"{m:02d}:{s:02d}"


# ── Test-mode helpers ─────────────────────────────────────────────────────────

def _simulate_actual_candle(ref_close: float) -> dict:
    """Generate a plausible OHLCV candle near ref_close (used in --test mode only)."""
    import random
    chg    = random.uniform(-0.015, 0.015)   # ±1.5% price change
    open_  = ref_close
    close  = ref_close * (1 + chg)
    high   = max(open_, close) * (1 + random.uniform(0.0005, 0.003))
    low    = min(open_, close) * (1 - random.uniform(0.0005, 0.003))
    volume = ref_close * random.uniform(80, 350)   # rough BTC-equivalent volume
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


# ── Binance helpers ───────────────────────────────────────────────────────────

def _binance(path: str, params: dict):
    with httpx.Client(timeout=15) as c:
        r = c.get(f"https://api.binance.com{path}", params=params)
        r.raise_for_status()
        return r.json()


def fetch_context() -> pd.DataFrame:
    """Fetch last CONTEXT closed 15m candles from Binance (drop the forming candle)."""
    raw = _binance("/api/v3/klines", {
        "symbol": SYMBOL, "interval": TF_VALUE, "limit": CONTEXT + 2,
    })
    rows = [
        {
            "open_time": datetime.fromtimestamp(r[0] / 1000, tz=UTC),
            "open":   float(r[1]),
            "high":   float(r[2]),
            "low":    float(r[3]),
            "close":  float(r[4]),
            "volume": float(r[5]),
        }
        for r in raw[:-1]   # drop last row (still-forming candle)
    ]
    df = pd.DataFrame(rows)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    return df.tail(CONTEXT).reset_index(drop=True)


def fetch_live_candle() -> dict | None:
    try:
        raw = _binance("/api/v3/klines", {"symbol": SYMBOL, "interval": TF_VALUE, "limit": 1})
        r = raw[0]
        return {
            "open_time": datetime.fromtimestamp(r[0] / 1000, tz=UTC),
            "open":   float(r[1]),
            "high":   float(r[2]),
            "low":    float(r[3]),
            "close":  float(r[4]),
            "volume": float(r[5]),
        }
    except Exception:
        return None


def fetch_closed_candle(target_open: datetime) -> dict | None:
    """Fetch the closed candle that opened at target_open. Returns None if not ready."""
    try:
        raw = _binance("/api/v3/klines", {
            "symbol": SYMBOL, "interval": TF_VALUE, "limit": 5,
        })
        for r in raw:
            t = datetime.fromtimestamp(r[0] / 1000, tz=UTC)
            if abs((t - target_open).total_seconds()) < 5:
                return {
                    "open":   float(r[1]),
                    "high":   float(r[2]),
                    "low":    float(r[3]),
                    "close":  float(r[4]),
                    "volume": float(r[5]),
                }
    except Exception:
        pass
    return None


def fetch_price() -> float | None:
    try:
        return float(_binance("/api/v3/ticker/price", {"symbol": SYMBOL})["price"])
    except Exception:
        return None


# ── Kronos loader ─────────────────────────────────────────────────────────────

def load_model(variant: str):
    from model import Kronos, KronosPredictor, KronosTokenizer
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model     = Kronos.from_pretrained(f"NeoQuasar/Kronos-{variant}")
    return KronosPredictor(model, tokenizer, max_context=CONTEXT)


# ── Single simulation ─────────────────────────────────────────────────────────

def run_one(predictor, ctx: pd.DataFrame, target_open: datetime, temperature: float) -> dict:
    pred = predictor.predict(
        df=ctx[["open", "high", "low", "close", "volume"]].copy(),
        x_timestamp=ctx["open_time"].copy(),
        y_timestamp=pd.Series([target_open]),
        pred_len=1,
        T=temperature,
        top_p=0.9,
        sample_count=1,
        verbose=False,
    )
    return {
        "open":   float(pred["open"].iloc[0]),
        "high":   float(pred["high"].iloc[0]),
        "low":    float(pred["low"].iloc[0]),
        "close":  float(pred["close"].iloc[0]),
        "volume": float(pred["volume"].iloc[0]),
    }


# ── DB helpers ────────────────────────────────────────────────────────────────

def save_to_db(samples: list[dict], target_open: datetime, target_close: datetime, variant: str, temperature: float) -> int | None:
    try:
        from sqlalchemy import text as _text
        from bitpredict.db import get_session
        from bitpredict.db_models import KronosPrediction

        closes  = np.array([s["close"]  for s in samples])
        opens   = np.array([s["open"]   for s in samples])
        highs   = np.array([s["high"]   for s in samples])
        lows    = np.array([s["low"]    for s in samples])
        volumes = np.array([s["volume"] for s in samples])
        ref     = float(samples[0]["close"])  # placeholder; will be set from ctx externally

        db = get_session()
        try:
            next_id = db.execute(_text("SELECT nextval('kronos_predictions_id_seq')")).scalar_one()
            record  = KronosPrediction(
                id=next_id,
                timeframe=TF_VALUE,
                predicted_at=datetime.now(tz=UTC),
                target_candle_open_time=target_open,
                target_candle_close_time=target_close,
                predicted_open=float(np.median(opens)),
                predicted_high=float(np.median(highs)),
                predicted_low=float(np.median(lows)),
                predicted_close=float(np.median(closes)),
                predicted_volume=float(np.median(volumes)),
                q10_close=float(np.percentile(closes, 10)),
                q90_close=float(np.percentile(closes, 90)),
                prob_bullish=float(np.mean(closes > float(np.median(closes)))),
                model_variant=variant,
                sample_count=len(samples),
                temperature=temperature,
                context_length=CONTEXT,
                status="done",
            )
            db.add(record)
            db.commit()
            return next_id
        finally:
            db.close()
    except Exception as e:
        console.print(f"[yellow]⚠  DB save failed: {e}[/yellow]")
        return None


def fill_actuals_db(db_id: int, actual: dict, pred_open: float, pred_close: float) -> None:
    try:
        from sqlalchemy import select
        from bitpredict.db import get_session
        from bitpredict.db_models import KronosPrediction

        db = get_session()
        try:
            record = db.execute(
                select(KronosPrediction).where(KronosPrediction.id == db_id)
            ).scalar_one_or_none()
            if record is None:
                return
            record.actual_open   = actual["open"]
            record.actual_high   = actual["high"]
            record.actual_low    = actual["low"]
            record.actual_close  = actual["close"]
            record.actual_volume = actual["volume"]
            pred_bull   = pred_close > pred_open
            actual_bull = actual["close"] > actual["open"]
            record.direction_correct = pred_bull == actual_bull
            record.close_error_pct   = (pred_close - actual["close"]) / actual["close"] * 100
            db.commit()
        finally:
            db.close()
    except Exception as e:
        console.print(f"[yellow]⚠  DB fill actuals failed: {e}[/yellow]")


def load_scoreboard(min_candle_minutes: int = 14) -> dict:
    try:
        from sqlalchemy import select
        from bitpredict.db import get_session
        from bitpredict.db_models import KronosPrediction

        db = get_session()
        try:
            rows = db.execute(
                select(KronosPrediction)
                .where(
                    KronosPrediction.timeframe == TF_VALUE,
                    KronosPrediction.status    == "done",
                    KronosPrediction.actual_close.isnot(None),
                )
                .order_by(KronosPrediction.predicted_at.desc())
                .limit(200)
            ).scalars().all()

            # Exclude test-mode entries (candle duration < min_candle_minutes)
            min_secs = min_candle_minutes * 60
            rows = [
                r for r in rows
                if (r.target_candle_close_time - r.target_candle_open_time).total_seconds() >= min_secs
            ]

            if not rows:
                return {"total": 0}

            errors  = [abs(float(r.close_error_pct)) for r in rows if r.close_error_pct is not None]
            correct = sum(1 for r in rows if r.direction_correct is True)
            return {
                "total":    len(rows),
                "correct":  correct,
                "accuracy": correct / len(rows),
                "mae":      float(np.mean(errors)) if errors else None,
                "best":     float(min(errors))     if errors else None,
                "worst":    float(max(errors))     if errors else None,
            }
        finally:
            db.close()
    except Exception:
        return {"total": 0}


def load_history(limit: int = 8, min_candle_minutes: int = 14) -> list[dict]:
    """
    Returns the last `limit` CLOSED candles (deduplicated by target candle).
    Excludes:
    - Candles that haven't closed yet
    - Test-mode entries (candle duration < min_candle_minutes)
    """
    try:
        from sqlalchemy import select
        from bitpredict.db import get_session
        from bitpredict.db_models import KronosPrediction

        # Only include candles that should already be fully closed
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=1)
        min_secs = min_candle_minutes * 60

        db = get_session()
        try:
            rows = db.execute(
                select(KronosPrediction)
                .where(
                    KronosPrediction.timeframe == TF_VALUE,
                    KronosPrediction.status    == "done",
                    KronosPrediction.target_candle_close_time <= cutoff,
                )
                .order_by(KronosPrediction.predicted_at.desc())
                .limit(limit * 6)   # fetch extra to survive deduplication + duration filter
            ).scalars().all()

            # Exclude test-mode entries (candle duration shorter than expected)
            rows = [
                r for r in rows
                if (r.target_candle_close_time - r.target_candle_open_time).total_seconds() >= min_secs
            ]

            # Deduplicate: keep only the latest prediction per target candle
            seen: set = set()
            deduped = []
            for r in rows:
                key = r.target_candle_open_time
                if key not in seen:
                    seen.add(key)
                    deduped.append(r)
                    if len(deduped) >= limit:
                        break

            return [
                {
                    "target_open":  r.target_candle_open_time,
                    "pred_close":   float(r.predicted_close)  if r.predicted_close  else None,
                    "pred_open":    float(r.predicted_open)   if r.predicted_open   else None,
                    "q10":          float(r.q10_close)        if r.q10_close        else None,
                    "q90":          float(r.q90_close)        if r.q90_close        else None,
                    "prob_bullish": float(r.prob_bullish)     if r.prob_bullish is not None else None,
                    "actual_close": float(r.actual_close)     if r.actual_close     else None,
                    "direction_ok": r.direction_correct,
                    "error_pct":    float(r.close_error_pct)  if r.close_error_pct  else None,
                }
                for r in deduped
            ]
        finally:
            db.close()
    except Exception:
        return []


# ── Rich display ──────────────────────────────────────────────────────────────

def _usd(v: float) -> str:
    return f"${v:,.2f}"


def _pct(a: float, b: float) -> float:
    return (a - b) / abs(b) * 100 if b != 0 else 0.0


def render_header(pred: dict, live_price: float | None, cycle: int, candle_secs: int = 900) -> Panel:
    secs    = _seconds_until_close(pred["target_close"])
    filled  = int((1.0 - secs / candle_secs) * 36)
    bar     = "█" * filled + "░" * (36 - filled)
    now_str = datetime.now(tz=UTC).strftime("%H:%M:%S UTC")

    t = Text()
    t.append("  KRONOS 15m  ", style="bold cyan")
    t.append(f"cycle #{cycle}  ", style="dim")
    t.append(f"{now_str}  ", style="yellow")
    if live_price is not None:
        bull = live_price >= pred.get("ref_close", live_price)
        cc   = "green" if bull else "red"
        t.append(f"Live: [{cc}]{_usd(live_price)}[/{cc}]  ")
    t.append("closes in: ", style="dim")
    t.append(_countdown(secs), style="bold white")
    t.append(f"  [{bar}]", style="dim cyan")
    return Panel(t, border_style="cyan", padding=(0, 1))


def render_prediction(pred: dict) -> Panel:
    bull   = pred.get("prob_bullish", 0) >= 0.5
    pct    = pred.get("prob_bullish", 0) * 100
    n      = pred.get("sample_count", 30)
    bull_n = int(round(pred.get("prob_bullish", 0) * n))
    bear_n = n - bull_n
    accent = "green" if bull else "red"
    arrow  = "▲" if bull else "▼"
    label  = "BULLISH" if bull else "BEARISH"

    t = Table(box=None, show_header=False, padding=(0, 1))
    t.add_column("", style="dim", width=20, no_wrap=True)
    t.add_column("", no_wrap=True)

    t.add_row(
        "Direction",
        f"[{accent} bold]{arrow} {pct:.0f}% {label}[/{accent} bold]"
        f"  [dim]({bull_n}↑ / {bear_n}↓ of {n} sims)[/dim]",
    )
    t.add_row(
        "Expected close",
        f"[bold white]{_usd(pred['pred_close'])}[/bold white]"
        f"  [dim]Δ {_pct(pred['pred_close'], pred['ref_close']):+.3f}%[/dim]",
    )
    t.add_row(
        "Band  [dim](Q10/Q90)[/dim]",
        f"[cyan]{_usd(pred['q10'])}[/cyan] ── [cyan]{_usd(pred['q90'])}[/cyan]"
        f"  [dim]±{_pct(pred['q90'], pred['q10']) / 2:.2f}%[/dim]",
    )
    t.add_row(
        "Pred. O / C",
        f"[dim]O[/dim] {_usd(pred['pred_open'])}  "
        f"[dim]C[/dim] [bold]{_usd(pred['pred_close'])}[/bold]",
    )
    t.add_row(
        "Pred. H / L",
        f"[dim]H[/dim] [green]{_usd(pred['pred_high'])}[/green]  "
        f"[dim]L[/dim] [red]{_usd(pred['pred_low'])}[/red]",
    )
    t.add_row(
        "Target candle",
        f"[bold]{pred['target_open'].strftime('%H:%M')} – "
        f"{pred['target_close'].strftime('%H:%M UTC')}[/bold]",
    )
    t.add_row(
        "Model / temp",
        f"[dim]{pred['variant']}[/dim]  [yellow]T={pred['temperature']}[/yellow]",
    )

    db_id = pred.get("db_id")
    title_id = f"  [dim]id={db_id}[/dim]" if db_id else ""
    return Panel(t,
        title=f"[bold {accent}]PREDICTION{title_id}[/bold {accent}]",
        border_style=accent, padding=(1, 1),
    )


def render_live_candle(
    candle: dict | None,
    live_price: float | None,
    target_close: datetime | None = None,
    candle_secs: int = 900,
) -> Panel:
    if candle is None:
        return Panel(Text("\n  Loading…\n", style="dim"),
            title="[bold]LIVE CANDLE[/bold]", border_style="dim")

    t = Table(box=None, show_header=False, padding=(0, 1))
    t.add_column("", style="dim", width=12, no_wrap=True)
    t.add_column("", no_wrap=True)

    open_str  = candle["open_time"].strftime("%H:%M")
    close_str = (candle["open_time"] + timedelta(minutes=15)).strftime("%H:%M UTC")
    t.add_row("Candle", f"[bold]{open_str} → {close_str}[/bold]")
    t.add_row("Open",   f"[white]{_usd(candle['open'])}[/white]")
    t.add_row("High",   f"[green]{_usd(candle['high'])}[/green]")
    t.add_row("Low",    f"[red]{_usd(candle['low'])}[/red]")

    if live_price is not None:
        chg = _pct(live_price, candle["open"])
        cc  = "green" if chg >= 0 else "red"
        t.add_row("Price", f"[{cc} bold]{_usd(live_price)} ({chg:+.3f}%)[/{cc} bold]")

    secs   = _seconds_until_close(target_close)
    filled = int((1.0 - secs / candle_secs) * 14)
    bar    = "█" * filled + "░" * (14 - filled)
    t.add_row("Closes", f"[bold yellow]{_countdown(secs)}[/bold yellow] [dim][{bar}][/dim]")

    return Panel(t, title="[bold yellow]LIVE CANDLE[/bold yellow]",
        border_style="yellow", padding=(0, 1))


def render_scoreboard(sb: dict) -> Panel:
    if sb.get("total", 0) == 0:
        return Panel(
            Text("\n  No evaluated predictions yet.\n  Waiting for first close…\n", style="dim"),
            title="[bold]SCOREBOARD[/bold]", border_style="dim",
        )

    n   = sb["total"]
    acc = sb["accuracy"] * 100
    ac  = "green" if acc >= 60 else "yellow" if acc >= 50 else "red"
    mc  = "green" if (sb.get("mae") or 1) < 0.5 else \
          "yellow" if (sb.get("mae") or 1) < 1.5 else "red"

    t = Table(box=None, show_header=False, padding=(0, 1))
    t.add_column("", style="dim", width=14, no_wrap=True)
    t.add_column("", no_wrap=True)

    t.add_row("Evaluated",  f"[bold]{n}[/bold] [dim]candles[/dim]")
    t.add_row("Direction",  f"[{ac} bold]{sb['correct']}/{n} ({acc:.0f}%)[/{ac} bold]")
    if sb.get("mae") is not None:
        t.add_row("Avg error", f"[{mc} bold]{sb['mae']:.3f}%[/{mc} bold]")
    if sb.get("best") is not None:
        t.add_row("Best",      f"[green]{sb['best']:.3f}%[/green]")
    if sb.get("worst") is not None:
        t.add_row("Worst",     f"[red]{sb['worst']:.3f}%[/red]")

    return Panel(t, title="[bold green]SCOREBOARD[/bold green]",
        border_style="green", padding=(0, 1))


def render_history(history: list[dict]) -> Panel:
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", expand=True)
    t.add_column("#",           width=3,  justify="right")
    t.add_column("Candle",      width=8)
    t.add_column("Dir",         width=5,  justify="center")
    t.add_column("Pred. Close", width=13, justify="right")
    t.add_column("Q10 – Q90",   width=24, justify="right")
    t.add_column("Actual",      width=13, justify="right")
    t.add_column("Error",       width=9,  justify="right")
    t.add_column("✓",           width=3,  justify="center")

    for i, h in enumerate(history, 1):
        candle_str = h["target_open"].strftime("%H:%M") if h.get("target_open") else "—"
        bull_pred  = (h.get("prob_bullish") or 0) >= 0.5
        d_col      = "green" if bull_pred else "red"
        d_str      = "▲" if bull_pred else "▼"

        band = (
            f"[dim]{_usd(h['q10'])}–{_usd(h['q90'])}[/dim]"
            if h.get("q10") and h.get("q90") else "[dim]—[/dim]"
        )
        actual = _usd(h["actual_close"]) if h.get("actual_close") else "[dim]pending[/dim]"

        err     = h.get("error_pct")
        err_str = f"{err:+.3f}%" if err is not None else "—"
        err_col = ("green"  if err is not None and abs(err) < 0.5  else
                   "yellow" if err is not None and abs(err) < 1.5  else "red")

        ok     = h.get("direction_ok")
        result = "[green]✓[/green]" if ok is True else \
                 "[red]✗[/red]"     if ok is False else "[dim]·[/dim]"

        t.add_row(
            str(i),
            candle_str,
            f"[{d_col} bold]{d_str}[/{d_col} bold]",
            _usd(h["pred_close"]) if h.get("pred_close") else "—",
            band, actual,
            f"[{err_col}]{err_str}[/{err_col}]",
            result,
        )

    evaluated = sum(1 for h in history if h.get("direction_ok") is not None)
    return Panel(t,
        title=f"[bold]HISTORY  [dim](last {len(history)} · {evaluated} evaluated)[/dim][/bold]",
        border_style="dim", padding=(0, 1),
    )


# ── Phase 1: inference with live table ───────────────────────────────────────

def run_inference_cycle(
    predictor,
    ctx: pd.DataFrame,
    target_open: datetime,
    temperature: float,
    n_samples: int,
    variant: str,
    cycle: int,
    candle_minutes: int = 15,
) -> dict:
    """Run N simulations, display each row live, return consensus dict."""
    ref_close    = float(ctx["close"].iloc[-1])
    target_close = target_open + timedelta(minutes=candle_minutes)

    console.print()
    console.rule(
        f"[bold cyan]Cycle #{cycle}[/bold cyan]  ·  "
        f"target [bold]{target_open.strftime('%H:%M')}–{target_close.strftime('%H:%M UTC')}[/bold]  ·  "
        f"ref close [bold white]{_usd(ref_close)}[/bold white]"
    )
    console.print()

    sim_table = Table(
        title=f"[bold]{n_samples} simulations[/bold]  "
              f"[dim]model: {variant}  T={temperature}  context: {CONTEXT} candles[/dim]",
        box=box.SIMPLE_HEAD, header_style="bold dim", expand=True,
    )
    sim_table.add_column("#",      width=4,  justify="right",  style="dim")
    sim_table.add_column("Close",  width=13, justify="right")
    sim_table.add_column("Open",   width=13, justify="right",  style="dim")
    sim_table.add_column("High",   width=13, justify="right",  style="dim")
    sim_table.add_column("Low",    width=13, justify="right",  style="dim")
    sim_table.add_column("Dir",    width=5,  justify="center")
    sim_table.add_column("ΔClose", width=10, justify="right")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Simulating…[/cyan]"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )
    task = progress.add_task("", total=n_samples)

    samples: list[dict] = []
    with Live(RichGroup(sim_table, progress), console=console, refresh_per_second=4):
        for i in range(n_samples):
            s = run_one(predictor, ctx, target_open, temperature)
            samples.append(s)

            bull  = s["close"] > ref_close
            d_col = "green" if bull else "red"
            d_str = "▲" if bull else "▼"
            delta = _pct(s["close"], ref_close)
            dc    = "green" if delta >= 0 else "red"

            sim_table.add_row(
                str(i + 1),
                f"[bold white]{_usd(s['close'])}[/bold white]",
                _usd(s["open"]),
                f"[green]{_usd(s['high'])}[/green]",
                f"[red]{_usd(s['low'])}[/red]",
                f"[{d_col} bold]{d_str}[/{d_col} bold]",
                f"[{dc}]{delta:+.3f}%[/{dc}]",
            )
            progress.advance(task)

    closes  = np.array([s["close"]  for s in samples])
    opens   = np.array([s["open"]   for s in samples])
    highs   = np.array([s["high"]   for s in samples])
    lows    = np.array([s["low"]    for s in samples])
    volumes = np.array([s["volume"] for s in samples])

    bull_n = int(np.sum(closes > ref_close))
    bear_n = n_samples - bull_n
    bar    = "[green]" + "█" * bull_n + "[/green][red]" + "░" * bear_n + "[/red]"
    console.print(f"\n  {bar}  [green]{bull_n}↑[/green] / [red]{bear_n}↓[/red]  "
                  f"spread [cyan]{_usd(float(np.min(closes)))}[/cyan]→"
                  f"[cyan]{_usd(float(np.max(closes)))}[/cyan]\n")

    prob_bull = float(np.mean(closes > ref_close))

    pred = {
        "ref_close":    ref_close,
        "pred_open":    float(np.median(opens)),
        "pred_high":    float(np.median(highs)),
        "pred_low":     float(np.median(lows)),
        "pred_close":   float(np.median(closes)),
        "pred_volume":  float(np.median(volumes)),
        "q10":          float(np.percentile(closes, 10)),
        "q90":          float(np.percentile(closes, 90)),
        "prob_bullish": prob_bull,
        "sample_count": len(samples),
        "temperature":  temperature,
        "variant":      variant,
        "target_open":  target_open,
        "target_close": target_close,
        "db_id":        None,
    }

    with console.status("[cyan]Saving to database…[/cyan]"):
        db_id = save_to_db(samples, target_open, target_close, variant, temperature)
        pred["db_id"] = db_id

    if db_id:
        console.print(f"[green]✓[/green] Saved to DB (id={db_id})\n")
    return pred


# ── Phase 2: live monitor until candle closes ─────────────────────────────────

def monitor_until_close(pred: dict, cycle: int, test_mode: bool = False) -> dict | None:
    """
    Show live layout until the target candle closes.
    Returns the actual closed candle dict (real or simulated), or None on Ctrl+C.

    test_mode=True: closes after 1 minute with a randomly simulated candle.

    Layout:
      header (3 lines)
      body row:
        left  (ratio=3) → prediction panel
        right (ratio=2) → candle (top) + scoreboard (bottom)
      history (bottom)
    """
    candle_secs        = 60 if test_mode else 900
    min_candle_minutes = 1  if test_mode else 14

    layout = Layout()
    layout.split_column(
        Layout(name="header",  size=3),
        Layout(name="body",    size=16),
        Layout(name="history"),
    )
    layout["body"].split_row(
        Layout(name="prediction", ratio=3),
        Layout(name="right_col",  ratio=2),
    )
    layout["right_col"].split_column(
        Layout(name="candle"),
        Layout(name="scoreboard"),
    )

    candle:     dict | None = None
    live_price: float | None = None
    scoreboard: dict = load_scoreboard()
    history:    list[dict] = load_history()

    def _refresh():
        nonlocal candle, live_price, scoreboard, history
        candle     = fetch_live_candle()
        live_price = fetch_price()
        scoreboard = load_scoreboard(min_candle_minutes=min_candle_minutes)
        history    = load_history(min_candle_minutes=min_candle_minutes)

    # Small buffer before declaring the candle closed
    close_buffer = timedelta(seconds=3) if test_mode else timedelta(seconds=10)

    try:
        with Live(layout, console=console, refresh_per_second=0.5, screen=True):
            while True:
                _refresh()

                layout["header"].update(render_header(pred, live_price, cycle, candle_secs))
                layout["body"]["prediction"].update(render_prediction(pred))
                layout["body"]["right_col"]["candle"].update(
                    render_live_candle(candle, live_price, pred["target_close"], candle_secs)
                )
                layout["body"]["right_col"]["scoreboard"].update(render_scoreboard(scoreboard))
                layout["history"].update(render_history(history))

                now = datetime.now(tz=UTC)
                if now >= pred["target_close"] + close_buffer:
                    if test_mode:
                        return _simulate_actual_candle(pred["ref_close"])
                    actual = fetch_closed_candle(pred["target_open"])
                    if actual:
                        return actual

                time.sleep(5)

    except KeyboardInterrupt:
        return None


# ── Show candle result after close ───────────────────────────────────────────

def show_result(pred: dict, actual: dict) -> None:
    pred_c  = pred["pred_close"]
    actual_c = actual["close"]
    err     = (pred_c - actual_c) / actual_c * 100

    pred_bull   = pred_c   > pred["pred_open"]
    actual_bull = actual_c > actual["open"]
    correct     = pred_bull == actual_bull

    accent   = "green" if correct else "red"
    result   = "✓  CORRECT" if correct else "✗  WRONG"
    err_col  = "green" if abs(err) < 0.5 else "yellow" if abs(err) < 1.5 else "red"

    t = Table(box=None, show_header=False, padding=(0, 3))
    t.add_column("", style="dim", width=22)
    t.add_column("")

    t.add_row("Direction",       f"[{accent} bold]{result}[/{accent} bold]")
    t.add_row("Predicted close", f"[bold white]{_usd(pred_c)}[/bold white]")
    t.add_row("Actual close",    f"[bold white]{_usd(actual_c)}[/bold white]")
    t.add_row("Close error",     f"[{err_col} bold]{err:+.3f}%[/{err_col} bold]")
    t.add_row("Predicted OHLC",
        f"O {_usd(pred['pred_open'])}  "
        f"H [green]{_usd(pred['pred_high'])}[/green]  "
        f"L [red]{_usd(pred['pred_low'])}[/red]",
    )
    t.add_row("Actual OHLC",
        f"O {_usd(actual['open'])}  "
        f"H [green]{_usd(actual['high'])}[/green]  "
        f"L [red]{_usd(actual['low'])}[/red]",
    )

    console.print()
    console.print(Panel(t,
        title=f"[bold {accent}]CANDLE CLOSED — {pred['target_open'].strftime('%H:%M UTC')}[/bold {accent}]",
        border_style=accent, padding=(1, 2),
    ))
    console.print()


# ── Main loop ─────────────────────────────────────────────────────────────────

def main(variant: str, temperature: float, n_samples: int, test_mode: bool = False) -> None:
    candle_minutes = 1 if test_mode else 15

    console.print()
    test_badge = "  [bold yellow blink]⚡ TEST MODE — 1-min simulated cycles[/bold yellow blink]" if test_mode else ""
    console.print(Panel(
        f"[bold cyan]Kronos 15m — Continuous Forecaster[/bold cyan]  ·  BTC/USDT{test_badge}\n"
        f"[dim]Model:[/dim] [bold]kronos-{variant}[/bold]   "
        f"[dim]Temperature:[/dim] [bold yellow]{temperature}[/bold yellow]   "
        f"[dim]Samples/cycle:[/dim] [bold]{n_samples}[/bold]   "
        f"[dim]Context:[/dim] [bold]{CONTEXT} candles from Binance[/bold]\n"
        f"[dim]Ctrl+C to stop · Results saved to DB across sessions[/dim]",
        border_style="cyan" if not test_mode else "yellow", padding=(0, 2),
    ))
    console.print()

    with console.status("[cyan]Loading Kronos model…[/cyan]"):
        predictor = load_model(variant)
    console.print(f"[green]✓[/green] Kronos-{variant} loaded\n")

    cycle = 1
    while True:
        # ── 0. Startup timing guard (normal mode only) ────────────────────────
        # If less than 1 minute remains until the next 15m candle closes,
        # wait for it to finish before starting inference — otherwise the
        # monitoring window would be too short for the first cycle.
        if not test_mode:
            secs = _seconds_until_close()
            if secs < 60:
                console.print(
                    f"\n[yellow]⏳ Only [bold]{secs}s[/bold] until the next 15m candle closes. "
                    f"Waiting for a clean start…[/yellow]"
                )
                time.sleep(secs + 8)   # +8s buffer so Binance has the candle ready
                console.print("[green]✓ Candle closed — starting inference now.[/green]\n")

        # ── 1. Fetch fresh context from Binance ───────────────────────────────
        console.print(f"[dim]Fetching {CONTEXT} candles from Binance…[/dim]")
        try:
            ctx = fetch_context()
            console.print(
                f"[green]✓[/green] Context: [bold]{len(ctx)}[/bold] candles  "
                f"· Last close: [bold white]{_usd(float(ctx['close'].iloc[-1]))}[/bold white]\n"
            )
        except Exception as e:
            console.print(f"[red]✗  Failed to fetch context: {e}[/red]")
            console.print("[dim]Retrying in 30s…[/dim]")
            time.sleep(30)
            continue

        if test_mode:
            # In test mode: target is "now + 1 min" (rounded to the current second)
            target_open = datetime.now(tz=UTC).replace(microsecond=0)
        else:
            target_open = _next_candle_open()

        # ── 2. Run inference (shows table live) ───────────────────────────────
        try:
            pred = run_inference_cycle(
                predictor=predictor,
                ctx=ctx,
                target_open=target_open,
                temperature=temperature,
                n_samples=n_samples,
                variant=variant,
                cycle=cycle,
                candle_minutes=candle_minutes,
            )
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]✗  Inference error: {e}[/red]")
            time.sleep(10)
            continue

        # ── 3. Live monitor until candle closes ───────────────────────────────
        actual = monitor_until_close(pred, cycle, test_mode=test_mode)
        if actual is None:
            # Ctrl+C during live monitor
            break

        # ── 4. Fill actuals in DB + show result ───────────────────────────────
        if pred.get("db_id"):
            with console.status("[cyan]Updating DB with actual OHLC…[/cyan]"):
                fill_actuals_db(pred["db_id"], actual, pred["pred_open"], pred["pred_close"])

        show_result(pred, actual)

        # ── 5. Brief pause, then next cycle ──────────────────────────────────
        sb = load_scoreboard()
        if sb.get("total", 0) > 0:
            acc = sb["accuracy"] * 100
            ac  = "green" if acc >= 60 else "yellow" if acc >= 50 else "red"
            console.print(
                f"  Scoreboard: [{ac} bold]{sb['correct']}/{sb['total']} ({acc:.0f}%)[/{ac} bold]"
                + (f"  · avg error [bold]{sb['mae']:.3f}%[/bold]" if sb.get("mae") else "")
            )

        console.print(f"\n[dim]Starting cycle #{cycle + 1} in 3s…[/dim]\n")
        time.sleep(3)
        cycle += 1

    # ── Exit summary ──────────────────────────────────────────────────────────
    console.print()
    console.rule("[bold]Session ended[/bold]")
    sb = load_scoreboard()
    if sb.get("total", 0) > 0:
        acc = sb["accuracy"] * 100
        ac  = "green" if acc >= 60 else "yellow" if acc >= 50 else "red"
        console.print(
            f"  DB scoreboard (15m): [{ac} bold]{sb['correct']}/{sb['total']} "
            f"direction accuracy ({acc:.0f}%)[/{ac} bold]"
            + (f"  · avg error [bold]{sb['mae']:.3f}%[/bold]" if sb.get("mae") else "")
        )
    else:
        console.print("  No evaluated predictions in DB for 15m.")
    console.print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Kronos 15m — continuous stochastic forecaster"
    )
    parser.add_argument("--model",       choices=["mini", "small", "base"], default="base")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--samples",     type=int,   default=30)
    parser.add_argument(
        "--test", action="store_true",
        help="Test mode: simulate candle close after 1 min with random values near real price.",
    )
    args = parser.parse_args()
    main(variant=args.model, temperature=args.temperature, n_samples=args.samples, test_mode=args.test)
