"""查询结果订阅推送 API"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionExecutionResponse,
)
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions", tags=["查询订阅推送"])


# ── Schemas ──


class ToggleRequest(BaseModel):
    is_active: bool


# ── Endpoints ──


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    request: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """创建查询订阅"""
    svc = SubscriptionService(db)
    try:
        sub = svc.create(
            user_id=current_user_id,
            template_id=request.template_id,
            cron_expression=request.cron_expression,
            notify_channel=request.notify_channel,
            semantic_metric_key=request.semantic_metric_key,
            semantic_query=request.semantic_query,
        )
        return sub.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[SubscriptionResponse])
def list_subscriptions(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取当前用户的订阅列表"""
    svc = SubscriptionService(db)
    subs = svc.list_subscriptions(user_id=current_user_id, offset=offset, limit=limit)
    return [s.to_dict() for s in subs]


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取订阅详情"""
    svc = SubscriptionService(db)
    sub = svc.get(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权访问该订阅")
    return sub.to_dict()


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(
    subscription_id: int,
    request: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """更新订阅"""
    svc = SubscriptionService(db)
    sub = svc.get(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权修改该订阅")
    try:
        data = request.model_dump(exclude_unset=True)
        updated = svc.update(subscription_id, **data)
        return updated.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """删除订阅"""
    svc = SubscriptionService(db)
    sub = svc.get(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权删除该订阅")
    svc.delete(subscription_id)


@router.post("/{subscription_id}/toggle", response_model=SubscriptionResponse)
def toggle_subscription(
    subscription_id: int,
    request: ToggleRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """启用/禁用订阅"""
    svc = SubscriptionService(db)
    sub = svc.get(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权操作该订阅")
    updated = svc.toggle_active(subscription_id, request.is_active)
    return updated.to_dict()


@router.post("/{subscription_id}/run")
def run_subscription_now(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """手动触发订阅执行"""
    svc = SubscriptionService(db)
    sub = svc.get(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权操作该订阅")

    # import here to avoid circular import
    from app.tasks.subscription_tasks import execute_subscription_task

    result = execute_subscription_task.delay(subscription_id)
    return {"message": "订阅执行已触发", "task_id": result.id}


@router.get("/{subscription_id}/executions", response_model=list[SubscriptionExecutionResponse])
def get_executions(
    subscription_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取订阅执行记录"""
    svc = SubscriptionService(db)
    sub = svc.get(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    if sub.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权访问该订阅")
    execs = svc.get_executions(subscription_id, offset=offset, limit=limit)
    return [e.to_dict() for e in execs]


@router.get("/cron/next/{cron_expression}")
def get_next_run_time(cron_expression: str):
    """计算 cron 表达式下次执行时间"""
    next_time = SubscriptionService.next_run_time(cron_expression)
    if not next_time:
        raise HTTPException(status_code=400, detail="无效的 cron 表达式")
    return {"cron_expression": cron_expression, "next_run_at": next_time}
