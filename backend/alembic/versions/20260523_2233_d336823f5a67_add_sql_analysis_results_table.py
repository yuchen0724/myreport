"""add sql_analysis_results table

Revision ID: d336823f5a67
Revises: b6f4a1f05db3
Create Date: 2026-05-23 22:33:43.682882

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd336823f5a67'
down_revision = 'b6f4a1f05db3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('sql_analysis_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sql_hash', sa.String(length=64), nullable=False),
    sa.Column('original_sql', sa.Text(), nullable=False),
    sa.Column('complexity_score', sa.Integer(), nullable=False),
    sa.Column('complexity_level', sa.String(length=20), nullable=False),
    sa.Column('select_column_count', sa.Integer(), nullable=True),
    sa.Column('join_count', sa.Integer(), nullable=True),
    sa.Column('subquery_depth', sa.Integer(), nullable=True),
    sa.Column('group_by_count', sa.Integer(), nullable=True),
    sa.Column('order_by_count', sa.Integer(), nullable=True),
    sa.Column('function_call_count', sa.Integer(), nullable=True),
    sa.Column('where_condition_count', sa.Integer(), nullable=True),
    sa.Column('issues', sa.JSON(), nullable=True),
    sa.Column('suggestions', sa.JSON(), nullable=True),
    sa.Column('estimated_time_ms', sa.Integer(), nullable=True),
    sa.Column('has_full_table_scan_risk', sa.String(length=10), nullable=True),
    sa.Column('missing_where_clause', sa.String(length=10), nullable=True),
    sa.Column('analyzer_version', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sql_analysis_complexity', 'sql_analysis_results', ['complexity_level', 'created_at'], unique=False)
    op.create_index('ix_sql_analysis_created', 'sql_analysis_results', ['created_at'], unique=False)
    op.create_index(op.f('ix_sql_analysis_results_id'), 'sql_analysis_results', ['id'], unique=False)
    op.create_index(op.f('ix_sql_analysis_results_sql_hash'), 'sql_analysis_results', ['sql_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_sql_analysis_results_sql_hash'), table_name='sql_analysis_results')
    op.drop_index(op.f('ix_sql_analysis_results_id'), table_name='sql_analysis_results')
    op.drop_index('ix_sql_analysis_created', table_name='sql_analysis_results')
    op.drop_index('ix_sql_analysis_complexity', table_name='sql_analysis_results')
    op.drop_table('sql_analysis_results')
