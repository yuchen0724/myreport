"""add_export_task_and_query_history_tables

Revision ID: 3e8cd2300836
Revises: 9fcf285a71e1
Create Date: 2026-04-22 18:50:22.132004

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e8cd2300836'
down_revision = '9fcf285a71e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 export_tasks 表
    op.create_table(
        'export_tasks',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建 query_history 表
    op.create_table(
        'query_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('data_source_id', sa.Integer(), nullable=True),
        sa.Column('query_type', sa.String(length=20), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_query_history_id'), 'query_history', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_query_history_id'), table_name='query_history')
    op.drop_table('query_history')
    op.drop_table('export_tasks')
