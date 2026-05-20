#!/usr/bin/env python
"""Historical backfill: 15min OHLCV (2018-01 → now) + funding rates (2019-09 → now).

Run inside the backend container:
    python scripts/rsi2_ingest_backfill.py

Validates completeness with a Rich table after download.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# ── Allow running as a script from the project root ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import polars as pl
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

from bitpredict.data.binance_client import BinanceClient
from bitpredict.data.funding import download_funding_history
from bitpredict.data.gaps import detect_gaps, gap_summary

console = Console()

_DATA_DIR = Path("/app/data/raw")
_SYMBOL = "BTCUSDT"
_INTERVAL = "15m"
_INTERVAL_DELTA = timedelta(minutes=15)
_MAX_PER_PAGE = 1000

_SCHEMA = {
    "open_time": pl.Datetime("us", "UTC"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
    "close_time": pl.Datetime("us", "UTC"),
    "quote_volume": pl.Float64,
    "trades": pl.Int64,
    "taker_buy_base": pl.Float64,
    "taker_buy_quote": pl.Float64,
}


def _raw_to_row(raw: list) -> dict:
    return {
        "open_time": datetime.fromtimestamp(raw[0] / 1000, tz=UTC),
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
        "close_time": datetime.fromtimestamp(raw[6] / 1000, tz=UTC),
        "quote_volume": float(raw[7]),
        "trades": int(raw[8]),
        "taker_buy_base": float(raw[9]),
        "taker_buy_quote": float(raw[10]),
    }


async def _download_15m(start: datetime, end: datetime, progress) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    current_start = start
    page = 0
    task = progress.add_task("Downloading 15m klines...", total=None)

    async with BinanceClient() as client:
        while current_start < end:
            raw = await client.get_klines(
                symbol=_SYMBOL,
                interval=_INTERVAL,
                start_time=current_start,
                end_time=end,
                limit=_MAX_PER_PAGE,
            )
            if not raw:
                break

            rows = [_raw_to_row(r) for r in raw]
            frame = pl.DataFrame(rows, schema=_SCHEMA)
            frames.append(frame)
            page += 1

            total_rows = sum(len(f) for f in frames)
            progress.update(task, description=f"Downloading 15m klines... page {page} ({total_rows:,} rows)")

            last_ts: datetime = rows[-1]["open_time"]
            next_start = last_ts + _INTERVAL_DELTA
            if next_start >= end or len(raw) < _MAX_PER_PAGE:
                break
            current_start = next_start

    progress.remove_task(task)
    if not frames:
        return pl.DataFrame(schema=_SCHEMA)

    result = pl.concat(frames)

    # Sort + deduplicate (Python-level to avoid Polars Windows crash)
    timestamps = result["open_time"].to_list()
    epoch_us = [int(ts.timestamp() * 1_000_000) for ts in timestamps]
    seen: set[int] = set()
    keep: list[int] = []
    for idx in sorted(range(len(epoch_us)), key=lambda i: epoch_us[i]):
        if epoch_us[idx] not in seen:
            seen.add(epoch_us[idx])
            keep.append(idx)

    return result[keep]


async def main() -> None:
    console.rule("[bold cyan]RSI-2 Historical Backfill[/bold cyan]")

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _DATA_DIR / f"{_SYMBOL.lower()}_{_INTERVAL}.parquet"

    start_15m = datetime(2018, 1, 1, tzinfo=UTC)
    end_15m = datetime.now(tz=UTC)

    # Check if partial data already exists
    if out_path.exists():
        existing = pl.read_parquet(out_path)
        times = existing["open_time"].to_list()
        if times:
            last_ts = max(t.replace(tzinfo=UTC) if t.tzinfo is None else t for t in times)
            start_15m = last_ts + _INTERVAL_DELTA
            console.print(f"[cyan]Resuming from {start_15m.isoformat()}[/cyan]")
        else:
            existing = pl.DataFrame(schema=_SCHEMA)
    else:
        existing = pl.DataFrame(schema=_SCHEMA)

    # ── Download 15min OHLCV ──────────────────────────────────────────────────
    console.print("\n[bold]Step 1/2:[/bold] Downloading 15min OHLCV klines...")
    with Progress(SpinnerColumn(), *Progress.get_default_columns(), TimeElapsedColumn()) as progress:
        new_df = await _download_15m(start_15m, end_15m, progress)

    if not new_df.is_empty():
        if not existing.is_empty():
            combined = pl.concat([existing, new_df])
            timestamps_all = combined["open_time"].to_list()
            epoch_us = [int(t.timestamp() * 1_000_000) for t in timestamps_all]
            seen: set[int] = set()
            keep: list[int] = []
            for idx in sorted(range(len(epoch_us)), key=lambda i: epoch_us[i]):
                if epoch_us[idx] not in seen:
                    seen.add(epoch_us[idx])
                    keep.append(idx)
            combined = combined[keep]
        else:
            combined = new_df

        combined.write_parquet(out_path)
        console.print(f"[green]✓ 15min data: {len(combined):,} rows → {out_path}[/green]")
    else:
        combined = existing
        console.print("[yellow]No new 15min data downloaded.[/yellow]")

    # Coverage table
    if not combined.is_empty():
        years = {}
        for ts in combined["open_time"].to_list():
            y = (ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts).year
            years[y] = years.get(y, 0) + 1

        from rich.table import Table
        tbl = Table(title="15min Coverage by Year")
        tbl.add_column("Year", style="cyan")
        tbl.add_column("Rows", justify="right")
        tbl.add_column("Expected", justify="right")
        for y, cnt in sorted(years.items()):
            expected = 365 * 24 * 4  # 4 bars/hour
            tbl.add_row(str(y), f"{cnt:,}", f"~{expected:,}")
        console.print(tbl)

        gaps = detect_gaps(combined, _INTERVAL)
        gs = gap_summary(gaps, _INTERVAL)
        if gs["gap_count"] == 0:
            console.print("[green]✓ No gaps detected.[/green]")
        else:
            console.print(f"[yellow]⚠ {gs['gap_count']} gaps, {gs['missing_candles']} missing candles.[/yellow]")

    # ── Download Funding Rates ────────────────────────────────────────────────
    console.print("\n[bold]Step 2/2:[/bold] Downloading funding rate history...")
    with Progress(SpinnerColumn(), *Progress.get_default_columns(), TimeElapsedColumn()) as progress:
        task = progress.add_task("Funding rates...", total=None)
        try:
            funding_df = await download_funding_history(symbol=_SYMBOL, data_dir=_DATA_DIR)
            progress.update(task, description=f"Done — {len(funding_df):,} funding entries")
            progress.remove_task(task)
            console.print(f"[green]✓ Funding rates: {len(funding_df):,} rows[/green]")
            if not funding_df.is_empty():
                fts = funding_df["funding_time"].to_list()
                console.print(
                    f"   Range: {min(fts)} → {max(fts)}"
                )
        except Exception as e:
            progress.remove_task(task)
            console.print(f"[red]⚠ Funding download failed: {e}[/red]")
            console.print("[dim]Continuing without funding rates (will use 0.0 for costs)[/dim]")

    console.rule("[bold green]Backfill complete[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
