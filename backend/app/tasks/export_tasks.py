# backend/app/tasks/export_tasks.py
import logging
import os
import traceback
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.export_task import ExportTask
from app.services.report_service import ReportService
from app.tasks.base_task import ExportTaskBase

logger = logging.getLogger(__name__)

# 导出文件存储目录（可通过环境变量配置）
EXPORT_DIR = os.getenv("EXPORT_DIR", "/tmp/exports")


def _export_excel_impl(self, task_id: str, data_source_id: int, sql: str, user_id: int) -> dict:
    """
    Excel 导出内部实现（抽取为普通函数，方便测试和复用）。

    使用 _export_excel_impl 允许在测试中直接调用，避免 Celery 任务包装器的干扰。
    幂等保证：如果任务已经是 SUCCESS 状态且有 file_path，直接返回成功。
    """
    db = SessionLocal()
    try:
        # ===== 幂等检查：如果任务已成功完成，直接返回 =====
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if task.status == "SUCCESS" and task.file_path:
            logger.info("任务已成功完成，跳过重试: task_id=%s", task_id)
            return {"status": "success", "file_path": task.file_path, "idempotent": True}

        # 更新为运行中状态
        if task.status != "RUNNING":
            task.status = "RUNNING"
            task.started_at = datetime.now(timezone.utc)
        task.retry_count = (task.retry_count or 0) + 1
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
        task.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("导出任务成功: task_id=%s", task_id)
        return {"status": "success", "file_path": file_path}

    except Exception as e:
        logger.error("导出任务失败: %s\n%s", task_id, traceback.format_exc())

        # 更新数据库记录
        task_obj = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if task_obj and task_obj.status != "FAILED":
            task_obj.status = "FAILED"
            task_obj.error_message = str(e)
            task_obj.completed_at = datetime.now(timezone.utc)
            db.commit()

        # 检查重试机会，指数退避
        current_retries = task_obj.retry_count if task_obj else 0
        if current_retries < 3:
            countdown = 60 * (3 ** current_retries)  # 60s, 180s, 540s
            logger.warning(
                "导出任务即将重试 (%d/3): task_id=%s, countdown=%ds",
                current_retries + 1, task_id, countdown,
            )
            raise self.retry(exc=e, countdown=countdown, max_retries=3)
        else:
            logger.error(
                "导出任务最终失败（已达最大重试次数）: task_id=%s, error=%s",
                task_id, e,
            )
            raise  # 不再重试，让异常向上传播

    finally:
        db.close()


def _export_pdf_impl(self, task_id: str, data_source_id: int, sql: str, user_id: int) -> dict:
    """
    PDF 导出内部实现（抽取为普通函数，方便测试和复用）。

    幂等保证：如果任务已经是 SUCCESS 状态且有 file_path，直接返回成功。
    """
    db = SessionLocal()
    try:
        # ===== 幂等检查 =====
        task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if task.status == "SUCCESS" and task.file_path:
            logger.info("PDF 任务已成功完成，跳过重试: task_id=%s", task_id)
            return {"status": "success", "file_path": task.file_path, "idempotent": True}

        # 更新为运行中状态
        if task.status != "RUNNING":
            task.status = "RUNNING"
            task.started_at = datetime.now(timezone.utc)
        task.retry_count = (task.retry_count or 0) + 1
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
        task.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("PDF 导出任务成功: task_id=%s", task_id)
        return {"status": "success", "file_path": file_path}

    except Exception as e:
        logger.error("PDF 导出任务失败: %s\n%s", task_id, traceback.format_exc())

        task_obj = db.query(ExportTask).filter(ExportTask.id == task_id).first()
        if task_obj and task_obj.status != "FAILED":
            task_obj.status = "FAILED"
            task_obj.error_message = str(e)
            task_obj.completed_at = datetime.now(timezone.utc)
            db.commit()

        current_retries = task_obj.retry_count if task_obj else 0
        if current_retries < 3:
            countdown = 60 * (3 ** current_retries)
            logger.warning(
                "PDF 导出任务即将重试 (%d/3): task_id=%s, countdown=%ds",
                current_retries + 1, task_id, countdown,
            )
            raise self.retry(exc=e, countdown=countdown, max_retries=3)
        else:
            logger.error(
                "PDF 导出任务最终失败（已达最大重试次数）: task_id=%s, error=%s",
                task_id, e,
            )
            raise

    finally:
        db.close()


# ===== Celery 任务注册 =====
# 使用 ExportTaskBase 基类，自动获得 on_success / on_failure 回调
# 采用 bind=True 并通过 run 方法委托到 _impl 函数

@celery_app.task(bind=True, base=ExportTaskBase, max_retries=3, default_retry_delay=60)
def export_excel_async(self, task_id: str, data_source_id: int, sql: str, user_id: int):
    """异步导出 Excel 任务（带自动重试，指数退避）"""
    return _export_excel_impl(self, task_id, data_source_id, sql, user_id)


@celery_app.task(bind=True, base=ExportTaskBase, max_retries=3, default_retry_delay=60)
def export_pdf_async(self, task_id: str, data_source_id: int, sql: str, user_id: int):
    """异步导出 PDF 任务（带自动重试，指数退避）"""
    return _export_pdf_impl(self, task_id, data_source_id, sql, user_id)
