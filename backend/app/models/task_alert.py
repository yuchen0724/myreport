# backend/app/models/task_alert.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class TaskAlert(Base):
    """任务失败告警记录——记录 Celery 任务最终失败时的告警信息"""
    __tablename__ = "task_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), nullable=False, index=True, comment="Celery 任务 ID")
    user_id = Column(Integer, nullable=True, index=True, comment="触发告警的用户 ID")
    task_type = Column(String(50), nullable=False, comment="任务类型: export_excel/export_pdf/train_predict")
    status = Column(String(20), nullable=False, default="unread", comment="告警状态: unread/read/dismissed")
    error_message = Column(Text, nullable=True, comment="错误信息")
    alert_message = Column(String(500), nullable=False, comment="告警摘要")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)
