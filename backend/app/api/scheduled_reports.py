"""定时报表 API"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.services.scheduled_report_service import ScheduledReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduled-reports", tags=["定时报表"])


# ── Schema ──

class Recipient(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None


class ScheduledReportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    cron_expression: str = Field(..., description="Cron 表达式，如 '0 8 * * 1'")
    template_id: int
    data_source_id: Optional[int] = None
    parameters: dict = Field(default_factory=dict)
    output_format: str = Field(default="excel", description="excel 或 pdf")
    recipients: list[Recipient] = Field(default_factory=list)


class ScheduledReportUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    template_id: Optional[int] = None
    data_source_id: Optional[int] = None
    parameters: Optional[dict] = None
    output_format: Optional[str] = None
    recipients: Optional[list[Recipient]] = None


class EnableRequest(BaseModel):
    enabled: bool


class DeliveryResponse(BaseModel):
    id: int
    scheduled_report_id: int
    status: str
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    error_message: Optional[str] = None
    generated_at: Optional[str] = None
    delivered_at: Optional[str] = None


# ── Endpoints ──

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_scheduled_report(
    request: ScheduledReportCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """创建定时报表"""
    svc = ScheduledReportService(db)
    try:
        report = svc.create(
            name=request.name,
            cron_expression=request.cron_expression,
            template_id=request.template_id,
            data_source_id=request.data_source_id,
            parameters=request.parameters,
            output_format=request.output_format,
            recipients=[r.model_dump() for r in request.recipients],
            created_by=current_user_id,
        )
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/")
def list_reports(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取定时报表列表"""
    svc = ScheduledReportService(db)
    reports = svc.list_reports(offset=offset, limit=limit)
    return [r.to_dict() for r in reports]


@router.get("/{report_id}")
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取定时报表详情"""
    svc = ScheduledReportService(db)
    report = svc.get(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时报表不存在")
    return report.to_dict()


@router.put("/{report_id}")
def update_report(
    report_id: int,
    request: ScheduledReportUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """更新定时报表"""
    svc = ScheduledReportService(db)
    data = request.model_dump(exclude_unset=True)
    if "recipients" in data and data["recipients"]:
        data["recipients"] = [r.model_dump() if isinstance(r, Recipient) else r for r in data["recipients"]]
    report = svc.update(report_id, **data)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时报表不存在")
    return report.to_dict()


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """删除定时报表"""
    svc = ScheduledReportService(db)
    if not svc.delete(report_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时报表不存在")


@router.post("/{report_id}/toggle")
def toggle_report(
    report_id: int,
    request: EnableRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """启用/禁用定时报表"""
    svc = ScheduledReportService(db)
    report = svc.toggle_enabled(report_id, request.enabled)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时报表不存在")
    return report.to_dict()


@router.post("/{report_id}/run-now")
def run_now(
    report_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """手动立即执行一次定时报表"""
    svc = ScheduledReportService(db)
    report = svc.schedule_next_run(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="定时报表不存在")
    return {"message": "已触发执行", "report": report.to_dict()}


@router.get("/{report_id}/deliveries")
def get_deliveries(
    report_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取报表投递历史"""
    svc = ScheduledReportService(db)
    deliveries = svc.get_deliveries(report_id, offset=offset, limit=limit)
    return [d.to_dict() for d in deliveries]


@router.get("/cron/next/{cron_expression}")
def get_next_run_time(cron_expression: str):
    """计算 cron 表达式下次执行时间"""
    next_time = ScheduledReportService.next_run_time(cron_expression)
    if not next_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的 cron 表达式")
    return {"cron_expression": cron_expression, "next_run_at": next_time}
