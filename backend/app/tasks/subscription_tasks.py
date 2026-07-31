"""查询结果订阅推送 - Celery 定时任务"""
import logging
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.subscription import QuerySubscription, SubscriptionExecution
from app.models.template import Template
from app.models.user import User
from app.schemas.semantic_metric import SemanticMetricQueryRequest
from app.services.query_service import QueryService
from app.services.semantic_metric_query_service import SemanticMetricQueryService
from app.services.notification_service import NotificationService
from app.services.report_delivery_service import ReportDeliveryService
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


def _send_feishu_notification(user_id: int, template_name: str, result_summary: str):
    """通过配置的飞书机器人 Webhook 发送通知。"""
    ReportDeliveryService().send_feishu_text(template_name, result_summary)


def _send_email_notification(db, user_id: int, template_name: str, result_summary: str):
    """发送邮件通知"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.email:
        raise RuntimeError("订阅用户未配置邮箱")
    ReportDeliveryService().send_email(
        [user.email],
        subject=template_name,
        body=result_summary,
    )


def _execute_subscription_impl(subscription_id: int) -> dict:
    """
    订阅执行内部实现（抽取为普通函数，方便测试）。
    1. 查询模板配置
    2. 执行模板对应的 SQL 查询
    3. 根据 notify_channel 推送结果
    4. 记录执行日志
    """
    db = SessionLocal()
    try:
        sub = db.query(QuerySubscription).filter(QuerySubscription.id == subscription_id).first()
        if not sub:
            return {"status": "error", "message": f"订阅不存在: {subscription_id}"}

        if not sub.is_active:
            return {"status": "skipped", "message": "订阅已禁用"}

        # create execution record
        exec_rec = SubscriptionExecution(subscription_id=subscription_id, status="pending")
        db.add(exec_rec)
        db.commit()
        db.refresh(exec_rec)

        try:
            template_name, result_summary = _execute_subscription_query(db, sub)
        except Exception as query_err:
            exec_rec.status = "failed"
            exec_rec.error_message = f"查询执行失败: {str(query_err)[:500]}"
            db.commit()
            return {"status": "error", "message": exec_rec.error_message}

        # send notification based on channel
        try:
            if sub.notify_channel == "feishu":
                _send_feishu_notification(sub.user_id, template_name, result_summary)
            elif sub.notify_channel == "email":
                _send_email_notification(db, sub.user_id, template_name, result_summary)
            else:
                raise ValueError(f"未知通知渠道: {sub.notify_channel}")
        except Exception as notif_err:
            logger.error("通知发送失败: %s", notif_err)
            exec_rec.status = "failed"
            exec_rec.error_message = f"通知发送失败: {str(notif_err)[:500]}"
            db.commit()
            try:
                NotificationService(db).create_alert(
                    task_id=f"subscription:{subscription_id}:{exec_rec.id}",
                    task_type="subscription",
                    error_message=str(notif_err),
                    alert_message=exec_rec.error_message,
                    user_id=sub.user_id,
                )
            except Exception:
                logger.exception("订阅失败告警记录失败")
            return {"status": "error", "message": exec_rec.error_message}

        # update execution record
        exec_rec.status = "success"
        exec_rec.result_summary = result_summary
        db.commit()

        # update subscription last_run_at
        sub.last_run_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("订阅执行成功: subscription_id=%d, exec_id=%d", subscription_id, exec_rec.id)
        return {"status": "success", "result_summary": result_summary, "execution_id": exec_rec.id}

    except Exception as e:
        logger.error("订阅执行异常: subscription_id=%d, error=%s\n%s", subscription_id, e, traceback.format_exc())
        return {"status": "error", "message": str(e)[:500]}
    finally:
        db.close()


def _execute_subscription_query(db, sub: QuerySubscription) -> tuple[str, str]:
    if sub.subscription_type == "briefing":
        from app.services.business_briefing_service import BusinessBriefingService

        title, summary, _ = BusinessBriefingService(db).generate(
            sub.briefing_config or {}, user_id=int(sub.user_id)
        )
        return title, summary

    if sub.semantic_metric_key:
        query_config = sub.semantic_query or {}
        metric, result = SemanticMetricQueryService(db).execute(
            SemanticMetricQueryRequest(
                metric_key=sub.semantic_metric_key,
                start_time=query_config.get("start_time"),
                end_time=query_config.get("end_time"),
                dimensions=query_config.get("dimensions") or [],
                filters=query_config.get("filters") or {},
                page=1,
                page_size=query_config.get("page_size", 1000),
            ),
            user_id=int(sub.user_id),
            is_admin=False,
        )
        return metric.name, f"语义指标查询完成: {metric.name}, {result.total} 行数据, {result.execution_time_ms}ms"

    template = db.query(Template).filter(Template.id == sub.template_id).first()
    if not template:
        raise ValueError(f"模板不存在: {sub.template_id}")

    import json
    try:
        config = json.loads(template.config) if isinstance(template.config, str) else template.config
    except (json.JSONDecodeError, TypeError):
        config = {}

    data_source_id = config.get("data_source_id") or config.get("dataSourceId")
    sql = config.get("sql") or config.get("query")
    if not sql:
        raise ValueError("模板配置中缺少 SQL 查询")
    if not data_source_id:
        raise ValueError("模板配置中缺少 data_source_id")

    from app.schemas.query import SQLQueryRequest
    query_service = QueryService(db)
    request = SQLQueryRequest(
        data_source_id=data_source_id,
        sql=sql,
        page=1,
        page_size=1,
    )
    result = query_service.execute_sql(request, int(sub.user_id))
    return template.name, f"查询完成: {result.total} 行数据, {result.execution_time_ms}ms"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def execute_subscription_task(self, subscription_id: int):
    """执行单个订阅推送任务"""
    try:
        result = _execute_subscription_impl(subscription_id)
        if result.get("status") == "error":
            raise RuntimeError(result.get("message") or "订阅执行失败")
        return result
    except Exception as exc:
        logger.error("订阅任务失败 (will retry): subscription_id=%d, error=%s", subscription_id, exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(name="app.tasks.subscription_tasks.run_all_subscriptions")
def run_all_subscriptions():
    """
    Beat 定时调度入口：遍历所有活跃订阅，按 cron 表达式判断是否需要执行。
    注意：celery beat 本身的 schedule 是全局固定的，这里通过 croniter 判断每个
    订阅是否到了执行时间。
    """
    from croniter import croniter

    db = SessionLocal()
    try:
        subs = db.query(QuerySubscription).filter(QuerySubscription.is_active == True).all()
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        triggered = 0

        for sub in subs:
            try:
                cron = croniter(sub.cron_expression, now)
                prev_run = cron.get_prev(datetime)
                diff = (now - prev_run).total_seconds()
                if not 0 <= diff < 90:
                    continue

                if sub.last_run_at:
                    last_run = sub.last_run_at
                    if last_run.tzinfo is None:
                        last_run = last_run.replace(tzinfo=timezone.utc)
                    if last_run.timestamp() >= prev_run.timestamp():
                        continue

                lock_key = f"subscription_schedule:{sub.id}:{int(prev_run.timestamp())}"
                redis = get_redis()
                try:
                    acquired = bool(redis.set(lock_key, "1", nx=True, ex=300))
                except Exception:
                    logger.exception("订阅调度锁不可用: subscription_id=%d", sub.id)
                    acquired = True
                if not acquired:
                    continue
                try:
                    execute_subscription_task.delay(sub.id)
                    triggered += 1
                except Exception:
                    try:
                        redis.delete(lock_key)
                    except Exception:
                        pass
                    raise
            except Exception as cron_err:
                logger.warning("Cron 解析失败: subscription_id=%d, cron=%s, error=%s",
                               sub.id, sub.cron_expression, cron_err)

        logger.info("订阅调度完成: 活跃 %d, 触发 %d", len(subs), triggered)
        return {"total_active": len(subs), "triggered": triggered}
    finally:
        db.close()
