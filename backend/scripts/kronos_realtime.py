"""
Kronos Real-Time — previsão candle a candle em tempo real.

Fluxo:
  1. Carrega últimos 512 candles (parquet + Binance para os mais recentes)
  2. Kronos prevê o próximo candle de 15min
  3. Tela atualiza a cada 5s mostrando preço ao vivo e countdown
  4. Quando o candle fecha → compara previsão vs realidade → próximo ciclo

Uso:
    docker compose exec backend python scripts/kronos_realtime.py
    docker compose exec backend python scripts/kronos_realtime.py --model base
"""
from __future__ import annotations

import argparse
import random
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import polars as pl
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

KRONOS_PATH = Path("/app/data/kronos")
if not KRONOS_PATH.exists():
    print("ERRO: /app/data/kronos não encontrado.")
    print("Rode: docker compose exec -u root backend python scripts/kronos_setup.py")
    sys.exit(1)
sys.path.insert(0, str(KRONOS_PATH))

DATA_PATH = Path("/app/data/raw/btcusdt_15m.parquet")
SYMBOL = "BTCUSDT"
INTERVAL = "15m"
CONTEXT_LEN = 512
BINANCE_BASE = "https://api.binance.com"

console = Console()


# ---------------------------------------------------------------------------
# Binance helpers (sync, sem autenticação)
# ---------------------------------------------------------------------------

def _binance_get(path: str, params: dict) -> list | dict:
    url = f"{BINANCE_BASE}{path}"
    with httpx.Client(timeout=10) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        return r.json()


def fetch_current_price() -> float:
    data = _binance_get("/api/v3/ticker/price", {"symbol": SYMBOL})
    return float(data["price"])


def fetch_recent_klines(limit: int = 10) -> pd.DataFrame:
    """Fetch recent closed + current 15min candles from Binance."""
    raw = _binance_get("/api/v3/klines", {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": limit,
    })
    rows = []
    for r in raw:
        rows.append({
            "open_time": datetime.fromtimestamp(r[0] / 1000, tz=UTC),
            "open":  float(r[1]),
            "high":  float(r[2]),
            "low":   float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        })
    df = pd.DataFrame(rows)
    # Ensure datetime64[ns, UTC] — object dtype breaks .dt accessor comparisons
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    return df


def fetch_live_candle() -> dict:
    """Return the currently-forming candle (last row from Binance)."""
    df = fetch_recent_klines(limit=2)
    row = df.iloc[-1]
    return {
        "open_time": row["open_time"],
        "open":  row["open"],
        "high":  row["high"],
        "low":   row["low"],
        "close": row["close"],
        "volume": row["volume"],
    }


# ---------------------------------------------------------------------------
# Parquet helpers
# ---------------------------------------------------------------------------

COLS = ["open_time", "open", "high", "low", "close", "volume"]


def _load_parquet() -> pd.DataFrame:
    """Load parquet, returning empty DataFrame if missing or corrupted."""
    if not DATA_PATH.exists():
        return pd.DataFrame(columns=COLS)
    try:
        df = pl.read_parquet(DATA_PATH).select(COLS).to_pandas()
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        return df
    except Exception:
        # Corrupted — delete and start fresh
        DATA_PATH.unlink(missing_ok=True)
        return pd.DataFrame(columns=COLS)


def update_parquet() -> int:
    """Fetch latest closed candles from Binance and append to parquet.

    Returns the number of new rows added.
    """
    df_hist = _load_parquet()

    # How many candles to request: fill from scratch or just refresh tail
    limit = CONTEXT_LEN + 1 if df_hist.empty else 30
    df_new = fetch_recent_klines(limit=limit)
    df_new = df_new.iloc[:-1]  # drop the still-open candle

    if df_hist.empty:
        merged = df_new
    else:
        cutoff = df_hist["open_time"].max()
        df_new = df_new[df_new["open_time"] > cutoff]
        merged = pd.concat([df_hist, df_new], ignore_index=True)

    merged = merged.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    pl.from_pandas(merged).write_parquet(DATA_PATH)

    return len(df_new)


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def build_context() -> pd.DataFrame:
    """Read parquet and return the last CONTEXT_LEN closed candles."""
    df = _load_parquet()
    if df.empty:
        raise RuntimeError("Parquet vazio — rode update_parquet() primeiro.")
    df = df.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)
    return df.tail(CONTEXT_LEN).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Candle timing
