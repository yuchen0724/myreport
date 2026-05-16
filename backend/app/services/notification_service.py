# backend/app/services/notification_service.py
"""
告警通知服务 —— Celery 任务失败时统一记录告警，支持前端轮询查询。

职责：
1. 记录任务失败告警到 task_alerts 表
2. 提供查询接口（按用户/任务类型/状态过滤）
3. 标记已读
"""
import logging
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.task_alert import TaskAlert

logger = logging.getLogger(__name__)


class NotificationService:
    """告警通知服务"""

    def __init__(self, db: Session):
        self.db = db

    def create_alert(
        self,
        task_id: str,
        task_type: str,
        error_message: str,
        alert_message: str,
        user_id: Optional[int] = None,
    ) -> TaskAlert:
        """记录一条任务失败告警

        Args:
            task_id: Celery 任务 ID
            task_type: 任务类型 (export_excel, export_pdf, train_predict, etc.)
            error_message: 错误详情
            alert_message: 告警摘要（前端展示用）
            user_id: 关联用户 ID
        """
        alert = TaskAlert(
            task_id=task_id,
            user_id=user_id,
            task_type=task_type,
            status="unread",
            error_message=error_message,
            alert_message=alert_message,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        logger.warning(
            "任务失败告警已记录: task_id=%s, task_type=%s, user_id=%s, alert_id=%d",
            task_id, task_type, user_id, alert.id,
        )
        return alert

    def get_alerts(
        self,
        user_id: Optional[int] = None,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskAlert]:
        """查询告警列表，按创建时间降序"""
        query = self.db.query(TaskAlert)

        if user_id is not None:
            query = query.filter(TaskAlert.user_id == user_id)
        if task_type:
            query = query.filter(TaskAlert.task_type == task_type)
        if status:
            query = query.filter(TaskAlert.status == status)

        return (
            query
            .order_by(desc(TaskAlert.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_unread_count(self, user_id: Optional[int] = None) -> int:
        """获取未读告警数量"""
        query = self.db.query(TaskAlert).filter(TaskAlert.status == "unread")
        if user_id is not None:
            query = query.filter(TaskAlert.user_id == user_id)
        return query.count()

    def mark_as_read(self, alert_id: int, user_id: Optional[int] = None) -> bool:
        """将告警标记为已读"""
        query = self.db.query(TaskAlert).filter(TaskAlert.id == alert_id)
        if user_id is not None:
            query = query.filter(TaskAlert.user_id == user_id)
        alert = query.first()
        if not alert:
            return False
        alert.status = "read"
        alert.read_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def mark_all_as_read(self, user_id: Optional[int] = None) -> int:
        """将所有未读告警标记为已读，返回更新的记录数"""
        query = self.db.query(TaskAlert).filter(TaskAlert.status == "unread")
        if user_id is not None:
            query = query.filter(TaskAlert.user_id == user_id)
        count = query.count()
        now = datetime.now(timezone.utc)
        query.update({"status": "read", "read_at": now})
        self.db.commit()
        return count
