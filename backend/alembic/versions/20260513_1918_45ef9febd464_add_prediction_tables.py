"""add prediction tables

Revision ID: 45ef9febd464
Revises: 11357bdbeb7e
Create Date: 2026-05-13 19:18:02.168954

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '45ef9febd464'
down_revision = '11357bdbeb7e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('prediction_models',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('data_source_id', sa.Integer(), nullable=False, comment='关联数据源'),
    sa.Column('model_type', sa.String(length=32), nullable=True, comment='模型类型'),
    sa.Column('feature_count', sa.Integer(), nullable=True, comment='特征数'),
    sa.Column('train_start_date', sa.Date(), nullable=True, comment='训练数据起始日期'),
    sa.Column('train_end_date', sa.Date(), nullable=True, comment='训练数据截止日期'),
    sa.Column('train_row_count', sa.Integer(), nullable=True, comment='训练样本数'),
    sa.Column('model_metrics', sa.JSON(), nullable=True, comment='模型指标(JSON)'),
    sa.Column('model_path', sa.String(length=255), nullable=True, comment='模型文件路径'),
    sa.Column('status', sa.String(length=16), nullable=True, comment='状态: training/ready/failed'),
    sa.Column('error_message', sa.Text(), nullable=True, comment='训练失败原因'),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('trained_at', sa.DateTime(), nullable=True, comment='训练完成时间'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('prediction_results',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('model_id', sa.Integer(), nullable=False, comment='模型ID'),
    sa.Column('data_source_id', sa.Integer(), nullable=False, comment='数据源ID'),
    sa.Column('store_code', sa.String(length=32), nullable=False, comment='门店编码'),
    sa.Column('matnr', sa.String(length=32), nullable=False, comment='商品编码'),
    sa.Column('forecast_date', sa.Date(), nullable=False, comment='预测日期'),
    sa.Column('predicted_value', sa.Float(), nullable=False, comment='预测值（元）'),
    sa.Column('lower_bound', sa.Float(), nullable=True, comment='预测下限'),
    sa.Column('upper_bound', sa.Float(), nullable=True, comment='预测上限'),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prediction_results_model_id'), 'prediction_results', ['model_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_prediction_results_model_id'), table_name='prediction_results')
    op.drop_table('prediction_results')
    op.drop_table('prediction_models')
