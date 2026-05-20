"""Add kronos_backtests table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS kronos_backtests_id_seq")

    op.create_table(
        "kronos_backtests",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("model_variant", sa.String(20), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("context_length", sa.Integer(), nullable=True),
        # Metrics
        sa.Column("directional_accuracy", sa.Float(), nullable=True),
        sa.Column("mape_close", sa.Float(), nullable=True),
        sa.Column("mape_high", sa.Float(), nullable=True),
        sa.Column("mape_low", sa.Float(), nullable=True),
        sa.Column("mape_volume", sa.Float(), nullable=True),
        sa.Column("band_width_pct_avg", sa.Float(), nullable=True),
        sa.Column("band_calibration_pct", sa.Float(), nullable=True),
        # Meta
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id", "executed_at"),
    )

    op.execute(
        "SELECT create_hypertable('kronos_backtests', 'executed_at', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )
    op.create_index("ix_kronos_backtests_timeframe", "kronos_backtests", ["timeframe"])


def downgrade() -> None:
    op.drop_table("kronos_backtests")
    op.execute("DROP SEQUENCE IF EXISTS kronos_backtests_id_seq")
