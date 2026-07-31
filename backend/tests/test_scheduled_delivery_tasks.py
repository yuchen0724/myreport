from io import BytesIO
from unittest.mock import MagicMock, patch

from app.models.data_source import DataSource
from app.models.scheduled_report import ReportDelivery, ScheduledReport
from app.models.subscription import QuerySubscription, SubscriptionExecution
from app.models.template import Template
from app.schemas.query import SQLQueryResponse
from app.tasks.scheduled_report_tasks import _execute_scheduled_report_impl
from app.tasks.subscription_tasks import _execute_subscription_impl, _execute_subscription_query


class _NonClosingSession:
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        return None


def test_template_subscription_uses_valid_minimal_page_size(db_session, test_user):
    template = Template(
        name="订阅模板",
        config='{"data_source_id": 1, "sql": "SELECT id FROM orders ORDER BY id"}',
        created_by=test_user.id,
        is_public=False,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    subscription = MagicMock(
        subscription_type="query",
        semantic_metric_key=None,
        template_id=template.id,
        user_id=test_user.id,
    )
    captured = {}

    class _QueryService:
        def __init__(self, db):
            self.db = db

        def execute_sql(self, request, user_id):
            captured["request"] = request
            return SQLQueryResponse(
                columns=["id"],
                rows=[[1]],
                total=20,
                page=request.page,
                page_size=request.page_size,
                execution_time_ms=1,
            )

    with patch("app.tasks.subscription_tasks.QueryService", _QueryService):
        _, summary = _execute_subscription_query(db_session, subscription)

    assert captured["request"].page_size == 1
    assert "20 行" in summary


def test_subscription_delivery_failure_is_not_marked_success(db_session, test_user):
    subscription = QuerySubscription(
        user_id=test_user.id,
        template_id=None,
        semantic_metric_key="gmv",
        semantic_query={},
        cron_expression="0 8 * * *",
        notify_channel="feishu",
        is_active=True,
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)

    with (
        patch(
            "app.tasks.subscription_tasks.SessionLocal",
            return_value=_NonClosingSession(db_session),
        ),
        patch(
            "app.tasks.subscription_tasks._execute_subscription_query",
            return_value=("GMV", "查询完成"),
        ),
        patch(
            "app.tasks.subscription_tasks._send_feishu_notification",
            side_effect=RuntimeError("webhook unavailable"),
        ),
        patch("app.tasks.subscription_tasks.NotificationService.create_alert"),
    ):
        result = _execute_subscription_impl(subscription.id)

    execution = db_session.query(SubscriptionExecution).filter(
        SubscriptionExecution.subscription_id == subscription.id
    ).one()
    assert result["status"] == "error"
    assert execution.status == "failed"
    assert "通知发送失败" in execution.error_message


def test_celery_beat_contains_report_dispatchers():
    from app.celery_app import celery_app

    assert set(celery_app.conf.beat_schedule) >= {
        "dispatch-query-subscriptions",
        "dispatch-scheduled-reports",
    }


def test_scheduled_report_generates_file_and_sends_email(
    db_session, test_user, tmp_path
):
    data_source = DataSource(
        name="定时报表数据源",
        type="MYSQL",
        host="localhost",
        port=3306,
        database="reporting",
        username="report_user",
        password_encrypted="encrypted",
        created_by=test_user.id,
        is_active=True,
    )
    db_session.add(data_source)
    db_session.flush()
    template = Template(
        name="定时报表模板",
        config=(
            '{"data_source_id": %d, "sql": '
            '"SELECT id FROM orders ORDER BY id"}' % data_source.id
        ),
        created_by=test_user.id,
        is_public=False,
    )
    db_session.add(template)
    db_session.flush()
    report = ScheduledReport(
        name="每日经营报表",
        cron_expression="0 8 * * *",
        template_id=template.id,
        output_format="excel",
        recipients=[{"email": "owner@example.com"}],
        created_by=test_user.id,
        enabled=True,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    with (
        patch(
            "app.tasks.scheduled_report_tasks.SessionLocal",
            return_value=_NonClosingSession(db_session),
        ),
        patch("app.tasks.scheduled_report_tasks.EXPORT_DIR", str(tmp_path)),
        patch(
            "app.tasks.scheduled_report_tasks.ReportService.generate_excel",
            return_value=BytesIO(b"xlsx-data"),
        ),
        patch(
            "app.tasks.scheduled_report_tasks.ReportDeliveryService.send_email"
        ) as send_email,
    ):
        result = _execute_scheduled_report_impl(report.id)

    assert result["status"] == "success"
    delivery = db_session.query(ReportDelivery).filter(
        ReportDelivery.scheduled_report_id == report.id
    ).one()
    assert delivery.status == "success"
    assert (tmp_path / delivery.file_name).read_bytes() == b"xlsx-data"
    send_email.assert_called_once()


def test_run_now_enqueues_real_scheduled_task(
    client, auth_headers, db_session, test_user, test_template
):
    report = ScheduledReport(
        name="立即执行报表",
        cron_expression="0 8 * * *",
        template_id=test_template.id,
        output_format="excel",
        recipients=[],
        created_by=test_user.id,
        enabled=True,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    with patch(
        "app.tasks.scheduled_report_tasks.execute_scheduled_report_task.delay",
        return_value=MagicMock(id="scheduled-task-1"),
    ) as delay:
        response = client.post(
            f"/api/scheduled-reports/{report.id}/run-now",
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["task_id"] == "scheduled-task-1"
    delay.assert_called_once_with(report.id, True)
