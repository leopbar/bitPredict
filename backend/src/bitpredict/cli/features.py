"""CLI commands for feature engineering: build, describe, correlation."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

features_app = typer.Typer(
    name="features",
    help="Feature engineering: build the feature set, describe statistics, show correlations.",
    no_args_is_help=True,
)

_CATEGORY_STYLE: dict[str, str] = {
    "Technical": "cyan",
    "Returns": "green",
    "Lags": "yellow",
    "Calendar": "magenta",
    "Other": "white",
}


@features_app.command("build")
def build() -> None:
    """Compute all features from raw klines and save to Parquet."""
    from bitpredict.features.pipeline import (
        _FEATURES_PARQUET,
        build_feature_set,
        load_raw_parquet,
        save_features,
    )

    console.print(Panel.fit("Building feature set from raw klines…", border_style="cyan"))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
        transient=True,
    ) as progress:
        t1 = progress.add_task("Loading raw klines…", total=None)
        raw = load_raw_parquet()
        progress.update(t1, description=f"Loaded {len(raw):,} raw candles", completed=1, total=1)

        t2 = progress.add_task("Computing features…", total=None)
        df = build_feature_set(raw)
        progress.update(
            t2,
            description=f"Computed {len(df.columns)} columns, {len(df):,} rows",
            completed=1,
            total=1,
        )

        t3 = progress.add_task("Saving to Parquet…", total=None)
        path = save_features(df)
        progress.update(t3, description=f"Saved to {path}", completed=1, total=1)

    size_mb = _FEATURES_PARQUET.stat().st_size / 1024 / 1024

    console.print(
        Panel.fit(
            f"[bold green]✓ Feature set built[/bold green]\n"
            f"Rows    : [bold]{len(df):,}[/bold]\n"
            f"Columns : [bold]{len(df.columns)}[/bold] "
            f"(context + {len(df.columns) - 7} features + target)\n"
            f"File    : [cyan]{_FEATURES_PARQUET}[/cyan]  ({size_mb:.1f} MB)",
            border_style="green",
        )
    )


@features_app.command("describe")
def describe() -> None:
    """Show statistics for every feature column."""
    from bitpredict.features.pipeline import FEATURE_CATEGORIES, feature_columns, load_features
    from bitpredict.features.target import TARGET_COL

    df = load_features()
    feat_cols = feature_columns(df)
    n_rows = len(df)

    tbl = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        title=f"Feature Set — {n_rows:,} rows, {len(feat_cols)} features",
        title_style="bold",
        title_justify="left",
    )
    tbl.add_column("Feature", style="bold", no_wrap=True)
    tbl.add_column("Category", justify="center")
    tbl.add_column("Non-null %", justify="right")
    tbl.add_column("Min", justify="right")
    tbl.add_column("Max", justify="right")
    tbl.add_column("Mean", justify="right")
    tbl.add_column("Std", justify="right")

    for col in feat_cols:
        series = df[col]
        non_null_pct = 100.0 * series.drop_nulls().len() / n_rows
        cat = FEATURE_CATEGORIES.get(col, "Other")
        style = _CATEGORY_STYLE.get(cat, "white")

        try:
            mn = series.min()
            mx = series.max()
            mean = series.mean()
            std = series.std()
            fmt = _fmt_num
        except Exception:  # noqa: BLE001
            mn = mx = mean = std = None
            fmt = str

        tbl.add_row(
            col,
            f"[{style}]{cat}[/{style}]",
            f"{non_null_pct:.1f}%",
            fmt(mn),
            fmt(mx),
            fmt(mean),
            fmt(std),
        )

    console.print(tbl)


@features_app.command("correlation")
def correlation(
    top: int = typer.Option(15, "--top", "-n", help="Number of top correlated features to show."),
) -> None:
    """Show the features most correlated with the 24h close target."""
    import numpy as np

    from bitpredict.features.pipeline import FEATURE_CATEGORIES, feature_columns, load_features
    from bitpredict.features.target import TARGET_COL

    df = load_features()
    feat_cols = feature_columns(df)

    # Use only rows where target is not null (should be all after pipeline)
    sub = df.select([*feat_cols, TARGET_COL]).drop_nulls()
    X = sub.select(feat_cols).to_numpy().astype(float)
    y = sub[TARGET_COL].to_numpy().astype(float)

    # Pearson correlation between each feature and the target
    corrs: list[tuple[str, float]] = []
    for i, col in enumerate(feat_cols):
        x_col = X[:, i]
        valid = ~(np.isnan(x_col) | np.isnan(y))
        if valid.sum() < 2:
            corrs.append((col, float("nan")))
            continue
        r = float(np.corrcoef(x_col[valid], y[valid])[0, 1])
        corrs.append((col, r))

    corrs.sort(key=lambda t: abs(t[1]) if not _isnan(t[1]) else 0.0, reverse=True)
    top_corrs = corrs[: top]

    tbl = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        title=f"Top {top} Features Correlated with target_close_24h",
        title_style="bold",
        title_justify="left",
    )
    tbl.add_column("Rank", justify="right", style="dim")
    tbl.add_column("Feature", style="bold", no_wrap=True)
    tbl.add_column("Category", justify="center")
    tbl.add_column("Pearson r", justify="right")
    tbl.add_column("Direction", justify="center")

    for rank, (col, r) in enumerate(top_corrs, start=1):
        cat = FEATURE_CATEGORIES.get(col, "Other")
        style = _CATEGORY_STYLE.get(cat, "white")
        if _isnan(r):
            r_str, direction = "—", "—"
        elif r >= 0:
            r_str = f"[green]+{r:.4f}[/green]"
            direction = "[green]↑[/green]"
        else:
            r_str = f"[red]{r:.4f}[/red]"
            direction = "[red]↓[/red]"

        tbl.add_row(str(rank), col, f"[{style}]{cat}[/{style}]", r_str, direction)

    console.print(tbl)


def _fmt_num(v: object) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)  # type: ignore[arg-type]
        if abs(f) >= 1_000_000:
            return f"{f/1_000_000:.2f}M"
        if abs(f) >= 1_000:
            return f"{f:,.1f}"
        return f"{f:.4f}"
    except (TypeError, ValueError):
        return str(v)


def _isnan(v: float) -> bool:
    import math
    try:
        return math.isnan(v)
    except (TypeError, ValueError):
        return True


def register(parent: typer.Typer) -> None:
    parent.add_typer(features_app)
