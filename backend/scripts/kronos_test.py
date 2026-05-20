"""
Kronos Foundation Model — teste isolado em BTC 15min.

Uso:
    docker compose exec backend python scripts/kronos_test.py
    docker compose exec backend python scripts/kronos_test.py --pred-len 32 --context 300
    docker compose exec backend python scripts/kronos_test.py --offset 200

O script:
1. Carrega os dados de BTC 15min do disco
2. Carrega o modelo Kronos (download automático ~200MB na 1a vez)
3. Usa N candles passados como contexto
4. Prevê os próximos P candles
5. Compara previsão vs realidade com tabela Rich
"""
from __future__ import annotations

import sys
import argparse
from datetime import timedelta
from pathlib import Path

# Kronos fica em /app/data/kronos (volume persistido — sobrevive a restarts)
KRONOS_PATH = Path("/app/data/kronos")
if not KRONOS_PATH.exists():
    print("ERRO: /app/data/kronos não encontrado.")
    print("Rode primeiro: docker compose exec backend python scripts/kronos_setup.py")
    sys.exit(1)
sys.path.insert(0, str(KRONOS_PATH))

import numpy as np
import pandas as pd
import polars as pl
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule

console = Console()

DATA_PATH = Path("/app/data/raw/btcusdt_15m.parquet")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sparkline(values: list[float], width: int = 20) -> str:
    """ASCII sparkline using block characters."""
    blocks = " ▁▂▃▄▅▆▇█"
    if not values or max(values) == min(values):
        return "─" * width
    lo, hi = min(values), max(values)
    indices = [int((v - lo) / (hi - lo) * (len(blocks) - 1)) for v in values]
    line = "".join(blocks[i] for i in indices)
    # Truncate or pad to width
    if len(line) > width:
        step = len(line) / width
        line = "".join(line[int(i * step)] for i in range(width))
    return line


def _pct_error(pred: float, real: float) -> float:
    if real == 0:
        return 0.0
    return abs(pred - real) / abs(real) * 100


def _direction_icon(pred_close: float, ctx_close: float, real_close: float) -> tuple[str, str]:
    """Returns (predicted_arrow, correct_or_not)."""
    pred_dir = "▲" if pred_close > ctx_close else "▼"
    real_dir = "▲" if real_close > ctx_close else "▼"
    match = "✓" if pred_dir == real_dir else "✗"
    return pred_dir, match


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_btc_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        console.print(f"[red]ERRO:[/red] {DATA_PATH} não encontrado. Execute a ingestão primeiro.")
        sys.exit(1)

    with console.status("[cyan]Carregando dados BTC 15min..."):
        df_pl = pl.read_parquet(DATA_PATH)
        df = df_pl.select(["open_time", "open", "high", "low", "close", "volume"]).to_pandas()
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        df = df.sort_values("open_time").reset_index(drop=True)

    console.print(f"[green]✓[/green] Dados carregados: [bold]{len(df):,}[/bold] candles  "
                  f"[dim]({df['open_time'].iloc[0].date()} → {df['open_time'].iloc[-1].date()})[/dim]")
    return df


# ---------------------------------------------------------------------------
# Load Kronos
# ---------------------------------------------------------------------------

def load_kronos(model_variant: str = "small"):
    """Load tokenizer + model. Downloads from HuggingFace if not cached."""
    from model import Kronos, KronosTokenizer, KronosPredictor

    tokenizer_id = "NeoQuasar/Kronos-Tokenizer-base"
    model_id = f"NeoQuasar/Kronos-{model_variant}"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        t1 = progress.add_task(f"[cyan]Baixando tokenizer ({tokenizer_id})...", total=None)
        tokenizer = KronosTokenizer.from_pretrained(tokenizer_id)
        progress.update(t1, description="[green]✓ Tokenizer carregado")

        t2 = progress.add_task(f"[cyan]Baixando modelo ({model_id})...", total=None)
        model = Kronos.from_pretrained(model_id)
        progress.update(t2, description=f"[green]✓ Modelo {model_id} carregado")

    predictor = KronosPredictor(model, tokenizer, max_context=512)
    console.print(f"[green]✓[/green] Kronos-[bold]{model_variant}[/bold] pronto para uso\n")
    return predictor


