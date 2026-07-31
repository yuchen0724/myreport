"""add sql corrections table

Revision ID: 20260731_1000
Revises: 20260529_2200
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_1000"
down_revision: Union[str, None] = "20260529_2200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sql_corrections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("data_source_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False, comment="用户原始问题"),
        sa.Column("original_sql", sa.Text(), nullable=False, comment="LLM 生成的原始 SQL"),
        sa.Column("corrected_sql", sa.Text(), nullable=False, comment="用户修正后的 SQL"),
        sa.Column("user_feedback", sa.Text(), nullable=True, comment="用户的文字反馈"),
        sa.Column("table_names", sa.Text(), nullable=True, comment="涉及的表名（逗号分隔）"),
        sa.Column("is_active", sa.Boolean(), nullable=True, comment="是否启用"),
        sa.Column("created_by", sa.Integer(), nullable=True, comment="提交反馈的用户 ID"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sql_corrections_data_source_id"),
        "sql_corrections",
        ["data_source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sql_corrections_data_source_id"), table_name="sql_corrections")
    op.drop_table("sql_corrections")
