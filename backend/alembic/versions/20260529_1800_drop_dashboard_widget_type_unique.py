"""drop dashboard widget type unique constraint

Revision ID: 20260529_1800
Revises: 20260529_1700
Create Date: 2026-05-29 18:00:00.000000

"""
from alembic import op

revision = "20260529_1800"
down_revision = "20260529_1700"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_user_widget_type", "dashboard_widget_configs", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_user_widget_type",
        "dashboard_widget_configs",
        ["user_id", "widget_type"],
    )
