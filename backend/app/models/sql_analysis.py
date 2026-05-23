"""SQL Analysis data models

用于 SQL 复杂度分析、慢查询检测的结果存储
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index
from sqlalchemy.sql import func

from app.core.database import Base


class SQLAnalysisResult(Base):
    """SQL 分析结果

    存储 SQL 复杂度分析结果，含缓存 key (sql_hash)
    """
    __tablename__ = "sql_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    sql_hash = Column(String(64), unique=True, index=True, nullable=False)
    original_sql = Column(Text, nullable=False)

    # 复杂度指标
    complexity_score = Column(Integer, nullable=False)  # 1-100
    complexity_level = Column(String(20), nullable=False)  # low/medium/high/critical

    # 详细指标
    select_column_count = Column(Integer, default=0)
    join_count = Column(Integer, default=0)
    subquery_depth = Column(Integer, default=0)
    group_by_count = Column(Integer, default=0)
    order_by_count = Column(Integer, default=0)
    function_call_count = Column(Integer, default=0)
    where_condition_count = Column(Integer, default=0)

    # 检测到的问题
    issues = Column(JSON, default=list)  # [{type, severity, position, description}]

    # 优化建议
    suggestions = Column(JSON, default=list)  # [{action, field, description}]

    # 预估信息
    estimated_time_ms = Column(Integer, nullable=True)
    has_full_table_scan_risk = Column(String(10), default="unknown")  # yes/no/unknown
    missing_where_clause = Column(String(10), default="unknown")

    # 元数据
    analyzer_version = Column(String(20), default="v1")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_sql_analysis_complexity", "complexity_level", "created_at"),
        Index("ix_sql_analysis_created", "created_at"),
    )

    def __repr__(self):
        return f"<SQLAnalysisResult(id={self.id}, level={self.complexity_level}, score={self.complexity_score})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sql_hash": self.sql_hash,
            "complexity_score": self.complexity_score,
            "complexity_level": self.complexity_level,
            "metrics": {
                "select_column_count": self.select_column_count,
                "join_count": self.join_count,
                "subquery_depth": self.subquery_depth,
                "group_by_count": self.group_by_count,
                "order_by_count": self.order_by_count,
                "function_call_count": self.function_call_count,
                "where_condition_count": self.where_condition_count,
            },
            "issues": self.issues or [],
            "suggestions": self.suggestions or [],
            "estimated_time_ms": self.estimated_time_ms,
            "has_full_table_scan_risk": self.has_full_table_scan_risk,
            "missing_where_clause": self.missing_where_clause,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }