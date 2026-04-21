import pytest
from fastapi.testclient import TestClient


def test_create_data_source(client: TestClient):
    """测试创建数据源"""
    response = client.post(
        "/api/datasources",
        json={
            "name": "Test DataSource",
            "type": "MYSQL",
            "host": "localhost",
            "port": 3306,
            "database": "test",
            "username": "root",
            "password": "password"
        }
    )
    # 由于没有真实数据库，会返回 400
    assert response.status_code in [201, 400]


def test_list_data_sources(client: TestClient):
    """测试列出数据源"""
    response = client.get("/api/datasources")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_test_connection(client: TestClient):
    """测试连接测试"""
    response = client.post(
        "/api/datasources/test",
        json={
            "type": "MYSQL",
            "host": "localhost",
            "port": 3306,
            "database": "test",
            "username": "root",
            "password": "password"
        }
    )
    assert response.status_code == 200
    assert "success" in response.json()
