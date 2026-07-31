"""add business briefing subscriptions

Revision ID: 20260731_1300
Revises: 20260731_1200
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_1300"
down_revision: Union[str, None] = "20260731_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "query_subscriptions",
        sa.Column("subscription_type", sa.String(20), nullable=False, server_default="query"),
    )
    op.add_column("query_subscriptions", sa.Column("briefing_config", sa.JSON(), nullable=True))
    op.create_index(
        "ix_query_subscriptions_subscription_type",
        "query_subscriptions",
        ["subscription_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_query_subscriptions_subscription_type", table_name="query_subscriptions")
    op.drop_column("query_subscriptions", "briefing_config")
    op.drop_column("query_subscriptions", "subscription_type")
