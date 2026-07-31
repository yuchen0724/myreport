"""Celery tasks for generating and delivering scheduled reports."""

import json
import logging
import os
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.redis import get_redis
from app.models.scheduled_report import ReportDelivery, ScheduledReport
from app.models.template import Template
from app.models.user import User
from app.schemas.report import ExcelExportRequest, PDFExportRequest
from app.services.report_delivery_service import ReportDeliveryService
from app.services.report_service import ReportService
from app.services.scheduled_report_service import ScheduledReportService

logger = logging.getLogger(__name__)
EXPORT_DIR = os.getenv("EXPORT_DIR", "/tmp/exports")


def _recipient_emails(db, recipients: list[dict]) -> list[str]:
    emails = {item.get("email", "").strip() for item in recipients if item.get("email")}
    user_ids = {item.get("user_id") for item in recipients if item.get("user_id")}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids), User.is_active == True).all()
        emails.update(user.email.strip() for user in users if user.email)
    return sorted(email for email in emails if email)


def _execute_scheduled_report_impl(report_id: int, force: bool = False) -> dict:
    db = SessionLocal()
    delivery = None
    try:
        report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
        if not report:
            return {"status": "error", "message": f"定时报表不存在: {report_id}"}
        if not report.enabled and not force:
            return {"status": "skipped", "message": "定时报表已禁用"}

        delivery = ReportDelivery(scheduled_report_id=report.id, status="pending")
        db.add(delivery)
        db.commit()
        db.refresh(delivery)

        template = db.query(Template).filter(Template.id == report.template_id).first()
        if not template:
            raise ValueError(f"模板不存在: {report.template_id}")
        try:
            config = json.loads(template.config) if isinstance(template.config, str) else template.config
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("模板配置不是有效 JSON") from exc

        data_source_id = report.data_source_id or config.get("data_source_id") or config.get("dataSourceId")
        sql = config.get("sql") or config.get("query")
        if not data_source_id or not sql:
            raise ValueError("模板配置缺少 data_source_id 或 SQL")

        os.makedirs(EXPORT_DIR, exist_ok=True)
        extension = "pdf" if report.output_format == "pdf" else "xlsx"
        file_name = f"scheduled_report_{report.id}_{delivery.id}.{extension}"
        file_path = os.path.join(EXPORT_DIR, file_name)
        request_type = PDFExportRequest if report.output_format == "pdf" else ExcelExportRequest
        request = request_type(
            data_source_id=data_source_id,
            sql=sql,
            params=report.parameters or {},
            filename=file_name,
        )
        service = ReportService(db)
        buffer = service.generate_pdf(request, report.created_by) if report.output_format == "pdf" else service.generate_excel(request, report.created_by)
        with open(file_path, "wb") as file:
            file.write(buffer.getvalue())

        emails = _recipient_emails(db, report.recipients or [])
        if emails:
            ReportDeliveryService().send_email(
                emails,
                subject=report.name,
                body=f"定时报表 {report.name} 已生成，请查收附件。",
                attachment_path=file_path,
                attachment_name=file_name,
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        delivery.status = "success"
        delivery.file_path = file_path
        delivery.file_name = file_name
        delivery.delivered_at = now if emails else None
        report.last_run_at = now
        db.commit()
        return {
            "status": "success",
            "delivery_id": delivery.id,
            "file_path": file_path,
            "recipients": len(emails),
        }
    except Exception as exc:
        logger.exception("定时报表执行失败: report_id=%d", report_id)
        if delivery:
            delivery.status = "failed"
            delivery.error_message = str(exc)[:1000]
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def execute_scheduled_report_task(self, report_id: int, force: bool = False):
    try:
        result = _execute_scheduled_report_impl(report_id, force)
        if result.get("status") == "error":
            raise RuntimeError(result.get("message") or "定时报表执行失败")
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="app.tasks.scheduled_report_tasks.dispatch_scheduled_reports")
def dispatch_scheduled_reports():
    db = SessionLocal()
    try:
        service = ScheduledReportService(db)
        reports = service.get_enabled_with_next()
        dispatched = 0
        redis = get_redis()
        for report in reports:
            scheduled_at = report.next_run_at or datetime.now(timezone.utc).replace(tzinfo=None)
            lock_key = f"scheduled_report:{report.id}:{int(scheduled_at.timestamp())}"
            try:
                acquired = bool(redis.set(lock_key, "1", nx=True, ex=300))
            except Exception:
                logger.exception("定时报表调度锁不可用: report_id=%d", report.id)
                acquired = True
            if not acquired:
                continue
            try:
                execute_scheduled_report_task.delay(report.id, False)
                service.mark_dispatched(report.id)
                dispatched += 1
            except Exception:
                try:
                    redis.delete(lock_key)
                except Exception:
                    pass
                logger.exception("定时报表入队失败: report_id=%d", report.id)
        return {"due": len(reports), "dispatched": dispatched}
    finally:
        db.close()
