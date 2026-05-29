"""add semantic metric versions

Revision ID: 20260529_1900
Revises: 20260529_1800
Create Date: 2026-05-29 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20260529_1900"
down_revision = "20260529_1800"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_metric_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["metric_id"], ["semantic_metrics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_id", "version_number", name="uq_semantic_metric_versions_metric_version"),
    )
    op.create_index("ix_semantic_metric_versions_metric_id", "semantic_metric_versions", ["metric_id"])


def downgrade() -> None:
    op.drop_index("ix_semantic_metric_versions_metric_id", table_name="semantic_metric_versions")
    op.drop_table("semantic_metric_versions")
