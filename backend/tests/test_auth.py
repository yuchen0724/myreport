import pytest
from fastapi.testclient import TestClient


def test_login_success(client: TestClient):
    """测试登录成功"""
    response = client.post(
        "/api/auth/login",
        data={"username": "test", "password": "test"}
    )
    assert response.status_code == 401  # 用户不存在


def test_login_invalid_credentials(client: TestClient):
    """测试登录失败"""
    response = client.post(
        "/api/auth/login",
        data={"username": "invalid", "password": "invalid"}
    )
    assert response.status_code == 401


def test_get_current_user_without_token(client: TestClient):
    """测试未登录获取用户信息"""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
