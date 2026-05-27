"""查询结果订阅推送服务

管理订阅的创建、查询、启停和手动触发
"""
import logging
from datetime import datetime
from typing import List, Optional

from croniter import croniter
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from app.models.subscription import QuerySubscription, SubscriptionExecution
from app.models.template import Template

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──

    def create(
        self,
        user_id: int,
        template_id: int,
        cron_expression: str,
        notify_channel: str = "feishu",
    ) -> QuerySubscription:
        """创建订阅"""
        # validate cron
        self._validate_cron(cron_expression)

        # validate template exists
        template = self.db.query(Template).filter(Template.id == template_id).first()
        if not template:
            raise ValueError("模板不存在")

        if notify_channel not in ("feishu", "email"):
            raise ValueError(f"不支持的通知渠道: {notify_channel}")

        sub = QuerySubscription(
            user_id=user_id,
            template_id=template_id,
            cron_expression=cron_expression,
            notify_channel=notify_channel,
            is_active=True,
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        # Eagerly load template for to_dict()
        self.db.refresh(sub, ["template"])
        logger.info("订阅已创建: id=%d, user_id=%d, template_id=%d", sub.id, user_id, template_id)
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
            sub.last_run_at = datetime.utcnow()
            self.db.commit()

    # ── scheduling helpers ──

    def get_active_subscriptions_due(self) -> List[QuerySubscription]:
        """获取所有活跃且需要执行的订阅（用于 beat 调度）"""
        now = datetime.utcnow()
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
            cron = croniter(cron_expression, datetime.utcnow())
            next_time = cron.get_next(datetime)
            return next_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
