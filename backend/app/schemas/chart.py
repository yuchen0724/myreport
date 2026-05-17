# backend/app/schemas/chart.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal

class ChartConfig(BaseModel):
    """图表配置"""
    chart_type: Literal["line", "bar", "pie", "scatter", "radar", "gauge", "funnel", "heatmap", "treemap", "boxplot"] = Field(..., description="图表类型")
    x_axis: str = Field(..., description="X 轴字段")
    y_axis: str = Field(..., description="Y 轴字段")
    title: Optional[str] = Field(None, description="图表标题")
    color: Optional[str] = Field(None, description="颜色")
    # 新增炫酷配置
    colorTheme: Optional[str] = Field("blue", description="配色主题: blue/purple/cyan/orange/green/pink")
    height: Optional[str] = Field("400px", description="图表高度")
    showParticles: Optional[bool] = Field(False, description="是否显示粒子特效")
    maxValue: Optional[float] = Field(None, description="最大值（雷达图/仪表盘用）")

class DrillItem(BaseModel):
    """钻取层级项"""
    field: str = Field(..., description="字段名")
    value: str = Field(..., description="字段值")
    label: Optional[str] = Field(None, description="显示标签")

class ChartRequest(BaseModel):
    """图表请求"""
    data_source_id: int = Field(..., description="数据源 ID")
    sql: str = Field(..., description="SQL 查询")
    chart_config: ChartConfig = Field(..., description="图表配置")
    drill_path: Optional[List[DrillItem]] = Field(None, description="钻取路径")

class ChartResponse(BaseModel):
    """图表响应"""
    chart_type: str = Field(..., description="图表类型")
    data: List[Dict[str, Any]] = Field(..., description="图表数据")
    config: Dict[str, Any] = Field(..., description="图表配置")
