"""add drilldown_config to dashboard_widget_configs

Revision ID: 20260527_drilldown
Revises: 20260526_1200
Create Date: 2026-05-27 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260527_drilldown'
down_revision = '20260526_1200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'dashboard_widget_configs',
        sa.Column('drilldown_config', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('dashboard_widget_configs', 'drilldown_config')