# ---------------------------------------------------------------------------
# Run prediction
# ---------------------------------------------------------------------------

def run_test(
    df: pd.DataFrame,
    predictor,
    context_len: int = 300,
    pred_len: int = 16,
    offset: int = 0,
    sample_count: int = 3,
):
    """
    offset=0 → testa no final do histórico (sem dado real para comparar)
    offset>0 → testa N candles atrás, permitindo comparação com realidade
    """
    total = len(df)
    test_end = total - offset          # último candle do contexto
    test_start = test_end - context_len
    future_end = test_end + pred_len

    if test_start < 0:
        console.print(f"[red]ERRO:[/red] Dados insuficientes para context_len={context_len}")
        sys.exit(1)

    ctx_df = df.iloc[test_start:test_end].copy()
    has_real = (future_end <= total) and (offset > 0)
    real_df = df.iloc[test_end:min(future_end, total)].copy() if has_real else None

    # Timestamps para os candles futuros (espaçamento de 15min)
    last_ts = ctx_df["open_time"].iloc[-1]
    future_timestamps = pd.Series([
        last_ts + timedelta(minutes=15 * (i + 1)) for i in range(pred_len)
    ])

    console.print(Rule("[bold]Configuração do Teste[/bold]"))
    config_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    config_table.add_column("", style="dim")
    config_table.add_column("", style="cyan bold")
    config_table.add_row("Contexto (entrada)", f"{context_len} candles")
    config_table.add_row("Previsão (saída)", f"{pred_len} candles = {pred_len * 15}min = {pred_len * 15 // 60}h")
    config_table.add_row("Último candle do contexto", str(last_ts.strftime("%Y-%m-%d %H:%M UTC")))
    config_table.add_row("Período previsto até", str(future_timestamps.iloc[-1].strftime("%Y-%m-%d %H:%M UTC")))
    config_table.add_row("Samples internos", str(sample_count))
    config_table.add_row("Dados reais disponíveis", "[green]SIM[/green]" if has_real else "[yellow]NÃO (previsão do futuro)[/yellow]")
    console.print(config_table)

    # Prepara input — Kronos recebe open/high/low/close (volume é opcional, amount não temos)
    x_df = ctx_df[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
    x_timestamp = ctx_df["open_time"].reset_index(drop=True)

    console.print(f"\n[cyan]Rodando Kronos...[/cyan] (pode levar 10-60s dependendo do hardware)\n")

    with console.status("[yellow]Gerando previsão...[/yellow]"):
        pred_df = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=future_timestamps,
            pred_len=pred_len,
            T=1.0,
            top_p=0.9,
            sample_count=sample_count,
            verbose=False,
        )

    console.print("[green]✓[/green] Previsão concluída!\n")
    return pred_df, real_df, ctx_df, future_timestamps


# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------

