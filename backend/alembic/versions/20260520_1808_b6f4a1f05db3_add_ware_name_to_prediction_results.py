"""add ware_name to prediction_results

Revision ID: b6f4a1f05db3
Revises: 47ade203cf67
Create Date: 2026-05-20 18:08:30.443743

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b6f4a1f05db3'
down_revision = '47ade203cf67'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('prediction_results', sa.Column('ware_name', sa.String(length=500), nullable=True, comment='商品名称'))


def downgrade() -> None:
    op.drop_column('prediction_results', 'ware_name')
