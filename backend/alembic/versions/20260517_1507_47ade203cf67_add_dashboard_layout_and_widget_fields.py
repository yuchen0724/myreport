"""add_dashboard_layout_and_widget_fields

Revision ID: 47ade203cf67
Revises: add_task_alerts_table
Create Date: 2026-05-17 15:07:49.420425

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '47ade203cf67'
down_revision = 'add_task_alerts_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 dashboard_layouts 表
    op.create_table('dashboard_layouts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dashboard_layouts_id'), 'dashboard_layouts', ['id'], unique=False)
    op.create_index(op.f('ix_dashboard_layouts_user_id'), 'dashboard_layouts', ['user_id'], unique=False)

    # 扩展 dashboard_widget_configs 表
    op.add_column('dashboard_widget_configs', sa.Column('layout_id', sa.Integer(), nullable=True))
    op.add_column('dashboard_widget_configs', sa.Column('widget_subtype', sa.String(length=50), nullable=True))
    op.add_column('dashboard_widget_configs', sa.Column('grid_x', sa.Integer(), nullable=True))
    op.add_column('dashboard_widget_configs', sa.Column('grid_y', sa.Integer(), nullable=True))
    op.add_column('dashboard_widget_configs', sa.Column('grid_w', sa.Integer(), nullable=True))
    op.add_column('dashboard_widget_configs', sa.Column('grid_h', sa.Integer(), nullable=True))
    op.add_column('dashboard_widget_configs', sa.Column('extra_config', sa.JSON(), nullable=True))
    op.create_index(op.f('ix_dashboard_widget_configs_layout_id'), 'dashboard_widget_configs', ['layout_id'], unique=False)
    op.create_foreign_key('fk_widget_configs_layout', 'dashboard_widget_configs', 'dashboard_layouts', ['layout_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint('fk_widget_configs_layout', 'dashboard_widget_configs', type_='foreignkey')
    op.drop_index(op.f('ix_dashboard_widget_configs_layout_id'), table_name='dashboard_widget_configs')
    op.drop_column('dashboard_widget_configs', 'extra_config')
    op.drop_column('dashboard_widget_configs', 'grid_h')
    op.drop_column('dashboard_widget_configs', 'grid_w')
    op.drop_column('dashboard_widget_configs', 'grid_y')
    op.drop_column('dashboard_widget_configs', 'grid_x')
    op.drop_column('dashboard_widget_configs', 'widget_subtype')
    op.drop_column('dashboard_widget_configs', 'layout_id')
    op.drop_index(op.f('ix_dashboard_layouts_user_id'), table_name='dashboard_layouts')
    op.drop_index(op.f('ix_dashboard_layouts_id'), table_name='dashboard_layouts')
    op.drop_table('dashboard_layouts')
