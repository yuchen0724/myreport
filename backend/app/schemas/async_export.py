# backend/app/schemas/async_export.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AsyncExportRequest(BaseModel):
    """异步导出请求"""
    data_source_id: int = Field(..., description="数据源ID")
    sql: str = Field(..., description="SQL查询语句")
    export_type: str = Field(..., description="导出类型: excel/pdf")
    filename: Optional[str] = Field(None, description="文件名")

class AsyncExportResponse(BaseModel):
    """异步导出响应"""
    task_id: str
    status: str
    message: str

class ExportTaskStatus(BaseModel):
    """导出任务状态"""
    id: str
    status: str
    file_path: Optional[str]
    error_message: Optional[str]
    row_count: Optional[int]
    created_at: Optional[datetime] = None
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: float  # 0-100
