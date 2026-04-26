"""审计日志Schema"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class AuditLogBase(BaseModel):
    """审计日志基础模型"""
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    """创建审计日志"""
    user_id: int


class AuditLogResponse(BaseModel):
    """审计日志响应"""
    id: int
    user_id: int
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """审计日志列表响应"""
    logs: list[AuditLogResponse]
    total: int
    skip: int
    limit: int


class UserActivityResponse(BaseModel):
    """用户活动响应"""
    total_actions: int
    action_counts: Dict[str, int]
    success_count: int
    failure_count: int
    success_rate: float


class SystemStatsResponse(BaseModel):
    """系统统计响应"""
    total_actions: int
    action_counts: Dict[str, int]
    resource_type_counts: Dict[str, int]
    success_count: int
    failure_count: int
    success_rate: float
    active_users: int
