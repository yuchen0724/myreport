import uuid
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from typing import Optional
from app.services.query_service import QueryService
from app.schemas.query import SQLQueryRequest
from app.schemas.report import ExcelExportRequest


class ReportService:
    def __init__(self, db):
        self.db = db
        self.query_service = QueryService(db)

    def generate_excel(self, request: ExcelExportRequest, user_id: int) -> BytesIO:
        """生成 Excel 文件"""
        # 执行查询
        query_request = SQLQueryRequest(
            data_source_id=request.data_source_id,
            sql=request.sql,
            params={}
        )
        result = self.query_service.execute_sql(query_request, user_id)

        # 创建 Excel 工作簿
        wb = Workbook()
        ws = wb.active
        ws.title = request.sheet_name or "Sheet1"

        # 写入表头
        for col_idx, column in enumerate(result.columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=column)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        # 写入数据
        for row_idx, row in enumerate(result.rows, 2):
            for col_idx, value in enumerate(row, 1):
                # 处理带时区的 datetime 对象
                if hasattr(value, 'tzinfo') and value.tzinfo is not None:
                    value = value.replace(tzinfo=None)
                ws.cell(row=row_idx, column=col_idx, value=value)

        # 保存到内存
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def generate_excel_async(self, request: ExcelExportRequest, user_id: int) -> str:
        """异步生成 Excel 文件（返回任务 ID）"""
        task_id = str(uuid.uuid4())
        # TODO: 使用 Celery 异步处理
        return task_id
