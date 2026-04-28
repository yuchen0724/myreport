from pydantic import BaseModel
from typing import Optional, List


class DashboardWidgetConfigResponse(BaseModel):
    id: Optional[int] = None
    widget_type: str
    title: str
    position: int
    visible: bool

    class Config:
        from_attributes = True


class DashboardWidgetUpdate(BaseModel):
    widget_type: str
    title: str
    visible: bool


class DashboardLayoutUpdate(BaseModel):
    widgets: List[DashboardWidgetUpdate]


class DashboardDataResponse(BaseModel):
    data_source_count: int = 0
    query_count: int = 0
    export_count: int = 0
    template_count: int = 0
    recent_queries: List[dict] = []
    recent_templates: List[dict] = []
