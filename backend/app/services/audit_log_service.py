"""审计日志服务"""

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.audit_log import AuditLog
import json


class AuditLogService:
    """审计日志服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_log(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        """创建审计日志
        
        Args:
            user_id: 用户ID
            action: 操作类型
            resource_type: 资源类型
            resource_id: 资源ID
            details: 操作详情
            ip_address: IP地址
            user_agent: 用户代理
            status: 操作状态
            error_message: 错误信息
        
        Returns:
            审计日志对象
        """
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log
    
    def get_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[AuditLog]:
        """获取审计日志列表
        
        Args:
            user_id: 用户ID
            action: 操作类型
            resource_type: 资源类型
            resource_id: 资源ID
            status: 操作状态
            start_date: 开始日期
            end_date: 结束日期
            skip: 跳过记录数
            limit: 返回记录数
        
        Returns:
            审计日志列表
        """
        query = self.db.query(AuditLog)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.filter(AuditLog.resource_id == str(resource_id))
        if status:
            query = query.filter(AuditLog.status == status)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_log_by_id(self, log_id: int) -> Optional[AuditLog]:
        """根据ID获取审计日志"""
        return self.db.query(AuditLog).filter(AuditLog.id == log_id).first()
    
    def get_user_activity(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取用户活动统计
        
        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            用户活动统计
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        logs = query.all()
        
        # 统计各类操作数量
        action_counts = {}
        for log in logs:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1
        
        # 统计成功率
        success_count = sum(1 for log in logs if log.status == "success")
        failure_count = sum(1 for log in logs if log.status == "failure")
        
        return {
            "total_actions": len(logs),
            "action_counts": action_counts,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / len(logs) if logs else 0
        }
    
    def get_system_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取系统统计信息
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            系统统计信息
        """
        query = self.db.query(AuditLog)
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        logs = query.all()
        
        # 统计各类操作数量
        action_counts = {}
        resource_type_counts = {}
        for log in logs:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1
            resource_type_counts[log.resource_type] = resource_type_counts.get(log.resource_type, 0) + 1
        
        # 统计成功率
        success_count = sum(1 for log in logs if log.status == "success")
        failure_count = sum(1 for log in logs if log.status == "failure")
        
        # 统计活跃用户
        active_users = set(log.user_id for log in logs)
        
        return {
            "total_actions": len(logs),
            "action_counts": action_counts,
            "resource_type_counts": resource_type_counts,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / len(logs) if logs else 0,
            "active_users": len(active_users)
        }
