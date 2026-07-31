"""AI report design and metric governance endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_deps import get_current_user_id
from app.core.database import get_db
from app.schemas.ai_design import MetricDraftRequest, ReportDraftRequest
from app.services.ai_design_service import AIDesignService
from app.services.data_source_service import DataSourceService


router = APIRouter(prefix="/api/ai-design", tags=["AI 报表与指标治理"])


@router.post("/report-draft")
async def generate_report_draft(
    request: ReportDraftRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    DataSourceService(db).require_access(request.data_source_id, current_user_id)
    return AIDesignService(db).generate_report_draft(
        request.data_source_id, request.requirement, current_user_id, request.preferred_chart,
    )


@router.get("/metric-audit/{data_source_id}")
async def audit_metrics(
    data_source_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    DataSourceService(db).require_access(data_source_id, current_user_id)
    return AIDesignService(db).audit_metrics(data_source_id, current_user_id)


@router.post("/metric-draft")
async def generate_metric_draft(
    request: MetricDraftRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    DataSourceService(db).require_access(request.data_source_id, current_user_id)
    return AIDesignService(db).generate_metric_draft(
        request.data_source_id, request.requirement, current_user_id,
    )
