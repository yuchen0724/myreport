# backend/app/api/alerts.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id, get_current_user
from app.services.notification_service import NotificationService
from app.models.user import User

router = APIRouter(prefix="/api/alerts", tags=["告警通知"])


class AlertResponse(BaseModel):
    id: int
    task_id: str
    user_id: Optional[int] = None
    task_type: str
    status: str
    error_message: Optional[str] = None
    alert_message: str
    created_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    count: int


@router.get("", response_model=List[AlertResponse])
async def get_alerts(
    task_type: Optional[str] = Query(None, description="过滤任务类型"),
    status: Optional[str] = Query(None, description="过滤状态(unread/read/dismissed)"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的告警列表"""
    service = NotificationService(db)
    # 非管理员只看自己的告警
    user_id = None if current_user.role and current_user.role.name == "admin" else current_user.id
    return service.get_alerts(
        user_id=user_id,
        task_type=task_type,
        status=status,
        limit=limit,
        offset=skip,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_alert_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的未读告警数量"""
    service = NotificationService(db)
    user_id = None if current_user.role and current_user.role.name == "admin" else current_user.id
    count = service.get_unread_count(user_id=user_id)
    return {"count": count}


@router.post("/{alert_id}/read")
async def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将单条告警标记为已读"""
    service = NotificationService(db)
    user_id = None if current_user.role and current_user.role.name == "admin" else current_user.id
    success = service.mark_as_read(alert_id, user_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警不存在或无权操作",
        )
    return {"message": "已标记为已读"}


@router.post("/read-all")
async def mark_all_alerts_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将所有告警标记为已读"""
    service = NotificationService(db)
    user_id = None if current_user.role and current_user.role.name == "admin" else current_user.id
    count = service.mark_all_as_read(user_id=user_id)
    return {"message": f"已标记 {count} 条告警为已读", "count": count}
