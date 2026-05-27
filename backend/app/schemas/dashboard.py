from pydantic import ConfigDict, BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DashboardLayoutResponse(BaseModel):
    id: int
    user_id: int
    name: str
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DashboardLayoutCreate(BaseModel):
    name: str = "新建布局"
    is_default: bool = False


class DashboardLayoutUpdate(BaseModel):
    name: Optional[str] = None
    is_default: Optional[bool] = None


class WidgetConfigResponse(BaseModel):
    id: Optional[int] = None
    widget_type: str
    widget_subtype: Optional[str] = None
    title: str
    grid_x: int = 0
    grid_y: int = 0
    grid_w: int = 4
    grid_h: int = 2
    position: int = 0
    visible: bool = True
    extra_config: Optional[Dict[str, Any]] = None
    drilldown_config: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class WidgetConfigCreate(BaseModel):
    widget_type: str
    widget_subtype: Optional[str] = None
    title: str = ""
    grid_x: int = 0
    grid_y: int = 0
    grid_w: int = 4
    grid_h: int = 2
    visible: bool = True
    extra_config: Optional[Dict[str, Any]] = None
    drilldown_config: Optional[Dict[str, Any]] = None


class WidgetConfigUpdate(BaseModel):
    title: Optional[str] = None
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None
    grid_w: Optional[int] = None
    grid_h: Optional[int] = None
    visible: Optional[bool] = None
    extra_config: Optional[Dict[str, Any]] = None
    drilldown_config: Optional[Dict[str, Any]] = None


class DashboardLayoutDetail(DashboardLayoutResponse):
    widgets: List[WidgetConfigResponse] = []


class DashboardWidgetConfigResponse(BaseModel):
    id: Optional[int] = None
    widget_type: str
    title: str
    position: int
    visible: bool

    model_config = ConfigDict(from_attributes=True)


class DashboardWidgetUpdate(BaseModel):
    widget_type: str
    title: str
    visible: bool


class DashboardLayoutUpdateOld(BaseModel):
    widgets: List[DashboardWidgetUpdate]


class DashboardDataResponse(BaseModel):
    data_source_count: int = 0
    query_count: int = 0
    export_count: int = 0
    template_count: int = 0
    recent_queries: List[dict] = []
    recent_templates: List[dict] = []
    chart_query_trend: List[dict] = []
    chart_data_source_pie: List[dict] = []
    chart_export_trend: List[dict] = []
    chart_template_pie: List[dict] = []
    chart_duration_scatter: List[dict] = []


# ==================== 钻取相关 Schema ====================

class DrilldownClickData(BaseModel):
    """图表点击数据"""
    field: str = Field(..., description="点击的字段名")
    value: Any = Field(..., description="点击的值")
    label: Optional[str] = Field(None, description="显示标签")


class DrilldownRequest(BaseModel):
    """钻取请求"""
    widget_id: int = Field(..., description="Widget ID（获取钻取配置）")
    template_id: int = Field(..., description="目标模板 ID")
    click_data: DrilldownClickData = Field(..., description="图表点击数据")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加参数")


class DrilldownResponse(BaseModel):
    """钻取响应"""
    columns: List[str]
    rows: List[List[Any]]
    total: int
    execution_time_ms: int
    title: Optional[str] = Field(None, description="下钻标题")
