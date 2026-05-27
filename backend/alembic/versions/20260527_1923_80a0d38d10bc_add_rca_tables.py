"""add rca tables

Revision ID: 80a0d38d10bc
Revises: 7dac5afa6904
Create Date: 2026-05-27 19:23:12.865047

"""
from alembic import op
import sqlalchemy as sa

revision = '80a0d38d10bc'
down_revision = '7dac5afa6904'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('rca_metric_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('label', sa.String(200), nullable=False),
        sa.Column('metric_field', sa.String(200), nullable=False),
        sa.Column('source_table', sa.String(300), nullable=False),
        sa.Column('threshold_type', sa.String(50), nullable=False, server_default='percent_change'),
        sa.Column('threshold_value', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('compare_type', sa.String(20), nullable=False, server_default='mom'),
        sa.Column('drill_dimensions', sa.JSON(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('data_source_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('rca_analysis_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(64), nullable=False),
        sa.Column('metric_config_id', sa.Integer(), nullable=False),
        sa.Column('analysis_date', sa.Date(), nullable=False),
        sa.Column('period_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('anomaly_count', sa.Integer(), nullable=True),
        sa.Column('summary', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['metric_config_id'], ['rca_metric_configs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rca_analysis_tasks_task_id', 'rca_analysis_tasks', ['task_id'])

    op.create_table('rca_anomalies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(64), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('dimension_path', sa.JSON(), nullable=False),
        sa.Column('current_value', sa.Float(), nullable=True),
        sa.Column('baseline_value', sa.Float(), nullable=True),
        sa.Column('change_pct', sa.Float(), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False, server_default='warning'),
        sa.Column('contribution_pct', sa.Float(), nullable=True),
        sa.Column('root_cause_hint', sa.Text(), nullable=True),
        sa.Column('drill_details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rca_anomalies_task_id', 'rca_anomalies', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_rca_anomalies_task_id', table_name='rca_anomalies')
    op.drop_table('rca_anomalies')
    op.drop_index('ix_rca_analysis_tasks_task_id', table_name='rca_analysis_tasks')
    op.drop_table('rca_analysis_tasks')
    op.drop_table('rca_metric_configs')