# ---------------------------------------------------------------------------

def current_candle_open() -> datetime:
    """UTC open time of the currently-forming 15min candle."""
    now = datetime.now(tz=UTC)
    minutes = (now.minute // 15) * 15
    return now.replace(minute=minutes, second=0, microsecond=0)


def next_candle_open() -> datetime:
    return current_candle_open() + timedelta(minutes=15)


def seconds_until_close() -> int:
    return max(0, int((next_candle_open() - datetime.now(tz=UTC)).total_seconds()))


# ---------------------------------------------------------------------------
# Kronos loader (cached)
# ---------------------------------------------------------------------------

_predictor_cache: dict = {}


def get_predictor(model_variant: str):
    if "predictor" not in _predictor_cache:
        from model import Kronos, KronosPredictor, KronosTokenizer
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        model = Kronos.from_pretrained(f"NeoQuasar/Kronos-{model_variant}")
        _predictor_cache["predictor"] = KronosPredictor(model, tokenizer, max_context=CONTEXT_LEN)
    return _predictor_cache["predictor"]


# ---------------------------------------------------------------------------
# Prediction runner (called in background thread)
# ---------------------------------------------------------------------------

def run_kronos_prediction(ctx_df: pd.DataFrame, predictor, candle_open: datetime) -> dict | None:
    """Run Kronos and return predicted next candle as dict."""
    try:
        x_df = ctx_df[["open", "high", "low", "close", "volume"]].copy()
        x_timestamp = ctx_df["open_time"].copy()
        y_timestamp = pd.Series([candle_open])

        pred_df = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=1,
            T=1.0,
            top_p=0.9,
            sample_count=5,
            verbose=False,
        )

        last_close = float(ctx_df["close"].iloc[-1])
        p_close = float(pred_df["close"].iloc[0])
        p_high  = float(pred_df["high"].iloc[0])
        p_low   = float(pred_df["low"].iloc[0])

        return {
            "candle_open": candle_open,
            "pred_close": p_close,
            "pred_high":  p_high,
            "pred_low":   p_low,
            "pred_dir":   "▲" if p_close > last_close else "▼",
            "ref_close":  last_close,
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _fmt_price(v: float) -> str:
    return f"${v:,.2f}"


def _dir_color(d: str) -> str:
    return "green" if d == "▲" else "red"


def _pct(a: float, b: float) -> float:
    return (a - b) / abs(b) * 100 if b != 0 else 0.0


def make_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="middle", size=14),
        Layout(name="footer"),
    )
    layout["middle"].split_row(
        Layout(name="prediction"),
        Layout(name="live_candle"),
        Layout(name="scoreboard"),
    )
    return layout


def render_header(state: dict) -> Panel:
    now_str = datetime.now(tz=UTC).strftime("%H:%M:%S UTC")
    secs = seconds_until_close()
    mins, s = divmod(secs, 60)
    t = Text()
    t.append("  KRONOS REAL-TIME  ", style="bold cyan")
    t.append(" BTC/USDT 15min  ", style="dim")
    t.append(f" {now_str}  ", style="yellow")
    t.append("  Próximo candle fecha em: ", style="dim")
    t.append(f"{mins:02d}:{s:02d}", style="bold white")
    bar_pct = 1.0 - secs / 900
    bar_filled = int(bar_pct * 40)
    bar = "█" * bar_filled + "░" * (40 - bar_filled)
    t.append(f"  [{bar}]", style="dim cyan")
    return Panel(t, border_style="cyan", padding=(0, 1))


