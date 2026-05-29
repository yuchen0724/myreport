"""add semantic metrics table

Revision ID: 20260529_1600
Revises: 80a0d38d10bc
Create Date: 2026-05-29 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20260529_1600"
down_revision = "80a0d38d10bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data_source_id", sa.Integer(), nullable=False),
        sa.Column("base_sql", sa.Text(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("time_column", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_key", name="uq_semantic_metrics_metric_key"),
    )
    op.create_index("ix_semantic_metrics_metric_key", "semantic_metrics", ["metric_key"])


def downgrade() -> None:
    op.drop_index("ix_semantic_metrics_metric_key", table_name="semantic_metrics")
    op.drop_table("semantic_metrics")
