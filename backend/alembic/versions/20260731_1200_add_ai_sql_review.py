"""add machine pre-review fields to sql reviews

Revision ID: 20260731_1200
Revises: 20260731_1100
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_1200"
down_revision: Union[str, None] = "20260731_1100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sql_reviews", sa.Column("ai_risk_level", sa.String(20), nullable=True))
    op.add_column("sql_reviews", sa.Column("ai_review", sa.JSON(), nullable=True))
    op.add_column("sql_reviews", sa.Column("ai_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_sql_reviews_ai_risk_level", "sql_reviews", ["ai_risk_level"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sql_reviews_ai_risk_level", table_name="sql_reviews")
    op.drop_column("sql_reviews", "ai_reviewed_at")
    op.drop_column("sql_reviews", "ai_review")
    op.drop_column("sql_reviews", "ai_risk_level")
