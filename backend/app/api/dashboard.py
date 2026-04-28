from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.dashboard import (
    DashboardWidgetConfigResponse,
    DashboardLayoutUpdate,
    DashboardDataResponse,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/widgets", response_model=List[DashboardWidgetConfigResponse])
async def get_dashboard_widgets(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    configs = service.get_widgets(current_user_id)
    return [DashboardWidgetConfigResponse.model_validate(c) for c in configs]


@router.put("/widgets", response_model=List[DashboardWidgetConfigResponse])
async def save_dashboard_widgets(
    payload: DashboardLayoutUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    configs = service.save_widgets(
        current_user_id,
        [w.model_dump() for w in payload.widgets],
    )
    return [DashboardWidgetConfigResponse.model_validate(c) for c in configs]


@router.get("/data", response_model=DashboardDataResponse)
async def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    data = service.get_dashboard_data(current_user_id)
    return DashboardDataResponse(**data)
