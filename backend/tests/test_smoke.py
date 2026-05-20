"""Integration test for the `bitpredict smoke` command.

Requires the Docker services (db, redis, mlflow) to be running and reachable
from the container where pytest is executed (i.e. `docker compose run --rm
backend pytest`).
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from bitpredict.cli import app


@pytest.mark.integration
def test_smoke_command_returns_zero_when_all_services_are_up() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["smoke"])
    assert result.exit_code == 0, (
        f"`bitpredict smoke` returned exit code {result.exit_code}\n\n"
        f"stdout:\n{result.stdout}"
    )
