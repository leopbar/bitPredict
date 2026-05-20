"""Drop Phase A tables: predictions, model_runs, alerts, reports, report_jobs, monitoring_metrics, email_log.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-18
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("monitoring_metrics")
    op.drop_table("report_jobs")
    op.drop_table("reports")
    op.drop_table("alerts")
    op.drop_table("model_runs")
    op.drop_table("predictions")
    op.drop_table("email_log")


def downgrade() -> None:
    # Downgrade intentionally left as no-op — Phase A tables are permanently removed.
    pass
