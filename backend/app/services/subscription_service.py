"""查询结果订阅推送服务

管理订阅的创建、查询、启停和手动触发
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from croniter import croniter
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from app.models.subscription import QuerySubscription, SubscriptionExecution
from app.models.template import Template
from app.repositories.semantic_metric_repository import SemanticMetricRepository

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──

    def create(
        self,
        user_id: int,
        template_id: int | None,
        cron_expression: str,
        notify_channel: str = "feishu",
        semantic_metric_key: str | None = None,
        semantic_query: dict | None = None,
    ) -> QuerySubscription:
        """创建订阅"""
        # validate cron
        self._validate_cron(cron_expression)

        if not template_id and not semantic_metric_key:
            raise ValueError("模板订阅和语义指标订阅至少选择一种")

        if template_id:
            template = self.db.query(Template).filter(Template.id == template_id).first()
            if not template:
                raise ValueError("模板不存在")

        if semantic_metric_key:
            metric = SemanticMetricRepository(self.db).get_visible_by_key(
                semantic_metric_key,
                user_id=user_id,
                is_admin=False,
                active_only=True,
            )
            if not metric:
                raise ValueError(f"语义指标不存在或不可访问: {semantic_metric_key}")

        if notify_channel not in ("feishu", "email"):
            raise ValueError(f"不支持的通知渠道: {notify_channel}")

        sub = QuerySubscription(
            user_id=user_id,
            template_id=template_id,
            semantic_metric_key=semantic_metric_key,
            semantic_query=semantic_query or {},
            cron_expression=cron_expression,
            notify_channel=notify_channel,
            is_active=True,
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        # Eagerly load template for to_dict()
        self.db.refresh(sub, ["template"])
        logger.info("订阅已创建: id=%d, user_id=%d, template_id=%s, metric=%s", sub.id, user_id, template_id, semantic_metric_key)
        return sub

    def get(self, subscription_id: int) -> Optional[QuerySubscription]:
        return (
            self.db.query(QuerySubscription)
            .options(joinedload(QuerySubscription.template))
            .filter(QuerySubscription.id == subscription_id)
            .first()
        )

    def list_subscriptions(
        self,
        user_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[QuerySubscription]:
        q = self.db.query(QuerySubscription).options(joinedload(QuerySubscription.template))
        if user_id is not None:
            q = q.filter(QuerySubscription.user_id == user_id)
        return q.order_by(desc(QuerySubscription.created_at)).offset(offset).limit(limit).all()

    def update(self, subscription_id: int, **kwargs) -> Optional[QuerySubscription]:
        sub = self.get(subscription_id)
        if not sub:
            return None
        semantic_metric_key = kwargs.get("semantic_metric_key", sub.semantic_metric_key)
        if semantic_metric_key:
            metric = SemanticMetricRepository(self.db).get_visible_by_key(
                semantic_metric_key,
                user_id=sub.user_id,
                is_admin=False,
                active_only=True,
            )
            if not metric:
                raise ValueError(f"语义指标不存在或不可访问: {semantic_metric_key}")
        for key, value in kwargs.items():
            if hasattr(sub, key) and value is not None:
                setattr(sub, key, value)
        if "cron_expression" in kwargs and kwargs["cron_expression"]:
            self._validate_cron(kwargs["cron_expression"])
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def delete(self, subscription_id: int) -> bool:
        sub = self.get(subscription_id)
        if not sub:
            return False
        self.db.delete(sub)
        self.db.commit()
        return True

    def toggle_active(self, subscription_id: int, is_active: bool) -> Optional[QuerySubscription]:
        sub = self.get(subscription_id)
        if not sub:
            return None
        sub.is_active = is_active
        self.db.commit()
        self.db.refresh(sub)
        return sub

    # ── Execution records ──

    def create_execution(self, subscription_id: int) -> SubscriptionExecution:
        exec_rec = SubscriptionExecution(subscription_id=subscription_id, status="pending")
        self.db.add(exec_rec)
        self.db.commit()
        self.db.refresh(exec_rec)
        return exec_rec

    def update_execution(self, execution_id: int, **kwargs) -> Optional[SubscriptionExecution]:
        rec = (
            self.db.query(SubscriptionExecution)
            .filter(SubscriptionExecution.id == execution_id)
            .first()
        )
        if not rec:
            return None
        for key, value in kwargs.items():
            if hasattr(rec, key):
                setattr(rec, key, value)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def get_executions(
        self, subscription_id: int, offset: int = 0, limit: int = 20
    ) -> List[SubscriptionExecution]:
        return (
            self.db.query(SubscriptionExecution)
            .filter(SubscriptionExecution.subscription_id == subscription_id)
            .order_by(desc(SubscriptionExecution.executed_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_last_run(self, subscription_id: int) -> None:
        sub = self.get(subscription_id)
        if sub:
            sub.last_run_at = _utc_now_naive()
            self.db.commit()

    # ── scheduling helpers ──

    def get_active_subscriptions_due(self) -> List[QuerySubscription]:
        """获取所有活跃且需要执行的订阅（用于 beat 调度）"""
        return (
            self.db.query(QuerySubscription)
            .filter(QuerySubscription.is_active == True)
            .all()
        )

    # ── internal ──

    @staticmethod
    def _validate_cron(expression: str):
        try:
            croniter(expression)
        except Exception as e:
            raise ValueError(f"无效的 cron 表达式 '{expression}': {e}")

    @staticmethod
    def next_run_time(cron_expression: str) -> Optional[str]:
        try:
            cron = croniter(cron_expression, _utc_now_naive())
            next_time = cron.get_next(datetime)
            return next_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
