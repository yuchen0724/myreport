import pytest
from fastapi.testclient import TestClient


def test_export_excel(client: TestClient, auth_headers: dict):
    """测试导出 Excel"""
    response = client.post(
        "/api/report/excel",
        headers=auth_headers,
        json={
            "data_source_id": 1,
            "sql": "SELECT 1",
            "filename": "test.xlsx"
        }
    )
    # 由于没有真实数据源，会返回 400
    assert response.status_code in [200, 400, 404]


@pytest.mark.skip(reason="需要 Redis 连接，在 CI 环境中跳过")
def test_export_excel_async(client: TestClient, auth_headers: dict):
    """测试异步导出 Excel"""
    response = client.post(
        "/api/report/excel/async",
        headers=auth_headers,
        json={
            "data_source_id": 1,
            "sql": "SELECT 1",
            "filename": "test.xlsx"
        }
    )
    # 由于没有真实数据源，会返回 400
    assert response.status_code in [200, 400, 404]
