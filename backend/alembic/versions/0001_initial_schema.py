"""Initial schema: all tables + klines TimescaleDB hypertable.

Revision ID: 0001
Revises:
Create Date: 2026-05-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # klines — will become a TimescaleDB hypertable
    # PK must include open_time (the time dimension column).
    # -------------------------------------------------------------------------
    op.create_table(
        "klines",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(30, 8), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quote_volume", sa.Numeric(30, 8), nullable=False),
        sa.Column("trades", sa.Integer(), nullable=False),
        sa.Column("taker_buy_base", sa.Numeric(30, 8), nullable=False),
        sa.Column("taker_buy_quote", sa.Numeric(30, 8), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "interval", "open_time"),
    )

    # Convert klines to a TimescaleDB hypertable with 30-day chunks.
    op.execute(
        "SELECT create_hypertable('klines', 'open_time', "
        "chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE)"
    )

    # Additional index on (symbol, interval) for fast per-pair queries.
    op.create_index("ix_klines_symbol_interval", "klines", ["symbol", "interval"])

    # -------------------------------------------------------------------------
    # predictions
    # -------------------------------------------------------------------------
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("target_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("q10", sa.Numeric(20, 8), nullable=False),
        sa.Column("q50", sa.Numeric(20, 8), nullable=False),
        sa.Column("q90", sa.Numeric(20, 8), nullable=False),
        sa.Column("recommendation", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("actual_price", sa.Numeric(20, 8), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_target_time", "predictions", ["target_time"])

    # -------------------------------------------------------------------------
    # model_runs
    # -------------------------------------------------------------------------
    op.create_table(
        "model_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mlflow_run_id", sa.String(64), nullable=False),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mlflow_run_id", name="uq_model_runs_mlflow_run_id"),
    )

    # -------------------------------------------------------------------------
    # alerts
    # -------------------------------------------------------------------------
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("condition_json", sa.JSON(), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # -------------------------------------------------------------------------
    # parameters  (dashboard key/value config store)
    # -------------------------------------------------------------------------
    op.create_table(
        "parameters",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_by", sa.String(100), nullable=False, server_default="'system'"
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # -------------------------------------------------------------------------
    # reports
    # -------------------------------------------------------------------------
    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("sent_to", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("parameters")
    op.drop_table("alerts")
    op.drop_table("model_runs")
    op.drop_index("ix_predictions_target_time", table_name="predictions")
    op.drop_table("predictions")
    op.drop_index("ix_klines_symbol_interval", table_name="klines")
    op.drop_table("klines")
