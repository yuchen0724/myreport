"""测试查询结果订阅推送功能

覆盖：
1. SubscriptionService CRUD
2. Subscription API 端点
3. Celery 任务执行逻辑
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestSubscriptionService:
    """测试 SubscriptionService 核心功能"""

    def test_create_subscription(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        sub = svc.create(
            user_id=test_user.id,
            template_id=test_template.id,
            cron_expression="0 8 * * 1",
            notify_channel="feishu",
        )
        assert sub.id is not None
        assert sub.user_id == test_user.id
        assert sub.template_id == test_template.id
        assert sub.cron_expression == "0 8 * * 1"
        assert sub.notify_channel == "feishu"
        assert sub.is_active is True

    def test_create_subscription_invalid_cron(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        with pytest.raises(ValueError, match="无效的 cron"):
            svc.create(user_id=test_user.id, template_id=test_template.id, cron_expression="invalid")

    def test_create_subscription_invalid_channel(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        with pytest.raises(ValueError, match="不支持的通知渠道"):
            svc.create(
                user_id=test_user.id,
                template_id=test_template.id,
                cron_expression="0 8 * * *",
                notify_channel="sms",
            )

    def test_create_subscription_nonexistent_template(self, db_session, test_user):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        from app.exceptions import NotFoundError

        with pytest.raises(NotFoundError, match="模板不存在"):
            svc.create(user_id=test_user.id, template_id=99999, cron_expression="0 8 * * *")

    def test_get_subscription(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        sub = svc.create(
            user_id=test_user.id,
            template_id=test_template.id,
            cron_expression="0 8 * * 1",
        )
        fetched = svc.get(sub.id)
        assert fetched is not None
        assert fetched.id == sub.id

    def test_list_subscriptions(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        svc.create(user_id=test_user.id, template_id=test_template.id, cron_expression="0 8 * * 1")
        svc.create(user_id=test_user.id, template_id=test_template.id, cron_expression="0 12 * * *")

        subs = svc.list_subscriptions(user_id=test_user.id)
        assert len(subs) == 2

    def test_update_subscription(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        sub = svc.create(
            user_id=test_user.id,
            template_id=test_template.id,
            cron_expression="0 8 * * 1",
        )
        updated = svc.update(sub.id, cron_expression="0 9 * * 2", notify_channel="email")
        assert updated.cron_expression == "0 9 * * 2"
        assert updated.notify_channel == "email"

    def test_delete_subscription(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        sub = svc.create(
            user_id=test_user.id,
            template_id=test_template.id,
            cron_expression="0 8 * * 1",
        )
        assert svc.delete(sub.id) is True
        assert svc.get(sub.id) is None

    def test_delete_nonexistent(self, db_session):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        assert svc.delete(99999) is False

    def test_toggle_active(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        sub = svc.create(
            user_id=test_user.id,
            template_id=test_template.id,
            cron_expression="0 8 * * 1",
        )
        assert sub.is_active is True
        updated = svc.toggle_active(sub.id, False)
        assert updated.is_active is False

    def test_create_and_update_execution(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        sub = svc.create(
            user_id=test_user.id,
            template_id=test_template.id,
            cron_expression="0 8 * * 1",
        )
        exec_rec = svc.create_execution(sub.id)
        assert exec_rec.status == "pending"

        svc.update_execution(exec_rec.id, status="success", result_summary="OK")
        execs = svc.get_executions(sub.id)
        assert len(execs) == 1
        assert execs[0].status == "success"

    def test_next_run_time(self):
        from app.services.subscription_service import SubscriptionService

        result = SubscriptionService.next_run_time("0 8 * * *")
        assert result is not None
        assert len(result) == 19  # "YYYY-MM-DD HH:MM:SS"

    def test_next_run_time_invalid(self):
        from app.services.subscription_service import SubscriptionService

        result = SubscriptionService.next_run_time("invalid cron")
        assert result is None

    def test_to_dict(self, db_session, test_user, test_template):
        from app.services.subscription_service import SubscriptionService

        svc = SubscriptionService(db_session)
        sub = svc.create(
            user_id=test_user.id,
            template_id=test_template.id,
            cron_expression="0 8 * * 1",
        )
        d = sub.to_dict()
        assert "id" in d
        assert "cron_expression" in d
        assert "notify_channel" in d
        assert "template_name" in d
        assert "username" in d


class TestSubscriptionAPI:
    """测试 Subscription API 端点"""

    def test_create_subscription_api(self, client, auth_headers, db_session, test_user, test_template):
        resp = client.post(
            "/api/subscriptions",
            json={
                "template_id": test_template.id,
                "cron_expression": "0 8 * * 1",
                "notify_channel": "feishu",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["template_id"] == test_template.id
        assert data["cron_expression"] == "0 8 * * 1"

    def test_list_subscriptions_api(self, client, auth_headers, db_session, test_user, test_template):
        client.post(
            "/api/subscriptions",
            json={"template_id": test_template.id, "cron_expression": "0 8 * * 1"},
            headers=auth_headers,
        )
        resp = client.get("/api/subscriptions", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_subscription_api(self, client, auth_headers, db_session, test_user, test_template):
        create_resp = client.post(
            "/api/subscriptions",
            json={"template_id": test_template.id, "cron_expression": "0 8 * * 1"},
            headers=auth_headers,
        )
        sub_id = create_resp.json()["id"]
        resp = client.get(f"/api/subscriptions/{sub_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == sub_id

    def test_update_subscription_api(self, client, auth_headers, db_session, test_user, test_template):
        create_resp = client.post(
            "/api/subscriptions",
            json={"template_id": test_template.id, "cron_expression": "0 8 * * 1"},
            headers=auth_headers,
        )
        sub_id = create_resp.json()["id"]
        resp = client.put(
            f"/api/subscriptions/{sub_id}",
            json={"cron_expression": "0 9 * * 2"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["cron_expression"] == "0 9 * * 2"

    def test_delete_subscription_api(self, client, auth_headers, db_session, test_user, test_template):
        create_resp = client.post(
            "/api/subscriptions",
            json={"template_id": test_template.id, "cron_expression": "0 8 * * 1"},
            headers=auth_headers,
        )
        sub_id = create_resp.json()["id"]
        resp = client.delete(f"/api/subscriptions/{sub_id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_toggle_subscription_api(self, client, auth_headers, db_session, test_user, test_template):
        create_resp = client.post(
            "/api/subscriptions",
            json={"template_id": test_template.id, "cron_expression": "0 8 * * 1"},
            headers=auth_headers,
        )
        sub_id = create_resp.json()["id"]
        resp = client.post(
            f"/api/subscriptions/{sub_id}/toggle",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_run_subscription_api(self, client, auth_headers, db_session, test_user, test_template):
        create_resp = client.post(
            "/api/subscriptions",
            json={"template_id": test_template.id, "cron_expression": "0 8 * * 1"},
            headers=auth_headers,
        )
        sub_id = create_resp.json()["id"]
        with patch("app.tasks.subscription_tasks.execute_subscription_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="mock-task-id")
            resp = client.post(f"/api/subscriptions/{sub_id}/run", headers=auth_headers)
            assert resp.status_code == 200
            assert "task_id" in resp.json()

    def test_get_executions_api(self, client, auth_headers, db_session, test_user, test_template):
        create_resp = client.post(
            "/api/subscriptions",
            json={"template_id": test_template.id, "cron_expression": "0 8 * * 1"},
            headers=auth_headers,
        )
        sub_id = create_resp.json()["id"]
        resp = client.get(f"/api/subscriptions/{sub_id}/executions", headers=auth_headers)
        assert resp.status_code == 200

    def test_next_run_time_api(self, client):
        resp = client.get("/api/subscriptions/cron/next/0 8 * * *")
        assert resp.status_code == 200
        assert "next_run_at" in resp.json()

    def test_next_run_time_api_invalid(self, client):
        resp = client.get("/api/subscriptions/cron/next/invalid")
        assert resp.status_code == 400


class TestSubscriptionTask:
    """测试 Celery 订阅任务"""

    def test_execute_subscription_impl_not_found(self):
        from app.tasks.subscription_tasks import _execute_subscription_impl
        with patch("app.tasks.subscription_tasks.SessionLocal") as mock_db_factory:
            mock_db = MagicMock()
            mock_db_factory.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = None
            result = _execute_subscription_impl(99999)
            assert result["status"] == "error"
            assert "不存在" in result["message"]

    def test_execute_subscription_impl_inactive(self):
        from app.tasks.subscription_tasks import _execute_subscription_impl
        from app.models.subscription import QuerySubscription

        mock_sub = MagicMock(spec=QuerySubscription)
        mock_sub.is_active = False

        with patch("app.tasks.subscription_tasks.SessionLocal") as mock_db_factory:
            mock_db = MagicMock()
            mock_db_factory.return_value = mock_db
            mock_db.query.return_value.filter.return_value.first.return_value = mock_sub
            result = _execute_subscription_impl(1)
            assert result["status"] == "skipped"
