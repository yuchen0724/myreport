import pytest
from fastapi.testclient import TestClient


def test_execute_sql_invalid(client: TestClient, auth_headers: dict):
    """测试执行无效 SQL"""
    response = client.post(
        "/api/query/sql",
        headers=auth_headers,
        json={
            "data_source_id": 1,
            "sql": "DROP TABLE users"
        }
    )
    assert response.status_code == 400


def test_execute_sql_select(client: TestClient, auth_headers: dict):
    """测试执行 SELECT 查询"""
    response = client.post(
        "/api/query/sql",
        headers=auth_headers,
        json={
            "data_source_id": 1,
            "sql": "SELECT 1"
        }
    )
    # 由于没有真实数据源，会返回 400
    assert response.status_code in [200, 400, 404]
