"""
Setup do Kronos — rode UMA VEZ antes do primeiro teste.

Uso:
    docker compose exec -u root backend python scripts/kronos_setup.py
"""
from __future__ import annotations

import subprocess
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
KRONOS_PATH = Path("/app/data/kronos")


def download_kronos() -> None:
    if KRONOS_PATH.exists():
        console.print(f"[yellow]Kronos já existe em {KRONOS_PATH} — pulando download.[/yellow]")
        return

    url = "https://github.com/shiyu-coder/Kronos/archive/refs/heads/master.zip"
    tmp_zip = Path("/tmp/kronos.zip")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
        task = p.add_task("Baixando Kronos do GitHub...", total=None)
        urllib.request.urlretrieve(url, tmp_zip)
        p.update(task, description="Extraindo arquivos...")
        zipfile.ZipFile(tmp_zip).extractall("/tmp")
        shutil.move("/tmp/Kronos-master", str(KRONOS_PATH))
        p.update(task, description="[green]✓ Kronos extraído para /app/data/kronos")

    console.print(f"[green]✓[/green] Kronos instalado em: {KRONOS_PATH}")


def install_deps() -> None:
    pkgs = ["einops==0.8.1", "huggingface_hub==0.33.1", "safetensors==0.6.2"]
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
        task = p.add_task(f"Instalando dependências: {', '.join(pkgs)}...", total=None)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + pkgs,
        )
        p.update(task, description=f"[green]✓ Dependências instaladas")
    console.print(f"[green]✓[/green] Pacotes: {', '.join(pkgs)}")


def verify() -> None:
    sys.path.insert(0, str(KRONOS_PATH))
    try:
        from model import Kronos, KronosTokenizer, KronosPredictor  # noqa: F401
        console.print("[green]✓[/green] Imports do Kronos funcionando")
    except ImportError as e:
        console.print(f"[red]ERRO nos imports:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    console.rule("[bold cyan]Kronos Setup[/bold cyan]")
    download_kronos()
    install_deps()
    verify()
    console.print()
    console.rule("[bold green]Setup concluído![/bold green]")
    console.print("\nAgora você pode rodar:")
    console.print("  [bold cyan]docker compose exec backend python scripts/kronos_test.py[/bold cyan]\n")
