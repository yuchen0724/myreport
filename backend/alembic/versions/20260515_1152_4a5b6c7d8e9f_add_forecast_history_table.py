"""add forecast_history table

Revision ID: 4a5b6c7d8e9f
Revises: b9f3a2c1e4d5
Create Date: 2026-05-15 11:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a5b6c7d8e9f'
down_revision: Union[str, None] = 'b9f3a2c1e4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'forecast_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(64), nullable=False, index=True, comment='Celery 任务 ID'),
        sa.Column('model_id', sa.Integer(), nullable=True, comment='实际使用的模型ID'),
        sa.Column('data_source_id', sa.Integer(), nullable=False, comment='数据源ID'),
        sa.Column('forecast_days', sa.Integer(), nullable=False, comment='预测天数'),
        sa.Column('result_count', sa.Integer(), nullable=True, comment='预测结果条数'),
        sa.Column('model_name', sa.String(128), nullable=True, comment='模型描述'),
        sa.Column('status', sa.String(16), nullable=False, server_default='running', comment='状态: success/failed'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='失败原因'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='提交时间'),
        sa.Column('created_by', sa.Integer(), nullable=True, comment='发起预测的用户 ID'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('forecast_history')
