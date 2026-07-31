"""SQL 修正日志模型 — 用户反馈学习"""

from datetime import datetime, timezone
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
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
    review_status = Column(
        String(20), nullable=False, default="verified", index=True,
        comment="审核状态: candidate / verified / rejected",
    )
    source = Column(
        String(30), nullable=False, default="user_feedback",
        comment="案例来源: user_feedback / ai_execution / auto_repair",
    )
    evidence = Column(JSON, nullable=True, comment="执行证据与质量元数据")
    created_by = Column(Integer, nullable=True, comment="提交反馈的用户 ID")
    verified_by = Column(Integer, nullable=True, comment="审核用户 ID")
    verified_at = Column(DateTime, nullable=True, comment="审核时间")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
