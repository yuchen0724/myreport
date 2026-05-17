from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.dashboard import (
    DashboardWidgetConfigResponse,
    DashboardLayoutUpdateOld,
    DashboardDataResponse,
    DashboardLayoutResponse,
    DashboardLayoutCreate,
    DashboardLayoutUpdate,
    DashboardLayoutDetail,
    WidgetConfigResponse,
    WidgetConfigCreate,
    WidgetConfigUpdate,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


# ==================== 布局 CRUD ====================

@router.get("/layouts", response_model=List[DashboardLayoutResponse])
async def list_layouts(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    return service.get_layouts(current_user_id)


@router.get("/layouts/{layout_id}", response_model=DashboardLayoutDetail)
async def get_layout(
    layout_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    layout = service.get_layout(layout_id, current_user_id)
    if not layout:
        raise HTTPException(status_code=404, detail="布局不存在")
    widgets = service.get_widgets(layout_id)
    return DashboardLayoutDetail(
        id=layout.id,
        user_id=layout.user_id,
        name=layout.name,
        is_default=layout.is_default,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
        widgets=[WidgetConfigResponse.model_validate(w) for w in widgets],
    )


@router.post("/layouts", response_model=DashboardLayoutDetail, status_code=201)
async def create_layout(
    payload: DashboardLayoutCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    layout = service.create_layout(current_user_id, payload.name)
    return DashboardLayoutDetail(
        id=layout.id,
        user_id=layout.user_id,
        name=layout.name,
        is_default=layout.is_default,
        created_at=layout.created_at,
        updated_at=layout.updated_at,
        widgets=[],
    )


@router.put("/layouts/{layout_id}", response_model=DashboardLayoutResponse)
async def update_layout(
    layout_id: int,
    payload: DashboardLayoutUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    layout = service.update_layout(layout_id, current_user_id, payload.model_dump(exclude_none=True))
    if not layout:
        raise HTTPException(status_code=404, detail="布局不存在")
    return layout


@router.delete("/layouts/{layout_id}")
async def delete_layout(
    layout_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    if not service.delete_layout(layout_id, current_user_id):
        raise HTTPException(status_code=404, detail="布局不存在")
    return {"message": "布局已删除"}


# ==================== Widget CRUD（基于布局） ====================

@router.get("/layouts/{layout_id}/widgets", response_model=List[WidgetConfigResponse])
async def list_widgets(
    layout_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    layout = service.get_layout(layout_id, current_user_id)
    if not layout:
        raise HTTPException(status_code=404, detail="布局不存在")
    return service.get_widgets(layout_id)


@router.post("/layouts/{layout_id}/widgets", response_model=WidgetConfigResponse, status_code=201)
async def create_widget(
    layout_id: int,
    payload: WidgetConfigCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    layout = service.get_layout(layout_id, current_user_id)
    if not layout:
        raise HTTPException(status_code=404, detail="布局不存在")
    widget = service.create_widget(layout_id, current_user_id, payload.model_dump())
    return widget


@router.put("/layouts/{layout_id}/widgets/{widget_id}", response_model=WidgetConfigResponse)
async def update_widget(
    layout_id: int,
    widget_id: int,
    payload: WidgetConfigUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    widget = service.update_widget(widget_id, current_user_id, payload.model_dump(exclude_none=True))
    if not widget:
        raise HTTPException(status_code=404, detail="组件不存在")
    return widget


@router.delete("/layouts/{layout_id}/widgets/{widget_id}")
async def delete_widget(
    layout_id: int,
    widget_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    if not service.delete_widget(widget_id, current_user_id):
        raise HTTPException(status_code=404, detail="组件不存在")
    return {"message": "组件已删除"}


# ==================== 批量保存布局内所有 widgets ====================

@router.put("/layouts/{layout_id}/widgets", response_model=List[WidgetConfigResponse])
async def save_layout_widgets(
    layout_id: int,
    payload: List[WidgetConfigCreate],
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    layout = service.get_layout(layout_id, current_user_id)
    if not layout:
        raise HTTPException(status_code=404, detail="布局不存在")
    configs = service.save_layout_widgets(
        layout_id,
        current_user_id,
        [w.model_dump() for w in payload],
    )
    return configs


# ==================== 旧 API 兼容 ====================

@router.get("/widgets", response_model=List[DashboardWidgetConfigResponse])
async def get_dashboard_widgets(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    configs = service.get_legacy_widgets(current_user_id)
    return [DashboardWidgetConfigResponse.model_validate(c) for c in configs]


@router.put("/widgets", response_model=List[DashboardWidgetConfigResponse])
async def save_dashboard_widgets(
    payload: DashboardLayoutUpdateOld,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    service = DashboardService(db)
    configs = service.save_legacy_widgets(
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
