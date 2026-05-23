"""定时报表数据模型"""
from datetime import datetime
from typing import Optional, List, Any

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, ForeignKey, Text, Index
from sqlalchemy.sql import func

from app.core.database import Base


class ScheduledReport(Base):
    """定时报表配置"""
    __tablename__ = "scheduled_reports"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(200), nullable=False)
    cron_expression = Column(String(50), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    parameters = Column(JSON, default=dict)
    output_format = Column(String(20), default="excel")  # excel / pdf
    recipients = Column(JSON, default=list)  # [{email, user_id}]
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_scheduled_reports_enabled_next", "enabled", "next_run_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "cron_expression": self.cron_expression,
            "template_id": self.template_id,
            "data_source_id": self.data_source_id,
            "parameters": self.parameters or {},
            "output_format": self.output_format,
            "recipients": self.recipients or [],
            "enabled": self.enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ReportDelivery(Base):
    """报表投递记录"""
    __tablename__ = "report_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    scheduled_report_id = Column(Integer, ForeignKey("scheduled_reports.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending / success / failed
    file_path = Column(Text, nullable=True)
    file_name = Column(String(200), nullable=True)
    error_message = Column(Text, nullable=True)
    generated_at = Column(DateTime, server_default=func.now())
    delivered_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_report_delivery_scheduled", "scheduled_report_id", "generated_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scheduled_report_id": self.scheduled_report_id,
            "status": self.status,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "error_message": self.error_message,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
        }
