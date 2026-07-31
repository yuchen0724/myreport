from types import SimpleNamespace
from unittest.mock import patch

from app.models.data_source import DataSource
from app.models.sql_correction import SqlCorrection
from app.services.ai_analyst_service import AIAnalystService


def _data_source(owner_id):
    return DataSource(
        name="AI 测试数据源",
        type="DORIS",
        host="localhost",
        port=9030,
        database="reporting",
        username="reader",
        password_encrypted="encrypted",
        created_by=owner_id,
        is_active=True,
    )


def test_user_feedback_stays_candidate_until_admin_review(
    client, db_session, test_user, auth_headers, test_admin, admin_auth_headers
):
    data_source = _data_source(test_user.id)
    db_session.add(data_source)
    db_session.commit()

    response = client.post(
        "/api/ai-analyst/feedback",
        headers=auth_headers,
        json={
            "data_source_id": data_source.id,
            "question": "统计昨日销售额",
            "original_sql": "SELECT amount FROM sale",
            "corrected_sql": "SELECT SUM(amount) FROM sales",
            "user_feedback": "表名和聚合方式已修正",
        },
    )

    assert response.status_code == 200
    correction = db_session.query(SqlCorrection).filter_by(
        id=response.json()["id"]
    ).one()
    assert correction.review_status == "candidate"
    assert correction.verified_by is None

    path = f"/api/ai-analyst/feedback/candidates?data_source_id={data_source.id}"
    assert client.get(path, headers=auth_headers).status_code == 403
    admin_response = client.get(path, headers=admin_auth_headers)
    assert admin_response.status_code == 200
    assert admin_response.json()[0]["id"] == correction.id


def test_schema_tool_binds_schema_and_table_filters(db_session):
    service = AIAnalystService(db_session)
    data_source = SimpleNamespace(type="DORIS", database="reporting")
    service.query_service.data_source_service.require_access = lambda *_: data_source
    malicious_name = "orders' OR 1=1 --"

    with patch(
        "app.utils.db_executor.execute_query", return_value=([], [])
    ) as execute_query:
        result = service.get_schema_tool(1, malicious_name, user_id=7)

    assert result["success"] is True
    _, sql, params = execute_query.call_args.args
    assert malicious_name not in sql
    assert "TABLE_SCHEMA = :schema_name" in sql
    assert "TABLE_NAME = :table_name" in sql
    assert params == {"table_name": malicious_name, "schema_name": "reporting"}
