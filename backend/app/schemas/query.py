from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class SQLQueryRequest(BaseModel):
    data_source_id: int
    sql: str = Field(..., min_length=1)
    params: Optional[dict] = None
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(50, ge=1, le=1000, description="每页条数")
    # 游标分页：传递上一页最后一行排序列的值，格式如 "S99,2025-40"
    cursor: Optional[str] = Field(None, description="游标（上一页最后一行排序列的值）")
    # 是否跳过深度分页的 ORDER BY 检查（NL2SQL 查询不需要，模板查询需要）
    skip_deep_pagination_check: bool = Field(False, description="是否跳过深度分页 ORDER BY 检查")


class SQLQueryResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    total: int
    page: int
    page_size: int
    execution_time_ms: int
    suggest_async: bool = False
    # 游标分页
    cursor: Optional[str] = Field(None, description="当前页游标（最后一行排序列的值）")
    next_cursor: Optional[str] = Field(None, description="下一页游标")
    cache_hit: bool = Field(False, description="是否命中缓存")


class QueryHistoryResponse(BaseModel):
    id: int
    user_id: int
    data_source_id: Optional[int] = None
    query_type: str
    query_text: str
    execution_time_ms: Optional[int] = None
    row_count: Optional[int] = None
    created_at: Optional[datetime] = None
