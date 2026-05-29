from datetime import date

import pytest

from app.core.security import encrypt_password, get_password_hash
from app.models.data_source import DataSource
from app.models.user import User
from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.schemas.query import SQLQueryResponse
from app.services.rca_service import RcaService


def _create_user(db_session, username="rca_user"):
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
        name="RCA 语义指标数据源",
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


def _create_config(service, data_source_id, user_id, metric_key="gmv"):
    return service.create_config(
        {
            "name": "gmv_rca",
            "label": "GMV RCA",
            "metric_field": "amount",
            "source_table": "reporting.fact_orders",
            "semantic_metric_key": metric_key,
            "threshold_type": "percent_change",
            "threshold_value": 10.0,
            "compare_type": "mom",
            "drill_dimensions": ["store_id"],
            "group_id": 812,
            "data_source_id": data_source_id,
        },
        user_id=user_id,
    )


def test_rca_config_validates_semantic_metric_visibility(db_session, test_user):
    other_user = _create_user(db_session, "rca_other")
    data_source = _create_data_source(db_session, other_user.id)
    _create_metric(db_session, data_source.id, other_user.id)

    with pytest.raises(ValueError) as exc_info:
        _create_config(RcaService(db_session), data_source.id, test_user.id)

    assert "语义指标不存在或不可访问" in str(exc_info.value)


def test_rca_config_accepts_visible_semantic_metric(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _create_metric(db_session, data_source.id, test_user.id)

    config = _create_config(RcaService(db_session), data_source.id, test_user.id)

    assert config.semantic_metric_key == "gmv"


def test_rca_semantic_metric_analysis_uses_metric_query_service(monkeypatch, db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _create_metric(db_session, data_source.id, test_user.id)
    service = RcaService(db_session)
    config = _create_config(service, data_source.id, test_user.id)
    task = service.trigger_analysis(
        {
            "metric_config_id": config.id,
            "analysis_date": date(2026, 6, 1),
            "period_days": 7,
        },
        user_id=test_user.id,
    )
    captured = []

    class FakeQueryService:
        def __init__(self, db):
            self.db = db

        def execute_sql(self, request, user_id):
            captured.append({"request": request, "user_id": user_id})
            is_dimension_query = "store_id, SUM(amount) AS metric_value" in request.sql
            is_current = request.params["start_time"] == "20260525"
            if not is_dimension_query:
                value = 80 if is_current else 100
                rows = [[value]]
                columns = ["metric_value"]
            elif is_current:
                columns = ["store_id", "metric_value"]
                rows = [["S001", 40], ["S002", 40]]
            else:
                columns = ["store_id", "metric_value"]
                rows = [["S001", 80], ["S002", 20]]
            return SQLQueryResponse(
                columns=columns,
                rows=rows,
                total=len(rows),
                page=request.page,
                page_size=request.page_size,
                execution_time_ms=3,
            )

    monkeypatch.setattr("app.services.semantic_metric_query_service.QueryService", FakeQueryService)

    result = service.execute_analysis(task.task_id)
    anomalies = service.get_anomalies(task.task_id)
    refreshed_task = service.get_task(task.task_id)

    assert result == {"status": "completed", "anomaly_count": 2}
    assert refreshed_task.summary["semantic_metric_key"] == "gmv"
    assert refreshed_task.summary["total_change_pct"] == -20.0
    assert {item.dimension_path["store_id"] for item in anomalies} == {"S001", "S002"}
    assert all(call["user_id"] == test_user.id for call in captured)
