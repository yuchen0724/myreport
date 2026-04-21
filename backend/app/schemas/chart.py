# backend/app/schemas/chart.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal

class ChartConfig(BaseModel):
    """图表配置"""
    chart_type: Literal["line", "bar", "pie", "scatter"] = Field(..., description="图表类型")
    x_axis: str = Field(..., description="X 轴字段")
    y_axis: str = Field(..., description="Y 轴字段")
    title: Optional[str] = Field(None, description="图表标题")
    color: Optional[str] = Field(None, description="颜色")

class ChartRequest(BaseModel):
    """图表请求"""
    data_source_id: int = Field(..., description="数据源 ID")
    sql: str = Field(..., description="SQL 查询")
    chart_config: ChartConfig = Field(..., description="图表配置")

class ChartResponse(BaseModel):
    """图表响应"""
    chart_type: str = Field(..., description="图表类型")
    data: List[Dict[str, Any]] = Field(..., description="图表数据")
    config: Dict[str, Any] = Field(..., description="图表配置")
