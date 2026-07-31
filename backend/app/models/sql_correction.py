"""SQL 修正日志模型 — 用户反馈学习"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.core.database import Base


class SqlCorrection(Base):
    """SQL 修正记录

    存储用户对 LLM 生成 SQL 的修正反馈，
    用于后续相似问题的 few-shot 示例注入。
    """
    __tablename__ = "sql_corrections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source_id = Column(Integer, nullable=False, index=True)
    question = Column(Text, nullable=False, comment="用户原始问题")
    original_sql = Column(Text, nullable=False, comment="LLM 生成的原始 SQL")
    corrected_sql = Column(Text, nullable=False, comment="用户修正后的 SQL")
    user_feedback = Column(Text, nullable=True, comment="用户的文字反馈")
    table_names = Column(Text, nullable=True, comment="涉及的表名（逗号分隔）")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_by = Column(Integer, nullable=True, comment="提交反馈的用户 ID")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