def render_prediction(state: dict) -> Panel:
    pred = state.get("prediction")
    is_loading = state.get("predicting", False)

    if is_loading:
        return Panel(
            Text("\n  ⏳  Kronos calculando previsão...\n", style="yellow italic"),
            title="[bold]PREVISÃO KRONOS[/bold]",
            border_style="yellow",
        )

    if pred is None:
        return Panel(
            Text("\n  Aguardando primeira previsão...\n", style="dim"),
            title="[bold]PREVISÃO KRONOS[/bold]",
            border_style="dim",
        )

    if "error" in pred:
        return Panel(
            Text(f"\n  ❌ {pred['error']}\n", style="red"),
            title="[bold]PREVISÃO KRONOS[/bold]",
            border_style="red",
        )

    d = pred["pred_dir"]
    dc = _dir_color(d)
    candle_str = pred["candle_open"].strftime("%H:%M UTC")

    t = Table(box=None, show_header=False, padding=(0, 2))
    t.add_column("", style="dim", width=20)
    t.add_column("", width=20)

    t.add_row("Candle previsto", f"[bold]{candle_str}[/bold]")
    t.add_row("Direção", f"[{dc} bold]{d}  {'ALTA' if d == '▲' else 'BAIXA'}[/{dc} bold]")
    t.add_row("Fechamento previsto", f"[bold white]{_fmt_price(pred['pred_close'])}[/bold white]")
    t.add_row("Máxima prevista", f"[green]{_fmt_price(pred['pred_high'])}[/green]")
    t.add_row("Mínima prevista", f"[red]{_fmt_price(pred['pred_low'])}[/red]")
    chg = _pct(pred["pred_close"], pred["ref_close"])
    t.add_row("Variação prevista", f"[{dc}]{chg:+.3f}%[/{dc}]")

    return Panel(t, title="[bold cyan]PREVISÃO KRONOS[/bold cyan]", border_style="cyan", padding=(1, 1))


def render_live_candle(state: dict) -> Panel:
    c = state.get("live_candle")
    cur_price = state.get("current_price")

    if c is None:
        return Panel(Text("\n  Carregando...\n", style="dim"), title="[bold]CANDLE ATUAL[/bold]", border_style="dim")

    t = Table(box=None, show_header=False, padding=(0, 2))
    t.add_column("", style="dim", width=20)
    t.add_column("", width=20)

    candle_str = c["open_time"].strftime("%H:%M UTC")
    t.add_row("Abertura do candle", f"[bold]{candle_str}[/bold]")
    t.add_row("Abertura (preço)", f"[white]{_fmt_price(c['open'])}[/white]")
    t.add_row("Máxima até agora", f"[green]{_fmt_price(c['high'])}[/green]")
    t.add_row("Mínima até agora", f"[red]{_fmt_price(c['low'])}[/red]")

    if cur_price is not None:
        chg = _pct(cur_price, c["open"])
        cc = "green" if chg >= 0 else "red"
        t.add_row("Preço atual", f"[{cc} bold]{_fmt_price(cur_price)}  ({chg:+.3f}%)[/{cc} bold]")
        updated = datetime.now(tz=UTC).strftime("%H:%M:%S")
        t.add_row("Atualizado", f"[dim]{updated} UTC[/dim]")

    return Panel(t, title="[bold yellow]CANDLE ATUAL (ao vivo)[/bold yellow]", border_style="yellow", padding=(1, 1))


def render_scoreboard(state: dict) -> Panel:
    history = state.get("history", [])
    n = len(history)

    if n == 0:
        return Panel(
            Text("\n  Nenhuma previsão concluída ainda.\n  Aguarde o candle fechar...\n", style="dim"),
            title="[bold]PLACAR[/bold]",
            border_style="dim",
        )

    hits = sum(1 for h in history if h.get("correct"))
    errors = [h["error_pct"] for h in history if "error_pct" in h]
    mae = float(np.mean(errors)) if errors else 0.0
    acc = hits / n * 100

    acc_color = "green" if acc >= 60 else "yellow" if acc >= 50 else "red"
    mae_color = "green" if mae < 0.3 else "yellow" if mae < 1.0 else "red"

    t = Table(box=None, show_header=False, padding=(0, 2))
    t.add_column("", style="dim", width=22)
    t.add_column("", width=18)

    t.add_row("Previsões concluídas", f"[bold]{n}[/bold]")
    t.add_row("Acertos de direção", f"[{acc_color} bold]{hits}/{n}  ({acc:.0f}%)[/{acc_color} bold]")
    t.add_row("Erro médio (preço)", f"[{mae_color} bold]{mae:.3f}%[/{mae_color} bold]")
    if errors:
        t.add_row("Melhor previsão", f"[green]{min(errors):.3f}%[/green]")
        t.add_row("Pior previsão", f"[red]{max(errors):.3f}%[/red]")

    return Panel(t, title="[bold green]PLACAR DA SESSÃO[/bold green]", border_style="green", padding=(1, 1))


