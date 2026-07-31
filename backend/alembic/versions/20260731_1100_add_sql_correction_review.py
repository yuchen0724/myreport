"""add review lifecycle to sql corrections

Revision ID: 20260731_1100
Revises: 20260731_1000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_1100"
down_revision: Union[str, None] = "20260731_1000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sql_corrections",
        sa.Column("review_status", sa.String(20), nullable=False, server_default="verified"),
    )
    op.add_column(
        "sql_corrections",
        sa.Column("source", sa.String(30), nullable=False, server_default="user_feedback"),
    )
    op.add_column("sql_corrections", sa.Column("evidence", sa.JSON(), nullable=True))
    op.add_column("sql_corrections", sa.Column("verified_by", sa.Integer(), nullable=True))
    op.add_column("sql_corrections", sa.Column("verified_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_sql_corrections_review_status", "sql_corrections", ["review_status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_sql_corrections_review_status", table_name="sql_corrections")
    op.drop_column("sql_corrections", "verified_at")
    op.drop_column("sql_corrections", "verified_by")
    op.drop_column("sql_corrections", "evidence")
    op.drop_column("sql_corrections", "source")
    op.drop_column("sql_corrections", "review_status")
