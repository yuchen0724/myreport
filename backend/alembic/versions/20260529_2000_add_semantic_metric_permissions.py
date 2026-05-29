"""add semantic metric permissions

Revision ID: 20260529_2000
Revises: 20260529_1900
Create Date: 2026-05-29 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20260529_2000"
down_revision = "20260529_1900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_metric_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission_level", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("granted_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["metric_id"], ["semantic_metrics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_id", "user_id", name="uq_semantic_metric_permissions_metric_user"),
    )
    op.create_index("ix_semantic_metric_permissions_metric_id", "semantic_metric_permissions", ["metric_id"])
    op.create_index("ix_semantic_metric_permissions_user_id", "semantic_metric_permissions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_semantic_metric_permissions_user_id", table_name="semantic_metric_permissions")
    op.drop_index("ix_semantic_metric_permissions_metric_id", table_name="semantic_metric_permissions")
    op.drop_table("semantic_metric_permissions")
