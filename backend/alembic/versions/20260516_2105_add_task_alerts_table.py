"""add task_alerts table

Revision ID: add_task_alerts_table
Revises: 4a5b6c7d8e9f
Create Date: 2026-05-16 21:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'add_task_alerts_table'
down_revision: Union[str, None] = '4a5b6c7d8e9f'


def upgrade() -> None:
    op.create_table(
        'task_alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='unread'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('alert_message', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_task_alerts_task_id', 'task_alerts', ['task_id'])
    op.create_index('ix_task_alerts_user_id', 'task_alerts', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_task_alerts_user_id', table_name='task_alerts')
    op.drop_index('ix_task_alerts_task_id', table_name='task_alerts')
    op.drop_table('task_alerts')
