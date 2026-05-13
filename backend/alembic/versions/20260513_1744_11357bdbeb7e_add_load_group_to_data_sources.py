"""add load_group to data_sources

Revision ID: 11357bdbeb7e
Revises: 15e420876c21
Create Date: 2026-05-13 17:44:28.597133

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '11357bdbeb7e'
down_revision = '15e420876c21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('data_sources', sa.Column('load_group', sa.Boolean(), nullable=True,
                  comment='是否加载集团数据（NL2SQL 下拉选择）'))


def downgrade() -> None:
    op.drop_column('data_sources', 'load_group')
