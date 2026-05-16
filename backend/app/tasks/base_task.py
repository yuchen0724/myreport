# backend/app/tasks/base_task.py
"""
Celery 任务基类 — 统一处理任务失败告警、自动重试和状态回调。

功能：
1. 自动重试（指数退避）：max_retries=3, default_retry_delay=60
2. 失败告警：记录到数据库 ExportTask 并写日志
3. 成功/失败回调：更新 ExportTask 状态（status / error_message / retry_count / completed_at）
"""

import logging
import traceback
from typing import Any, Dict, Optional

from celery import Task
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.export_task import ExportTask
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ExportTaskBase(Task):
    """
    导出任务的 Celery 基类。

    子类通过 @celery_app.task(bind=True, base=ExportTaskBase) 注册即可自动获得：
    - on_success: 更新任务为 SUCCESS
    - on_failure: 更新任务为 FAILED，记录错误信息，自动重试（指数退避）
    - 重试幂等：重试时不会重复将任务标记为 FAILED
    """

    # 默认重试配置（子类可覆盖）
    max_retries = 3
    default_retry_delay = 60  # 首次重试延迟（秒）
    autoretry_for = (Exception,)

    def _get_task_id_from_request(self) -> str:
        """从任务参数中提取 task_id（第一个位置参数）"""
        if self.request and self.request.args and len(self.request.args) > 0:
            return str(self.request.args[0])
        return ""

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """任务成功回调 — 更新数据库状态为 SUCCESS"""
        db = SessionLocal()
        try:
            task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
            if task and task.status != "SUCCESS":
                task.status = "SUCCESS"
                task.completed_at = datetime.now(timezone.utc)
                db.commit()
                logger.info("导出任务成功: task_id=%s", task_id)
        except Exception as e:
            logger.error("更新任务成功状态失败: task_id=%s, error=%s", task_id, e)
        finally:
            db.close()
        super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict,
                   einfo: Any) -> None:
        """任务失败回调 — 记录错误、告警日志、自动重试（指数退避）"""
        real_task_id = self._get_task_id_from_request() or task_id

        db = SessionLocal()
        try:
            task = db.query(ExportTask).filter(ExportTask.id == real_task_id).first()
            if task:
                # 只有当任务还不是 FAILED 状态时才更新（避免重复写）
                if task.status != "FAILED":
                    task.status = "FAILED"
                    task.error_message = str(exc)
                    task.completed_at = datetime.now(timezone.utc)
                    db.commit()

                # 记录当前重试次数
                retry_count = task.retry_count or 0

                # 检查是否还有重试机会
                if retry_count < self.max_retries:
                    # 指数退避：60s, 180s, 540s
                    countdown = self.default_retry_delay * (3 ** retry_count)
                    logger.warning(
                        "导出任务失败，即将重试 (%d/%d): task_id=%s, countdown=%ds, error=%s",
                        retry_count + 1, self.max_retries, real_task_id, countdown, exc,
                    )
                    # 关闭数据库会话后再抛出 retry（避免 conn 泄漏）
                    db.close()
                    db = None
                    raise self.retry(exc=exc, countdown=countdown, max_retries=self.max_retries)
                else:
                    # 已达最大重试次数，发出最终告警
                    logger.error(
                        "导出任务最终失败（已达最大重试次数 %d）: task_id=%s, error=%s\n%s",
                        self.max_retries, real_task_id, exc, traceback.format_exc(),
                    )
                    # 记录告警到数据库
                    try:
                        notif = NotificationService(db)
                        notif.create_alert(
                            task_id=real_task_id,
                            task_type="export",
                            error_message=str(exc),
                            alert_message=f"导出任务最终失败（重试{self.max_retries}次后）: {str(exc)[:200]}",
                            user_id=task.user_id,
                        )
                    except Exception as alert_e:
                        logger.error("记录告���失败: task_id=%s, error=%s", real_task_id, alert_e)
            else:
                logger.error("导出任务失败，任务记录不存在: task_id=%s, error=%s", real_task_id, exc)
        except Exception as retry_exc:
            # self.retry() 会抛出 celery.exceptions.Retry，需要重新抛出
            # 不能在这里用 isinstance 检查 self.retry 的返回类型，因为 self.retry 是方法
            # 直接重新抛出，让 Celery 框架处理
            raise
        finally:
            if db is not None:
                db.close()

        super().on_failure(exc, task_id, args, kwargs, einfo=einfo)

    def after_return(self, status: str, retval: Any, task_id: str,
                     args: tuple, kwargs: dict, einfo: Any) -> None:
        """任务返回后清理"""
        # 如果任务最终成功但状态未被标记（某些边缘情况），不做额外处理
        super().after_return(status, retval, task_id, args, kwargs, einfo)

    def update_task_retry_count(self, task_id: str, retry_count: int) -> None:
        """更新任务重试次数到数据库（幂等安全）"""
        db = SessionLocal()
        try:
            task = db.query(ExportTask).filter(ExportTask.id == task_id).first()
            if task:
                task.retry_count = retry_count
                db.commit()
        except Exception as e:
            logger.error("更新重试次数失败: task_id=%s, error=%s", task_id, e)
        finally:
            db.close()
