"""定时报表服务

管理定时报表的创建、查询、启停和调度
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy.orm import Session

from app.models.scheduled_report import ScheduledReport, ReportDelivery
from app.services.data_source_service import DataSourceService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ScheduledReportService:
    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──

    def create(
        self,
        name: str,
        cron_expression: str,
        template_id: int,
        data_source_id: Optional[int],
        parameters: dict,
        output_format: str,
        recipients: list,
        created_by: int,
    ) -> ScheduledReport:
        """创建定时报表"""
        self._validate_cron(cron_expression)
        TemplateService(self.db).require_view_access(template_id, created_by)
        if data_source_id is not None:
            DataSourceService(self.db).require_access(data_source_id, created_by)
        if output_format not in ("excel", "pdf"):
            raise ValueError("output_format 必须是 excel 或 pdf")

        report = ScheduledReport(
            name=name,
            cron_expression=cron_expression,
            template_id=template_id,
            data_source_id=data_source_id,
            parameters=parameters,
            output_format=output_format,
            recipients=recipients,
            created_by=created_by,
            enabled=True,
        )
        self._update_next_run(report)
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def _get(self, report_id: int) -> Optional[ScheduledReport]:
        return self.db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()

    def get(self, report_id: int, user_id: int) -> Optional[ScheduledReport]:
        return self.db.query(ScheduledReport).filter(
            ScheduledReport.id == report_id,
            ScheduledReport.created_by == user_id,
        ).first()

    def list_reports(self, user_id: int, offset: int = 0, limit: int = 20) -> List[ScheduledReport]:
        return (
            self.db.query(ScheduledReport)
            .filter(ScheduledReport.created_by == user_id)
            .order_by(ScheduledReport.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update(self, report_id: int, user_id: int, **kwargs) -> Optional[ScheduledReport]:
        report = self.get(report_id, user_id)
        if not report:
            return None
        if "template_id" in kwargs:
            TemplateService(self.db).require_view_access(kwargs["template_id"], user_id)
        if kwargs.get("data_source_id") is not None:
            DataSourceService(self.db).require_access(kwargs["data_source_id"], user_id)
        if "output_format" in kwargs and kwargs["output_format"] not in ("excel", "pdf"):
            raise ValueError("output_format 必须是 excel 或 pdf")
        for key, value in kwargs.items():
            if hasattr(report, key):
                setattr(report, key, value)
        if "cron_expression" in kwargs:
            self._validate_cron(kwargs["cron_expression"])
            self._update_next_run(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def delete(self, report_id: int, user_id: int) -> bool:
        report = self.get(report_id, user_id)
        if not report:
            return False
        self.db.delete(report)
        self.db.commit()
        return True

    def toggle_enabled(self, report_id: int, user_id: int, enabled: bool) -> Optional[ScheduledReport]:
        report = self.get(report_id, user_id)
        if not report:
            return None
        report.enabled = enabled
        if enabled:
            self._update_next_run(report)
        else:
            report.next_run_at = None
        self.db.commit()
        self.db.refresh(report)
        return report

    # ── 投递记录 ──

    def get_deliveries(
        self, report_id: int, user_id: int, offset: int = 0, limit: int = 20
    ) -> List[ReportDelivery]:
        if not self.get(report_id, user_id):
            return []
        return (
            self.db.query(ReportDelivery)
            .filter(ReportDelivery.scheduled_report_id == report_id)
            .order_by(ReportDelivery.generated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def create_delivery(self, report_id: int) -> ReportDelivery:
        delivery = ReportDelivery(scheduled_report_id=report_id, status="pending")
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    def update_delivery(self, delivery_id: int, **kwargs) -> Optional[ReportDelivery]:
        delivery = self.db.query(ReportDelivery).filter(ReportDelivery.id == delivery_id).first()
        if not delivery:
            return None
        for key, value in kwargs.items():
            if hasattr(delivery, key):
                setattr(delivery, key, value)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    # ── 调度 ──

    def get_enabled_with_next(self) -> List[ScheduledReport]:
        """获取所有启用且需要执行的定时报表"""
        now = _utc_now_naive()
        return (
            self.db.query(ScheduledReport)
            .filter(
                ScheduledReport.enabled == True,
                ScheduledReport.next_run_at <= now,
            )
            .order_by(ScheduledReport.next_run_at)
            .all()
        )

    def schedule_next_run(self, report_id: int, user_id: int) -> Optional[ScheduledReport]:
        """兼容旧调用：仅重新计算下一次计划时间。"""
        report = self.get(report_id, user_id)
        if not report:
            return None
        self._update_next_run(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def mark_dispatched(self, report_id: int) -> Optional[ScheduledReport]:
        """任务成功进入队列后推进下一次计划时间。"""
        report = self._get(report_id)
        if not report:
            return None
        self._update_next_run(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    # ── 内部方法 ──

    @staticmethod
    def _validate_cron(expression: str):
        try:
            croniter(expression)
        except Exception as e:
            raise ValueError(f"无效的 cron 表达式 '{expression}': {e}")

    @staticmethod
    def _update_next_run(report: ScheduledReport):
        try:
            local_now = datetime.now(ZoneInfo("Asia/Shanghai"))
            cron = croniter(report.cron_expression, local_now)
            next_local = cron.get_next(datetime)
            report.next_run_at = next_local.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass

    @staticmethod
    def next_run_time(cron_expression: str) -> Optional[str]:
        """计算 cron 表达式的下次执行时间"""
        try:
            cron = croniter(cron_expression, datetime.now(ZoneInfo("Asia/Shanghai")))
            next_time = cron.get_next(datetime)
            return next_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
