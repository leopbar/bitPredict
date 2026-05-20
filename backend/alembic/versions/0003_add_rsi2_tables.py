"""Add RSI-2 strategy tables: funding_rates, rsi2_signals, rsi2_trades.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "funding_rates",
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("funding_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("funding_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("mark_price", sa.Numeric(20, 8), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("symbol", "funding_time"),
    )
    op.create_index("ix_funding_rates_time", "funding_rates", ["funding_time"])

    op.create_table(
        "rsi2_signals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("signal_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", sa.String(5), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("stop_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("rsi2_value", sa.Numeric(10, 4), nullable=True),
        sa.Column("meta_proba", sa.Numeric(6, 4), nullable=True),
        sa.Column("params_version", sa.String(50), nullable=False, server_default=sa.text("'A'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rsi2_signals_time", "rsi2_signals", ["signal_time"])

    op.create_table(
        "rsi2_trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", sa.String(5), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("gross_pnl_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("net_pnl_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("exit_reason", sa.String(20), nullable=False),
        sa.Column("bars_held", sa.Integer(), nullable=False),
        sa.Column("params_version", sa.String(50), nullable=False, server_default=sa.text("'A'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rsi2_trades_entry_time", "rsi2_trades", ["entry_time"])


def downgrade() -> None:
    op.drop_index("ix_rsi2_trades_entry_time", table_name="rsi2_trades")
    op.drop_table("rsi2_trades")
    op.drop_index("ix_rsi2_signals_time", table_name="rsi2_signals")
    op.drop_table("rsi2_signals")
    op.drop_index("ix_funding_rates_time", table_name="funding_rates")
    op.drop_table("funding_rates")
