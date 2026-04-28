# backend/app/tasks/export_tasks.py
import logging
import os
import traceback
from datetime import datetime

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.export_task import ExportTask
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

# 导出文件存储目录（可通过环境变量配置）
EXPORT_DIR = os.getenv("EXPORT_DIR", "/tmp/exports")


@celery_app.task(bind=True)
def export_excel_async(self, task_id: str, data_source_id: int, sql: str, user_id: int):
    """异步导出 Excel 任务"""
    db = SessionLocal()
    try:
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task.status = "RUNNING"
        task.started_at = datetime.now()
        db.commit()

        report_service = ReportService(db)
        from app.schemas.report import ExcelExportRequest
        export_request = ExcelExportRequest(
            data_source_id=data_source_id,
            sql=sql,
            filename=f"export_{task_id}.xlsx"
        )

        excel_data = report_service.generate_excel(export_request, user_id)

        os.makedirs(EXPORT_DIR, exist_ok=True)
        file_path = os.path.join(EXPORT_DIR, f"{task_id}.xlsx")
        with open(file_path, 'wb') as f:
            f.write(excel_data.getvalue())

        task.status = "SUCCESS"
        task.file_path = file_path
        task.completed_at = datetime.now()
        db.commit()

        return {"status": "success", "file_path": file_path}

    except Exception as e:
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()

        logger.error("导出任务失败: %s\n%s", task_id, traceback.format_exc())
        raise self.retry(exc=e, countdown=60, max_retries=3)

    finally:
        db.close()


@celery_app.task(bind=True)
def export_pdf_async(self, task_id: str, data_source_id: int, sql: str, user_id: int):
    """异步导出 PDF 任务"""
    db = SessionLocal()
    try:
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task.status = "RUNNING"
        task.started_at = datetime.now()
        db.commit()

        report_service = ReportService(db)
        from app.schemas.report import PDFExportRequest
        export_request = PDFExportRequest(
            data_source_id=data_source_id,
            sql=sql,
            filename=f"export_{task_id}.pdf"
        )

        pdf_data = report_service.generate_pdf(export_request, user_id)

        os.makedirs(EXPORT_DIR, exist_ok=True)
        file_path = os.path.join(EXPORT_DIR, f"{task_id}.pdf")
        with open(file_path, 'wb') as f:
            f.write(pdf_data.getvalue())

        task.status = "SUCCESS"
        task.file_path = file_path
        task.completed_at = datetime.now()
        db.commit()

        return {"status": "success", "file_path": file_path}

    except Exception as e:
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()

        logger.error("PDF 导出任务失败: %s\n%s", task_id, traceback.format_exc())
        raise self.retry(exc=e, countdown=60, max_retries=3)

    finally:
        db.close()
