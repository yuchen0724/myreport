from pydantic import BaseModel
from typing import Optional


class ExcelExportRequest(BaseModel):
    data_source_id: int
    sql: str
    filename: Optional[str] = "export.xlsx"
    sheet_name: Optional[str] = "Sheet1"


class ExcelExportResponse(BaseModel):
    task_id: str
    status: str
    message: str
