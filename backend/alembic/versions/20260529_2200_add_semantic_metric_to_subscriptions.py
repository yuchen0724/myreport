"""add semantic metric to subscriptions

Revision ID: 20260529_2200
Revises: 20260529_2100
Create Date: 2026-05-29 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20260529_2200"
down_revision = "20260529_2100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("query_subscriptions", sa.Column("semantic_metric_key", sa.String(100), nullable=True))
    op.add_column("query_subscriptions", sa.Column("semantic_query", sa.JSON(), nullable=True))
    op.create_index("ix_query_subscriptions_semantic_metric_key", "query_subscriptions", ["semantic_metric_key"])
    op.alter_column("query_subscriptions", "template_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("query_subscriptions", "template_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_query_subscriptions_semantic_metric_key", table_name="query_subscriptions")
    op.drop_column("query_subscriptions", "semantic_query")
    op.drop_column("query_subscriptions", "semantic_metric_key")
