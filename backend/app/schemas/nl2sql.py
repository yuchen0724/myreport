# backend/app/schemas/nl2sql.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class NL2SQLRequest(BaseModel):
    """NL2SQL 查询请求"""
    question: str = Field(..., description="自然语言问题")
    data_source_id: int = Field(..., description="数据源 ID")
    context: Optional[str] = Field(None, description="上下文信息")
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