def render_history(state: dict) -> Panel:
    history = state.get("history", [])

    t = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold dim",
        expand=True,
    )
    t.add_column("#", width=3, justify="right")
    t.add_column("Horário", width=10)
    t.add_column("Dir. Prevista", justify="center", width=14)
    t.add_column("Fech. Previsto", justify="right", width=16)
    t.add_column("Fech. Real", justify="right", width=14)
    t.add_column("Erro %", justify="right", width=9)
    t.add_column("Acerto?", justify="center", width=9)

    for i, h in enumerate(reversed(history), 1):
        n = len(history) - i + 1
        d = h.get("pred_dir", "?")
        dc = _dir_color(d)
        correct = h.get("correct")
        result_icon = "[green]✓[/green]" if correct else "[red]✗[/red]"
        err = h.get("error_pct")
        err_str = f"{err:.3f}%" if err is not None else "—"
        err_color = "green" if (err or 0) < 0.3 else "yellow" if (err or 0) < 1.0 else "red"

        t.add_row(
            str(n),
            h.get("candle_str", "—"),
            f"[{dc} bold]{d}[/{dc} bold]",
            _fmt_price(h["pred_close"]) if "pred_close" in h else "—",
            _fmt_price(h["real_close"]) if "real_close" in h else "—",
            f"[{err_color}]{err_str}[/{err_color}]",
            result_icon if correct is not None else "[dim]—[/dim]",
        )

    title = f"[bold]HISTÓRICO DA SESSÃO[/bold] [dim]({len(history)} previsões)[/dim]"
    return Panel(t, title=title, border_style="dim", padding=(0, 1))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main(model_variant: str = "small", test_mode: bool = False) -> None:
    console.print(Panel(
        "[bold cyan]Kronos Real-Time[/bold cyan] — BTC/USDT 15min\n"
        "[dim]Previsão candle a candle · atualiza a cada 5s · Ctrl+C para sair[/dim]",
        border_style="cyan",
    ))

    with console.status("[cyan]Carregando modelo Kronos...[/cyan]"):
        predictor = get_predictor(model_variant)
    console.print(f"[green]✓[/green] Kronos-{model_variant} carregado\n")

    # Shared state (accessed by main thread + prediction thread)
    state: dict = {
        "prediction": None,   # previsão mais recente (para exibir)
        "predicting": False,
        "live_candle": None,
        "current_price": None,
        "history": [],
        # pending: dict[candle_open_time_str -> pred_dict]
        # guarda todas as previsões aguardando o candle fechar
        "pending": {},
    }
    state_lock = threading.Lock()

    def _predict_async(candle_open: datetime) -> None:
        """Atualiza parquet, constrói contexto e roda Kronos em background."""
        with state_lock:
            state["predicting"] = True
        try:
            update_parquet()
            ctx = build_context()
            result = run_kronos_prediction(ctx, predictor, candle_open)
        except Exception as e:
            result = {"error": str(e)}
        with state_lock:
            state["predicting"] = False
            state["prediction"] = result
            # Guarda em pending para comparar quando o candle fechar
            if result and "error" not in result and result.get("candle_open"):
                key = result["candle_open"].isoformat()
                state["pending"][key] = result

    def _check_and_close_candles() -> None:
        """Varre pending e registra resultados dos candles já fechados."""
        now = datetime.now(tz=UTC)
        with state_lock:
            pending_copy = dict(state["pending"])

        for key, pred in pending_copy.items():
            pred_candle: datetime = pred["candle_open"]
            candle_close_time = pred_candle + timedelta(minutes=15)

            # Aguarda o candle fechar (+ 5s de margem para Binance atualizar)
            if now < candle_close_time + timedelta(seconds=5):
                continue

            try:
                df = fetch_recent_klines(limit=10)
                # Range comparison: any candle whose open_time falls within the 15-min window
                t0 = pd.Timestamp(pred_candle)
                t1 = t0 + pd.Timedelta(minutes=15)
                match = df[(df["open_time"] >= t0) & (df["open_time"] < t1)]
                if match.empty:
                    continue

                real_close = float(match.iloc[0]["close"])
                real_dir = "▲" if real_close > pred["ref_close"] else "▼"
                correct = pred["pred_dir"] == real_dir
                err_pct = abs(pred["pred_close"] - real_close) / abs(real_close) * 100

                with state_lock:
                    state["history"].append({
                        "candle_str": pred_candle.strftime("%H:%M"),
                        "pred_dir":   pred["pred_dir"],
                        "pred_close": pred["pred_close"],
                        "real_close": real_close,
                        "real_dir":   real_dir,
                        "correct":    correct,
                        "error_pct":  err_pct,
                    })
                    # Remove do pending após registrar
                    state["pending"].pop(key, None)

            except Exception:
                pass

    # Ensure parquet is up-to-date before first prediction
    with console.status("[cyan]Atualizando dados históricos...[/cyan]"):
        try:
            added = update_parquet()
            console.print(f"[green]✓[/green] Parquet atualizado (+{added} candles)\n")
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Falha ao atualizar parquet: {e}\n")

    # TEST MODE: inject fake past predictions to verify history/scoreboard immediately
    if test_mode:
        console.print("[yellow bold]MODO TESTE:[/yellow bold] injetando previsões passadas...\n")
        try:
            current_price = fetch_current_price()
        except Exception:
            current_price = 76000.0
        now_utc = datetime.now(tz=UTC)
        for i in range(1, 4):  # 3 candles: 15, 30, 45 min atrás
            minutes_ago = i * 15 + 2
            past_time = now_utc - timedelta(minutes=minutes_ago)
            minutes_floor = (past_time.minute // 15) * 15
            candle_open = past_time.replace(minute=minutes_floor, second=0, microsecond=0)
            fake_close = current_price * (1 + random.uniform(-0.005, 0.005))
            ref_close  = current_price * (1 + random.uniform(-0.005, 0.005))
            pred_dir   = "▲" if fake_close > ref_close else "▼"
            key = candle_open.isoformat()
            state["pending"][key] = {
                "candle_open": candle_open,
                "pred_close":  round(fake_close, 2),
                "pred_high":   round(fake_close * 1.002, 2),
                "pred_low":    round(fake_close * 0.998, 2),
                "pred_dir":    pred_dir,
                "ref_close":   round(ref_close, 2),
            }
            console.print(f"  [dim]→ candle simulado: {candle_open.strftime('%H:%M UTC')}[/dim]")
        console.print()

    # Initial prediction
    next_open = next_candle_open()
    state["last_candle_open"] = None
    t = threading.Thread(target=_predict_async, args=(next_open,), daemon=True)
    t.start()

    layout = make_layout()

    with Live(layout, console=console, refresh_per_second=0.5, screen=True) as live:
        last_candle_boundary = current_candle_open()

        while True:
            try:
                # Update live price every cycle
                try:
                    price = fetch_current_price()
                    candle = fetch_live_candle()
                    with state_lock:
                        state["current_price"] = price
                        state["live_candle"] = candle
                except Exception:
                    pass

                # Check if candle closed and record result
                _check_and_close_candles()

                # Detect new candle → trigger new prediction
                new_boundary = current_candle_open()
                if new_boundary != last_candle_boundary:
                    last_candle_boundary = new_boundary
                    next_open = next_candle_open()
                    t = threading.Thread(target=_predict_async, args=(next_open,), daemon=True)
                    t.start()

                # Render
                with state_lock:
                    snap = dict(state)

                layout["header"].update(render_header(snap))
                layout["middle"]["prediction"].update(render_prediction(snap))
                layout["middle"]["live_candle"].update(render_live_candle(snap))
                layout["middle"]["scoreboard"].update(render_scoreboard(snap))
                layout["footer"].update(render_history(snap))

                time.sleep(5)

            except KeyboardInterrupt:
                break

    # Summary on exit
    console.print()
    console.rule("[bold]Resumo da Sessão[/bold]")
    history = state.get("history", [])
    if history:
        hits = sum(1 for h in history if h.get("correct"))
        errors = [h["error_pct"] for h in history if "error_pct" in h]
        console.print(f"  Previsões concluídas: [bold]{len(history)}[/bold]")
        console.print(f"  Acertos de direção:   [bold]{hits}/{len(history)} ({hits/len(history)*100:.0f}%)[/bold]")
        if errors:
            console.print(f"  Erro médio de preço:  [bold]{np.mean(errors):.3f}%[/bold]")
    else:
        console.print("  Nenhuma previsão concluída nesta sessão.")
    console.print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kronos Real-Time — previsão candle a candle")
    parser.add_argument("--model", choices=["mini", "small", "base"], default="small",
                        help="Variante do Kronos (mini=4M, small=25M, base=102M)")
    parser.add_argument("--test", action="store_true",
                        help="Injeta previsões passadas simuladas para testar histórico/placar imediatamente")
    args = parser.parse_args()
    main(model_variant=args.model, test_mode=args.test)