def display_results(
    pred_df: pd.DataFrame,
    real_df: pd.DataFrame | None,
    ctx_df: pd.DataFrame,
    future_timestamps: pd.Series,
    pred_len: int,
):
    last_close = ctx_df["close"].iloc[-1]
    has_real = real_df is not None and len(real_df) > 0

    console.print(Rule("[bold]Resultado da Previsão[/bold]"))

    # ── Tabela principal ──────────────────────────────────────────────────
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        expand=True,
    )

    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Horário (UTC)", width=17)
    table.add_column("Prev. Fechamento", justify="right", width=16)
    table.add_column("Prev. Máxima", justify="right", width=13)
    table.add_column("Prev. Mínima", justify="right", width=13)
    table.add_column("Dir.", justify="center", width=5)

    if has_real:
        table.add_column("Real Fechamento", justify="right", width=16)
        table.add_column("Erro %", justify="right", width=8)
        table.add_column("Acerto?", justify="center", width=8)

    direction_hits = 0
    close_errors = []
    pred_closes = []
    real_closes = []

    n_real = len(real_df) if has_real else 0

    for i in range(min(pred_len, len(pred_df))):
        ts = future_timestamps.iloc[i]
        p_close = float(pred_df["close"].iloc[i])
        p_high = float(pred_df["high"].iloc[i])
        p_low = float(pred_df["low"].iloc[i])

        pred_closes.append(p_close)

        ref_close = pred_closes[i - 1] if i > 0 else last_close
        pred_dir = "▲" if p_close > ref_close else "▼"
        dir_color = "green" if pred_dir == "▲" else "red"

        if has_real and i < n_real:
            r_close = float(real_df["close"].iloc[i])
            real_closes.append(r_close)
            real_ref = real_closes[i - 1] if i > 0 else last_close
            real_dir = "▲" if r_close > real_ref else "▼"
            correct = pred_dir == real_dir
            if correct:
                direction_hits += 1
            err = _pct_error(p_close, r_close)
            close_errors.append(err)

            table.add_row(
                str(i + 1),
                ts.strftime("%d/%m %H:%M"),
                f"[bold]{p_close:,.2f}[/bold]",
                f"{p_high:,.2f}",
                f"{p_low:,.2f}",
                f"[{dir_color}]{pred_dir}[/{dir_color}]",
                f"[bold]{r_close:,.2f}[/bold]",
                f"[{'red' if err > 1 else 'yellow' if err > 0.3 else 'green'}]{err:.2f}%[/]",
                f"[green]✓[/green]" if correct else f"[red]✗[/red]",
            )
        else:
            table.add_row(
                str(i + 1),
                ts.strftime("%d/%m %H:%M"),
                f"[bold]{p_close:,.2f}[/bold]",
                f"{p_high:,.2f}",
                f"{p_low:,.2f}",
                f"[{dir_color}]{pred_dir}[/{dir_color}]",
            )

    console.print(table)

    # ── Sparklines ────────────────────────────────────────────────────────
    console.print()
    spark_pred = _sparkline(pred_closes, width=pred_len * 2)
    pred_chg = pred_closes[-1] - last_close
    pred_chg_pct = pred_chg / last_close * 100
    chg_color = "green" if pred_chg >= 0 else "red"

    console.print(f"  Trajetória prevista:  [cyan]{spark_pred}[/cyan]  "
                  f"[{chg_color}]{pred_chg:+.2f} ({pred_chg_pct:+.2f}%)[/{chg_color}]")

    if has_real and real_closes:
        spark_real = _sparkline(real_closes, width=len(real_closes) * 2)
        real_chg = real_closes[-1] - last_close
        real_chg_pct = real_chg / last_close * 100
        real_color = "green" if real_chg >= 0 else "red"
        console.print(f"  Trajetória real:      [white]{spark_real}[/white]  "
                      f"[{real_color}]{real_chg:+.2f} ({real_chg_pct:+.2f}%)[/{real_color}]")

    # ── Métricas resumo ───────────────────────────────────────────────────
    if has_real and close_errors:
        console.print()
        console.print(Rule("[bold]Métricas de Acurácia[/bold]"))

        summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 3))
        summary.add_column("", style="dim")
        summary.add_column("", style="bold")
        summary.add_column("", style="dim italic")

        mae = float(np.mean(close_errors))
        n_compared = len(close_errors)
        dir_acc = direction_hits / n_compared * 100 if n_compared else 0

        dir_color = "green" if dir_acc >= 60 else "yellow" if dir_acc >= 50 else "red"
        mae_color = "green" if mae < 0.3 else "yellow" if mae < 1.0 else "red"

        summary.add_row(
            "Acerto de direção",
            f"[{dir_color}]{direction_hits}/{n_compared} ({dir_acc:.0f}%)[/{dir_color}]",
            "→ quantas vezes subiu/caiu no sentido certo",
        )
        summary.add_row(
            "Erro médio no preço (MAPE)",
            f"[{mae_color}]{mae:.3f}%[/{mae_color}]",
            "→ quanto % o preço previsto errou em média",
        )
        summary.add_row(
            "Erro máximo",
            f"{max(close_errors):.3f}%",
            "→ pior candle individual",
        )
        summary.add_row(
            "Erro mínimo",
            f"{min(close_errors):.3f}%",
            "→ melhor candle individual",
        )
        console.print(summary)

    # ── Legenda ───────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]Como ler esta tabela:[/bold]\n\n"
        "[cyan]#[/cyan]          Número do candle futuro (1 = próximos 15min, 2 = próximos 30min...)\n"
        "[cyan]Horário[/cyan]    Quando esse candle começa (UTC)\n"
        "[cyan]Prev. Fechamento[/cyan]  Preço que o Kronos prevê para o fechamento\n"
        "[cyan]Prev. Máx/Mín[/cyan]    Teto e piso previstos para o candle\n"
        "[cyan]Dir.[/cyan]       [green]▲[/green] = Kronos prevê alta  [red]▼[/red] = Kronos prevê queda\n"
        + (
            "[cyan]Real Fechamento[/cyan]  O que realmente aconteceu (comparação histórica)\n"
            "[cyan]Erro %[/cyan]     [green]<0.3%[/green] ótimo  [yellow]0.3-1%[/yellow] aceitável  [red]>1%[/red] ruim\n"
            "[cyan]Acerto?[/cyan]    [green]✓[/green] acertou a direção  [red]✗[/red] errou a direção\n"
            if has_real else
            "[dim]Offset=0: previsão do futuro real — não há dados para comparar ainda.[/dim]\n"
            "[dim]Use --offset 100 para testar num ponto histórico e ver a comparação.[/dim]\n"
        ),
        title="[dim]Legenda[/dim]",
        border_style="dim",
    ))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Teste do modelo Kronos em BTC 15min")
    parser.add_argument("--context", type=int, default=300,
                        help="Quantos candles usar como contexto (máx 512, padrão 300)")
    parser.add_argument("--pred-len", type=int, default=16,
                        help="Quantos candles prever (padrão 16 = 4 horas)")
    parser.add_argument("--offset", type=int, default=50,
                        help="Quantos candles atrás testar (0=futuro real, >0=backtest histórico, padrão 50)")
    parser.add_argument("--samples", type=int, default=3,
                        help="Quantas amostras internas gerar e fazer média (1-10, padrão 3)")
    parser.add_argument("--model", choices=["mini", "small", "base"], default="small",
                        help="Variante do Kronos (mini=4M, small=25M, base=102M, padrão small)")
    args = parser.parse_args()

    console.print(Panel(
        "[bold cyan]Kronos Foundation Model[/bold cyan] — Teste em BTC/USDT 15min\n"
        "[dim]Modelo pré-treinado em 12 bilhões de K-lines de 45 exchanges globais[/dim]",
        border_style="cyan",
    ))
    console.print()

    df = load_btc_data()
    predictor = load_kronos(model_variant=args.model)

    pred_df, real_df, ctx_df, future_ts = run_test(
        df=df,
        predictor=predictor,
        context_len=min(args.context, 512),
        pred_len=args.pred_len,
        offset=args.offset,
        sample_count=args.samples,
    )

    display_results(
        pred_df=pred_df,
        real_df=real_df,
        ctx_df=ctx_df,
        future_timestamps=future_ts,
        pred_len=args.pred_len,
    )


if __name__ == "__main__":
    main()
