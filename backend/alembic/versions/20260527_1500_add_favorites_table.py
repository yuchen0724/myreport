"""add favorites table

Revision ID: a1b2c3d4e5f6
Revises: 20260527_1300_add_drilldown_config
Create Date: 2026-05-27 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = '20260527_drilldown'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'favorites',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('templates.id'), nullable=False, index=True),
        sa.Column('category', sa.String(50), nullable=False, server_default='默认'),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table('favorites')
