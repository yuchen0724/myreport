from unittest.mock import MagicMock, patch

import pytest

from app.core.security import encrypt_password, get_password_hash
from app.models.data_source import DataSource
from app.models.subscription import QuerySubscription
from app.models.user import User
from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.schemas.query import SQLQueryResponse
from app.services.subscription_service import SubscriptionService
from app.tasks.subscription_tasks import _execute_subscription_query


def _create_user(db_session, username="sub_metric_user"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=get_password_hash("testpassword"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_data_source(db_session, user_id):
    data_source = DataSource(
        name="订阅语义指标数据源",
        type="MYSQL",
        host="localhost",
        port=3306,
        database="reporting",
        username="report_user",
        password_encrypted=encrypt_password("password"),
        is_active=True,
        created_by=user_id,
    )
    db_session.add(data_source)
    db_session.commit()
    db_session.refresh(data_source)
    return data_source


def _create_metric(db_session, data_source_id, user_id):
    return SemanticMetricRepository(db_session).create(
        {
            "metric_key": "gmv",
            "name": "GMV",
            "description": "成交金额",
            "data_source_id": data_source_id,
            "base_sql": "SELECT biz_date, amount, store_id FROM fact_orders",
            "metric_expression": "SUM(amount)",
            "dimensions": ["store_id"],
            "time_column": "biz_date",
            "is_active": True,
        },
        user_id=user_id,
    )


def test_create_semantic_metric_subscription(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _create_metric(db_session, data_source.id, test_user.id)

    sub = SubscriptionService(db_session).create(
        user_id=test_user.id,
        template_id=None,
        semantic_metric_key="gmv",
        semantic_query={
            "dimensions": ["store_id"],
            "start_time": "2026-05-01",
            "end_time": "2026-06-01",
        },
        cron_expression="0 8 * * *",
    )

    assert sub.template_id is None
    assert sub.semantic_metric_key == "gmv"
    assert sub.semantic_query["dimensions"] == ["store_id"]
    assert sub.to_dict()["metric_name"] == "gmv"


def test_create_semantic_metric_subscription_rejects_invisible_metric(db_session, test_user):
    other_user = _create_user(db_session, "sub_metric_other")
    data_source = _create_data_source(db_session, other_user.id)
    _create_metric(db_session, data_source.id, other_user.id)

    with pytest.raises(ValueError) as exc_info:
        SubscriptionService(db_session).create(
            user_id=test_user.id,
            template_id=None,
            semantic_metric_key="gmv",
            cron_expression="0 8 * * *",
        )

    assert "语义指标不存在或不可访问" in str(exc_info.value)


def test_create_subscription_requires_template_or_metric(db_session, test_user):
    with pytest.raises(ValueError) as exc_info:
        SubscriptionService(db_session).create(
            user_id=test_user.id,
            template_id=None,
            cron_expression="0 8 * * *",
        )

    assert "至少选择一种" in str(exc_info.value)


def test_create_business_briefing_subscription(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _create_metric(db_session, data_source.id, test_user.id)

    sub = SubscriptionService(db_session).create(
        user_id=test_user.id,
        template_id=None,
        cron_expression="0 8 * * *",
        subscription_type="briefing",
        briefing_config={"metric_keys": ["gmv"], "period": "yesterday"},
    )

    assert sub.subscription_type == "briefing"
    assert sub.briefing_config["metric_keys"] == ["gmv"]


def test_execute_semantic_metric_subscription_query(monkeypatch, db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _create_metric(db_session, data_source.id, test_user.id)
    sub = QuerySubscription(
        user_id=test_user.id,
        template_id=None,
        semantic_metric_key="gmv",
        semantic_query={
            "dimensions": ["store_id"],
            "start_time": "2026-05-01",
            "end_time": "2026-06-01",
            "page_size": 20,
        },
        cron_expression="0 8 * * *",
        notify_channel="feishu",
        is_active=True,
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    captured = {}

    class FakeQueryService:
        def __init__(self, db):
            self.db = db

        def execute_sql(self, request, user_id):
            captured["request"] = request
            captured["user_id"] = user_id
            return SQLQueryResponse(
                columns=["store_id", "metric_value"],
                rows=[["S001", 100]],
                total=1,
                page=request.page,
                page_size=request.page_size,
                execution_time_ms=4,
            )

    monkeypatch.setattr("app.services.semantic_metric_query_service.QueryService", FakeQueryService)

    name, summary = _execute_subscription_query(db_session, sub)

    assert name == "GMV"
    assert "语义指标查询完成" in summary
    assert captured["user_id"] == test_user.id
    assert captured["request"].page_size == 20
