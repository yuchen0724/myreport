"""add query_subscriptions and subscription_executions tables

Revision ID: 20260527_1000
Revises: 20260526_1200
Create Date: 2026-05-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260527_1000'
down_revision = '20260526_1200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('query_subscriptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=False),
    sa.Column('cron_expression', sa.String(length=50), nullable=False),
    sa.Column('notify_channel', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('last_run_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_query_subscriptions_id'), 'query_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_query_subscriptions_user_id'), 'query_subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_query_subscriptions_template_id'), 'query_subscriptions', ['template_id'], unique=False)
    op.create_index('ix_query_subscriptions_user_active', 'query_subscriptions', ['user_id', 'is_active'], unique=False)

    op.create_table('subscription_executions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('subscription_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('result_summary', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.ForeignKeyConstraint(['subscription_id'], ['query_subscriptions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_executions_id'), 'subscription_executions', ['id'], unique=False)
    op.create_index(op.f('ix_subscription_executions_subscription_id'), 'subscription_executions', ['subscription_id'], unique=False)
    op.create_index('ix_subscription_exec_sub_executed', 'subscription_executions', ['subscription_id', 'executed_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_subscription_exec_sub_executed', table_name='subscription_executions')
    op.drop_index(op.f('ix_subscription_executions_subscription_id'), table_name='subscription_executions')
    op.drop_index(op.f('ix_subscription_executions_id'), table_name='subscription_executions')
    op.drop_table('subscription_executions')
    op.drop_index('ix_query_subscriptions_user_active', table_name='query_subscriptions')
    op.drop_index(op.f('ix_query_subscriptions_template_id'), table_name='query_subscriptions')
    op.drop_index(op.f('ix_query_subscriptions_user_id'), table_name='query_subscriptions')
    op.drop_index(op.f('ix_query_subscriptions_id'), table_name='query_subscriptions')
    op.drop_table('query_subscriptions')
