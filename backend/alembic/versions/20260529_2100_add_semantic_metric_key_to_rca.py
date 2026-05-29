"""add semantic metric key to rca configs

Revision ID: 20260529_2100
Revises: 20260529_2000
Create Date: 2026-05-29 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20260529_2100"
down_revision = "20260529_2000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rca_metric_configs", sa.Column("semantic_metric_key", sa.String(100), nullable=True))
    op.create_index("ix_rca_metric_configs_semantic_metric_key", "rca_metric_configs", ["semantic_metric_key"])


def downgrade() -> None:
    op.drop_index("ix_rca_metric_configs_semantic_metric_key", table_name="rca_metric_configs")
    op.drop_column("rca_metric_configs", "semantic_metric_key")
