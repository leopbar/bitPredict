"""Add kronos_backtest_trades table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS kronos_backtest_trades_id_seq")

    op.create_table(
        "kronos_backtest_trades",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("target_open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("backtest_id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        # Prediction output
        sa.Column("predicted_close", sa.Float(), nullable=True),
        sa.Column("predicted_high", sa.Float(), nullable=True),
        sa.Column("predicted_low", sa.Float(), nullable=True),
        sa.Column("q10_close", sa.Float(), nullable=True),
        sa.Column("q90_close", sa.Float(), nullable=True),
        # Actual candle values
        sa.Column("actual_open", sa.Float(), nullable=True),
        sa.Column("actual_close", sa.Float(), nullable=True),
        sa.Column("actual_high", sa.Float(), nullable=True),
        sa.Column("actual_low", sa.Float(), nullable=True),
        # Accuracy
        sa.Column("prob_bullish", sa.Float(), nullable=True),
        sa.Column("direction_correct", sa.Boolean(), nullable=True),
        sa.Column("close_error_pct", sa.Float(), nullable=True),
        sa.Column("band_covers_actual", sa.Boolean(), nullable=True),
        # Trade simulation result
        sa.Column("trade_return_pct", sa.Float(), nullable=True),
        sa.Column("trade_pnl_usd", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id", "target_open_time"),
    )

    op.execute(
        "SELECT create_hypertable('kronos_backtest_trades', 'target_open_time', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    )
    op.create_index(
        "ix_kronos_backtest_trades_backtest_id",
        "kronos_backtest_trades",
        ["backtest_id"],
    )
    op.create_index(
        "ix_kronos_backtest_trades_timeframe",
        "kronos_backtest_trades",
        ["timeframe"],
    )


def downgrade() -> None:
    op.drop_table("kronos_backtest_trades")
    op.execute("DROP SEQUENCE IF EXISTS kronos_backtest_trades_id_seq")
