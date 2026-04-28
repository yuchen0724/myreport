from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class SQLQueryRequest(BaseModel):
    data_source_id: int
    sql: str = Field(..., min_length=1)
    params: Optional[dict] = None
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(50, ge=1, le=1000, description="每页条数")


class SQLQueryResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    total: int
    page: int
    page_size: int
    execution_time_ms: int


class QueryHistoryResponse(BaseModel):
    id: int
    user_id: int
    data_source_id: Optional[int] = None
    query_type: str
    query_text: str
    execution_time_ms: Optional[int] = None
    row_count: Optional[int] = None
    created_at: Optional[datetime] = None
