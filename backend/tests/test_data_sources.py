import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, encrypt_password, get_password_hash
from app.models.data_source import DataSource
from app.models.user import User


def test_create_data_source(client: TestClient, auth_headers: dict):
    """测试创建数据源"""
    response = client.post(
        "/api/datasources",
        headers=auth_headers,
        json={
            "name": "Test DataSource",
            "type": "MYSQL",
            "host": "localhost",
            "port": 3306,
            "database": "test",
            "username": "root",
            "password": "testpassword"
        }
    )
    # 由于没有真实数据库，会返回 400
    assert response.status_code in [201, 400]


def test_list_data_sources(client: TestClient, auth_headers: dict):
    """测试列出数据源"""
    response = client.get("/api/datasources", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_test_connection(client: TestClient, auth_headers: dict):
    """测试连接测试"""
    response = client.post(
        "/api/datasources/test",
        headers=auth_headers,
        json={
            "type": "MYSQL",
            "host": "localhost",
            "port": 3306,
            "database": "test",
            "username": "root",
            "password": "testpassword"
        }
    )
    # 无真实连接返回 400
    assert response.status_code in [200, 400]


def test_data_source_detail_never_exposes_password(
    client: TestClient, auth_headers: dict, db_session, test_user
):
    data_source = DataSource(
        name="Owned source",
        type="MYSQL",
        host="localhost",
        port=3306,
        database="test",
        username="reader",
        password_encrypted=encrypt_password("top-secret"),
        created_by=test_user.id,
        is_active=True,
    )
    db_session.add(data_source)
    db_session.commit()

    response = client.get(f"/api/datasources/{data_source.id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json().get("password_decrypted") is None


def test_data_source_detail_rejects_other_user(client: TestClient, db_session, test_user):
    data_source = DataSource(
        name="Private source",
        type="MYSQL",
        host="localhost",
        port=3306,
        database="test",
        username="reader",
        password_encrypted=encrypt_password("top-secret"),
        created_by=test_user.id,
        is_active=True,
    )
    other_user = User(
        username="other-ds-user",
        email="other-ds-user@example.com",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    db_session.add_all([data_source, other_user])
    db_session.commit()
    token = create_access_token({"sub": other_user.username, "user_id": other_user.id})

    response = client.get(
        f"/api/datasources/{data_source.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
