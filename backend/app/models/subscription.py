"""查询结果订阅推送模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class QuerySubscription(Base):
    """查询结果订阅配置"""
    __tablename__ = "query_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=True, index=True)
    semantic_metric_key = Column(String(100), nullable=True, index=True)
    semantic_query = Column(JSON, nullable=True)
    cron_expression = Column(String(50), nullable=False)
    notify_channel = Column(String(20), nullable=False, default="feishu")  # feishu / email
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # relationships
    user = relationship("User", foreign_keys=[user_id])
    template = relationship("Template", foreign_keys=[template_id])
    executions = relationship("SubscriptionExecution", back_populates="subscription", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "template_id": self.template_id,
            "semantic_metric_key": self.semantic_metric_key,
            "semantic_query": self.semantic_query,
            "cron_expression": self.cron_expression,
            "notify_channel": self.notify_channel,
            "is_active": self.is_active,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # related names for frontend display
            "template_name": self.template.name if self.template else None,
            "metric_name": self.semantic_metric_key,
            "username": self.user.username if self.user else None,
        }


class SubscriptionExecution(Base):
    """订阅执行记录"""
    __tablename__ = "subscription_executions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    subscription_id = Column(Integer, ForeignKey("query_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default="pending")  # pending / success / failed
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    subscription = relationship("QuerySubscription", back_populates="executions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "status": self.status,
            "result_summary": self.result_summary,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }
