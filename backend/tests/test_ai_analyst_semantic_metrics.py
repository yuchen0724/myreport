import pytest

from app.core.security import encrypt_password, get_password_hash
from app.models.data_source import DataSource
from app.models.user import User
from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.schemas.query import SQLQueryResponse
from app.services.ai_analyst_service import AIAnalystService


def _create_user(db_session, username):
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


def _create_data_source(db_session, user_id, name="AI 语义指标数据源"):
    data_source = DataSource(
        name=name,
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


def _create_metric(db_session, data_source_id, user_id, metric_key="gmv", name="GMV"):
    return SemanticMetricRepository(db_session).create(
        {
            "metric_key": metric_key,
            "name": name,
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


def test_ai_analyst_list_metrics_tool_filters_by_current_user(db_session, test_user):
    other_user = _create_user(db_session, "ai_metric_other")
    data_source = _create_data_source(db_session, test_user.id)
    _create_metric(db_session, data_source.id, test_user.id)
    _create_metric(db_session, data_source.id, other_user.id, metric_key="other_gmv", name="其他GMV")

    result = AIAnalystService(db_session).list_metrics_tool(data_source.id, user_id=test_user.id)

    assert result["success"] is True
    assert result["total"] == 1
    assert result["metrics"][0]["metric_key"] == "gmv"


def test_ai_analyst_query_metric_tool_uses_semantic_query_service(monkeypatch, db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _create_metric(db_session, data_source.id, test_user.id)
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
                execution_time_ms=5,
            )

    monkeypatch.setattr("app.services.semantic_metric_query_service.QueryService", FakeQueryService)

    result = AIAnalystService(db_session).query_metric_tool(
        metric_key="gmv",
        data_source_id=data_source.id,
        user_id=test_user.id,
        dimensions=["store_id"],
        start_time="2026-05-01",
        end_time="2026-06-01",
        page=1,
        page_size=20,
    )

    assert result["success"] is True
    assert result["metric"]["metric_key"] == "gmv"
    assert result["columns"] == ["store_id", "metric_value"]
    assert result["rows"] == [["S001", 100]]
    assert captured["user_id"] == test_user.id
    assert captured["request"].page_size == 20


def test_ai_analyst_query_metric_tool_rejects_invisible_metric(db_session, test_user):
    other_user = _create_user(db_session, "ai_metric_other")
    data_source = _create_data_source(db_session, other_user.id)
    _create_metric(db_session, data_source.id, other_user.id)

    result = AIAnalystService(db_session).query_metric_tool(
        metric_key="gmv",
        data_source_id=data_source.id,
        user_id=test_user.id,
    )

    assert result["success"] is False
    assert result["error"] == "指标不存在或已禁用"


def test_ai_analyst_execute_tool_dispatches_metric_tools(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _create_metric(db_session, data_source.id, test_user.id)
    service = AIAnalystService(db_session)

    result = service._execute_tool(
        {"tool": "list_metrics", "input": {"data_source_id": data_source.id}},
        data_source_id=data_source.id,
        user_id=test_user.id,
    )

    assert result["success"] is True
    assert result["metrics"][0]["metric_key"] == "gmv"


def test_ai_analyst_parse_action_handles_nested_tool_input(db_session):
    service = AIAnalystService(db_session)

    action = service._parse_action('ACTION: {"tool":"get_schema","input":{"data_source_id":10}}')

    assert action == {"tool": "get_schema", "input": {"data_source_id": 10}}


def test_ai_analyst_parse_action_uses_first_action_when_model_repeats(db_session):
    service = AIAnalystService(db_session)

    action = service._parse_action(
        'ACTION: {"tool":"get_schema","input":{"data_source_id":10}}'
        'ACTION: {"tool":"get_schema","input":{"data_source_id":10}}'
    )

    assert action == {"tool": "get_schema", "input": {"data_source_id": 10}}


def test_ai_analyst_parse_action_handles_json_code_block(db_session):
    service = AIAnalystService(db_session)

    action = service._parse_action(
        '```json\n{"tool":"list_metrics","input":{"data_source_id":10}}\n```'
    )

    assert action == {"tool": "list_metrics", "input": {"data_source_id": 10}}
