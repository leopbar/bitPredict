"""bitPredict command-line interface."""

from __future__ import annotations

import typer

from bitpredict.cli import download, stream
from bitpredict.cli import kronos as kronos_cli
from bitpredict.cli.api import register as register_api
from bitpredict.cli.db import register as register_db
from bitpredict.cli.serve import register as register_serve
from bitpredict.cli.smoke import run_smoke_test

app = typer.Typer(
    name="bitpredict",
    help="bitPredict CLI — tools for the Bitcoin price prediction system.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _callback() -> None:
    """bitPredict — Bitcoin price prediction system."""


@app.command(name="smoke", help="Verify connectivity to Postgres and Redis.")
def smoke() -> None:
    run_smoke_test()


download.register(app)
stream.register(app)
register_db(app)
register_serve(app)
register_api(app)
kronos_cli.register(app)
