"""审计日志模型"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class AuditLog(Base):
    """审计日志模型"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False, index=True)  # 操作类型：CREATE, UPDATE, DELETE, QUERY等
    resource_type = Column(String(50), nullable=False, index=True)  # 资源类型：template, query, data_source等
    resource_id = Column(String(100), nullable=True)  # 资源ID
    details = Column(Text, nullable=True)  # 操作详情（JSON格式）
    ip_address = Column(String(50), nullable=True)  # IP地址
    user_agent = Column(String(500), nullable=True)  # 用户代理
    status = Column(String(20), default="success")  # 操作状态：success, failure
    error_message = Column(Text, nullable=True)  # 错误信息
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # 关系
    user = relationship("User", backref="audit_logs")

    # 唯一约束
    __table_args__ = (
        {'comment': '审计日志表'},
    )
