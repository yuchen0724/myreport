"""add metric expression to semantic metrics

Revision ID: 20260529_1700
Revises: 20260529_1600
Create Date: 2026-05-29 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20260529_1700"
down_revision = "20260529_1600"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "semantic_metrics",
        sa.Column("metric_expression", sa.String(300), nullable=False, server_default="COUNT(*)"),
    )


def downgrade() -> None:
    op.drop_column("semantic_metrics", "metric_expression")
