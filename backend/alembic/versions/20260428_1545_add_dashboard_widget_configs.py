"""add_dashboard_widget_configs_table

Revision ID: 58e2a1b3c4d5
Revises: add_sql_to_export_tasks
Create Date: 2026-04-28 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '58e2a1b3c4d5'
down_revision = 'add_sql_to_export_tasks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'dashboard_widget_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('widget_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('visible', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'widget_type', name='uq_user_widget_type'),
    )
    op.create_index(
        'ix_dashboard_widget_configs_user_id',
        'dashboard_widget_configs',
        ['user_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_dashboard_widget_configs_user_id')
    op.drop_table('dashboard_widget_configs')
