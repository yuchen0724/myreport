from pydantic import BaseModel, Field
from typing import Any, Optional


class ExcelExportRequest(BaseModel):
    data_source_id: int
    sql: str
    filename: Optional[str] = "export.xlsx"
    sheet_name: Optional[str] = "Sheet1"
    params: dict[str, Any] = Field(default_factory=dict)


class PDFExportRequest(ExcelExportRequest):
    filename: Optional[str] = "export.pdf"


class ExcelExportResponse(BaseModel):
    task_id: str
    status: str
    message: str
