from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.models.audit_log import AuditLog


class AuditLogRepository:
    """审计日志数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, audit_log: AuditLog) -> AuditLog:
        """创建审计日志"""
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log

    def get_by_id(self, log_id: int) -> Optional[AuditLog]:
        """根据 ID 获取审计日志"""
        return self.db.query(AuditLog).filter(AuditLog.id == log_id).first()

    def query(self):
        """返回查询构建器"""
        return self.db.query(AuditLog)
