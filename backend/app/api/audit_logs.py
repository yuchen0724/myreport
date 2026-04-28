"""审计日志API"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.services.audit_log_service import AuditLogService
from app.schemas.audit_log import AuditLogResponse, AuditLogListResponse, UserActivityResponse, SystemStatsResponse

router = APIRouter(prefix="/api/audit-logs", tags=["审计日志"])


@router.get("", response_model=AuditLogListResponse)
async def get_audit_logs(
    action: Optional[str] = Query(None, description="操作类型"),
    resource_type: Optional[str] = Query(None, description="资源类型"),
    resource_id: Optional[str] = Query(None, description="资源ID"),
    status: Optional[str] = Query(None, description="操作状态"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取当前用户的审计日志列表"""
    audit_service = AuditLogService(db)

    logs = audit_service.get_logs(
        user_id=current_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )

    return {
        "logs": logs,
        "total": len(logs),
        "skip": skip,
        "limit": limit
    }


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取审计日志详情"""
    audit_service = AuditLogService(db)
    log = audit_service.get_log_by_id(log_id)

    if not log:
        raise HTTPException(status_code=404, detail="审计日志不存在")

    # 只能查看自己的日志（管理员可查看全部，待实现）
    if log.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权查看该日志")

    return log


@router.get("/user/{user_id}/activity", response_model=UserActivityResponse)
async def get_user_activity(
    user_id: int,
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取当前用户的活动统计"""
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权查看该用户的活动统计")

    audit_service = AuditLogService(db)
    activity = audit_service.get_user_activity(user_id, start_date, end_date)

    return activity


@router.get("/system/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取系统统计信息（管理员功能，暂未开放）"""
    raise HTTPException(status_code=403, detail="系统统计功能需要管理员权限")
