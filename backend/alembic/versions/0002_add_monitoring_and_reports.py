"""Add monitoring_metrics, report_jobs, email_log tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monitoring_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("metric_type", sa.String(50), nullable=False),
        sa.Column("feature_name", sa.String(100), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_monitoring_metrics_recorded_at",
        "monitoring_metrics",
        ["recorded_at"],
    )
    op.create_index(
        "ix_monitoring_metrics_type",
        "monitoring_metrics",
        ["metric_type", "feature_name"],
    )

    op.create_table(
        "report_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("celery_task_id", sa.String(64), nullable=True),
        sa.Column("result_file_path", sa.String(500), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "email_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_preview", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("email_log")
    op.drop_table("report_jobs")
    op.drop_index("ix_monitoring_metrics_type", table_name="monitoring_metrics")
    op.drop_index("ix_monitoring_metrics_recorded_at", table_name="monitoring_metrics")
    op.drop_table("monitoring_metrics")
