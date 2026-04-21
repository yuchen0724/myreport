from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class SQLQueryRequest(BaseModel):
    data_source_id: int
    sql: str = Field(..., min_length=1)
    params: Optional[dict] = None


class SQLQueryResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    total: int
    execution_time_ms: int


class QueryHistoryResponse(BaseModel):
    id: int
    user_id: int
    data_source_id: Optional[int] = None
    query_type: str
    query_text: str
    execution_time_ms: Optional[int] = None
    row_count: Optional[int] = None
    created_at: datetime
