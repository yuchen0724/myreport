import uuid
from io import BytesIO
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, Alignment
from app.services.query_service import QueryService
from app.schemas.report import ExcelExportRequest
from app.config import get_settings
from app.utils.pdf_generator import PDFGenerator
from app.models.export_task import ExportTask


class ReportService:
    def __init__(self, db):
        self.db = db
        self.query_service = QueryService(db)
        self.pdf_generator = PDFGenerator()
        self.settings = get_settings()
        self.last_row_count = 0

    def generate_excel(self, request: ExcelExportRequest, user_id: int) -> BytesIO:
        """生成 Excel 文件"""
        columns, rows, total = self.query_service.execute_export_sql(
            request.data_source_id,
            request.sql,
            user_id,
            params=request.params,
            max_rows=self.settings.export_max_rows,
        )
        self.last_row_count = total

        wb = Workbook(write_only=True)
        ws = wb.create_sheet()
        ws.title = request.sheet_name or "Sheet1"

        header = []
        for column in columns:
            cell = WriteOnlyCell(ws, value=column)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")
            header.append(cell)
        ws.append(header)

        for row in rows:
            values = []
            for value in row:
                if hasattr(value, 'tzinfo') and value.tzinfo is not None:
                    value = value.replace(tzinfo=None)
                values.append(value)
            ws.append(values)

        # 保存到内存
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    def generate_pdf(self, request: ExcelExportRequest, user_id: int) -> BytesIO:
        """
        生成 PDF 文件

        Args:
            request: 导出请求
            user_id: 用户 ID

        Returns:
            PDF 文件流
        """
        columns, rows, total = self.query_service.execute_export_sql(
            request.data_source_id,
            request.sql,
            user_id,
            params=request.params,
            max_rows=self.settings.pdf_export_max_rows,
        )
        self.last_row_count = total

        # 生成 PDF
        pdf_buffer = self.pdf_generator.generate_pdf(
            title=request.filename or "Report",
            columns=columns,
            rows=rows,
            filename=request.filename
        )

        return pdf_buffer

    def generate_excel_async(self, request: ExcelExportRequest, user_id: int) -> str:
        """异步生成 Excel 文件（返回任务 ID）"""
        from app.tasks.export_tasks import export_excel_async

        task_id = str(uuid.uuid4())

        task = ExportTask(
            id=task_id,
            user_id=user_id,
            status="PENDING",
            sql=request.sql
        )
        self.db.add(task)
        self.db.commit()

        export_excel_async.delay(
            task_id,
            request.data_source_id,
            request.sql,
            user_id,
            request.params,
        )

        return task_id
