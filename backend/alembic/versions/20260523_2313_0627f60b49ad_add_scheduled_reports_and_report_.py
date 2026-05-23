"""add scheduled_reports and report_deliveries tables

Revision ID: 0627f60b49ad
Revises: d336823f5a67
Create Date: 2026-05-23 23:13:20.210800

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0627f60b49ad'
down_revision = 'd336823f5a67'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('scheduled_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('cron_expression', sa.String(length=50), nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=False),
    sa.Column('data_source_id', sa.Integer(), nullable=True),
    sa.Column('parameters', sa.JSON(), nullable=True),
    sa.Column('output_format', sa.String(length=20), nullable=True),
    sa.Column('recipients', sa.JSON(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('last_run_at', sa.DateTime(), nullable=True),
    sa.Column('next_run_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], ),
    sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scheduled_reports_cron_expression'), 'scheduled_reports', ['cron_expression'], unique=False)
    op.create_index(op.f('ix_scheduled_reports_id'), 'scheduled_reports', ['id'], unique=False)
    op.create_index('ix_scheduled_reports_enabled_next', 'scheduled_reports', ['enabled', 'next_run_at'], unique=False)
    
    op.create_table('report_deliveries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scheduled_report_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('file_path', sa.Text(), nullable=True),
    sa.Column('file_name', sa.String(length=200), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('generated_at', sa.DateTime(), nullable=True),
    sa.Column('delivered_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['scheduled_report_id'], ['scheduled_reports.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_deliveries_id'), 'report_deliveries', ['id'], unique=False)
    op.create_index('ix_report_delivery_scheduled', 'report_deliveries', ['scheduled_report_id', 'generated_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_report_delivery_scheduled', table_name='report_deliveries')
    op.drop_index(op.f('ix_report_deliveries_id'), table_name='report_deliveries')
    op.drop_table('report_deliveries')
    op.drop_index('ix_scheduled_reports_enabled_next', table_name='scheduled_reports')
    op.drop_index(op.f('ix_scheduled_reports_id'), table_name='scheduled_reports')
    op.drop_index(op.f('ix_scheduled_reports_cron_expression'), table_name='scheduled_reports')
    op.drop_table('scheduled_reports')
