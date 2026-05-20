"""Add kronos_predictions hypertable.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kronos_predictions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_candle_open_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_candle_close_time", sa.DateTime(timezone=True), nullable=True),
        # Median predictions
        sa.Column("predicted_open",   sa.Float(), nullable=True),
        sa.Column("predicted_high",   sa.Float(), nullable=True),
        sa.Column("predicted_low",    sa.Float(), nullable=True),
        sa.Column("predicted_close",  sa.Float(), nullable=True),
        sa.Column("predicted_volume", sa.Float(), nullable=True),
        # Uncertainty band
        sa.Column("q10_close", sa.Float(), nullable=True),
        sa.Column("q90_close", sa.Float(), nullable=True),
        sa.Column("prob_bullish", sa.Float(), nullable=True),
        # Post-close actuals
        sa.Column("actual_open",   sa.Float(), nullable=True),
        sa.Column("actual_high",   sa.Float(), nullable=True),
        sa.Column("actual_low",    sa.Float(), nullable=True),
        sa.Column("actual_close",  sa.Float(), nullable=True),
        sa.Column("actual_volume", sa.Float(), nullable=True),
        # Accuracy
        sa.Column("direction_correct", sa.Boolean(), nullable=True),
        sa.Column("close_error_pct",   sa.Float(), nullable=True),
        # Config snapshot
        sa.Column("model_variant",  sa.String(20), nullable=True),
        sa.Column("sample_count",   sa.Integer(), nullable=True),
        sa.Column("temperature",    sa.Float(), nullable=True),
        sa.Column("context_length", sa.Integer(), nullable=True),
        # Celery tracking
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("status",  sa.String(20), nullable=False, server_default="pending"),
        # TimescaleDB requires the partition column (predicted_at) in the primary key
        sa.PrimaryKeyConstraint("id", "predicted_at"),
    )
    # Sequence for id (TimescaleDB does not support SERIAL with composite PKs)
    op.execute("CREATE SEQUENCE kronos_predictions_id_seq;")
    op.execute(
        "ALTER TABLE kronos_predictions "
        "ALTER COLUMN id SET DEFAULT nextval('kronos_predictions_id_seq');"
    )
    op.create_index(
        "ix_kronos_predictions_timeframe_predicted_at",
        "kronos_predictions", ["timeframe", "predicted_at"],
    )

    # Convert to TimescaleDB hypertable partitioned by predicted_at
    op.execute(
        "SELECT create_hypertable('kronos_predictions', 'predicted_at', "
        "if_not_exists => TRUE);"
    )


def downgrade() -> None:
    op.drop_table("kronos_predictions")
