"""add_data_source_table

Revision ID: 9fcf285a71e1
Revises: 1f798af28135
Create Date: 2026-04-22 18:38:31.887159

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9fcf285a71e1'
down_revision = '1f798af28135'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 data_sources 表
    op.create_table(
        'data_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('database', sa.String(length=100), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_encrypted', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_data_sources_id'), 'data_sources', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_data_sources_id'), table_name='data_sources')
    op.drop_table('data_sources')
