# backend/app/tasks/export_tasks.py
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.export_task import ExportTask
from app.services.report_service import ReportService
from app.services.query_service import QueryService
from datetime import datetime
import traceback

@celery_app.task(bind=True)
def export_excel_async(self, task_id: str, data_source_id: int, sql: str, user_id: int):
    """异步导出 Excel 任务"""
    db = SessionLocal()
    try:
        # 更新任务状态为运行中
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task.status = "RUNNING"
        task.started_at = datetime.now()
        db.commit()

        # 生成 Excel
        report_service = ReportService(db)
        from app.schemas.report import ExcelExportRequest
        export_request = ExcelExportRequest(
            data_source_id=data_source_id,
            sql=sql,
            filename=f"export_{task_id}.xlsx"
        )

        excel_data = report_service.generate_excel(export_request, user_id)

        # 保存文件
        file_path = f"/tmp/exports/{task_id}.xlsx"
        with open(file_path, 'wb') as f:
            f.write(excel_data.getvalue())

        # 更新任务状态为成功
        task.status = "SUCCESS"
        task.file_path = file_path
        task.completed_at = datetime.now()
        db.commit()

        return {"status": "success", "file_path": file_path}

    except Exception as e:
        # 更新任务状态为失败
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()

        # 记录错误
        error_trace = traceback.format_exc()
        print(f"导出任务失败: {task_id}\n{error_trace}")

        # 重试
        raise self.retry(exc=e, countdown=60, max_retries=3)

    finally:
        db.close()

@celery_app.task(bind=True)
def export_pdf_async(self, task_id: str, data_source_id: int, sql: str, user_id: int):
    """异步导出 PDF 任务"""
    db = SessionLocal()
    try:
        # 更新任务状态为运行中
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task.status = "RUNNING"
        task.started_at = datetime.now()
        db.commit()

        # 生成 PDF
        report_service = ReportService(db)
        from app.schemas.report import PDFExportRequest
        export_request = PDFExportRequest(
            data_source_id=data_source_id,
            sql=sql,
            filename=f"export_{task_id}.pdf"
        )

        pdf_data = report_service.generate_pdf(export_request, user_id)

        # 保存文件
        file_path = f"/tmp/exports/{task_id}.pdf"
        with open(file_path, 'wb') as f:
            f.write(pdf_data.getvalue())

        # 更新任务状态为成功
        task.status = "SUCCESS"
        task.file_path = file_path
        task.completed_at = datetime.now()
        db.commit()

        return {"status": "success", "file_path": file_path}

    except Exception as e:
        # 更新任务状态为失败
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            db.commit()

        # 记录错误
        error_trace = traceback.format_exc()
        print(f"PDF 导出任务失败: {task_id}\n{error_trace}")

        # 重试
        raise self.retry(exc=e, countdown=60, max_retries=3)

    finally:
        db.close()
