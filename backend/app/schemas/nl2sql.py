# backend/app/schemas/nl2sql.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class NL2SQLRequest(BaseModel):
    """NL2SQL 查询请求"""
    question: str = Field(..., description="自然语言问题")
    data_source_id: int = Field(..., description="数据源 ID")
    context: Optional[str] = Field(None, description="上下文信息")
    group_id: Optional[int] = Field(None, description="用户所属集团ID，用于分表选择")


class NL2SQLChartConfig(BaseModel):
    """LLM 推荐图表配置"""
    chart_type: str = Field("bar", description="图表类型: bar, line, pie, scatter")
    x_axis: str = Field("", description="X 轴字段名")
    y_axis: str = Field("", description="Y 轴字段名")
    reason: str = Field("", description="推荐原因")


class GeneratedSQLResult(BaseModel):
    """LLM 生成 SQL 的内部结构化输出"""
    sql: str = Field(..., description="生成的 SELECT SQL 语句")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="置信度 0-1")
    explanation: str = Field("", description="SQL 生成逻辑说明")
    chart_config: Optional[NL2SQLChartConfig] = Field(None, description="推荐图表配置")


class SQLSuggestion(BaseModel):
    """SQL 建议"""
    sql: str = Field(..., description="生成的 SQL")
    confidence: float = Field(..., description="置信度 0-1")
    explanation: Optional[str] = Field(None, description="解释")
    chart_config: Optional[Dict[str, Any]] = Field(None, description="图表配置：chart_type(图表类型), x_axis(X轴字段), y_axis(Y轴字段)")


class NL2SQLResponse(BaseModel):
    """NL2SQL 查询响应"""
    suggestions: List[SQLSuggestion] = Field(..., description="SQL 建议列表")
    selected_sql: str = Field(..., description="选中的 SQL")
    query_result: Optional[Dict[str, Any]] = Field(None, description="查询结果")
    execution_time_ms: Optional[int] = Field(None, description="执行时间（毫秒）")
    recommended_chart: Optional[Dict[str, Any]] = Field(None, description="推荐的图表配置")
