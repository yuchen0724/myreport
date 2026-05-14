"""add task_id and created_by to prediction_models

Revision ID: b9f3a2c1e4d5
Revises: 45ef9febd464
Create Date: 2026-05-14 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9f3a2c1e4d5'
down_revision = '45ef9febd464'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('prediction_models', sa.Column('task_id', sa.String(64), nullable=True, comment='Celery 任务 ID'))
    op.add_column('prediction_models', sa.Column('created_by', sa.Integer(), nullable=True, comment='发起训练的用户 ID'))
    op.create_index(op.f('ix_prediction_models_task_id'), 'prediction_models', ['task_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_prediction_models_task_id'), table_name='prediction_models')
    op.drop_column('prediction_models', 'created_by')
    op.drop_column('prediction_models', 'task_id')
