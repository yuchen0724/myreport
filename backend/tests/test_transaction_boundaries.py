from unittest.mock import patch

from app.core.security import verify_password
from app.models.data_source import DataSource
from app.models.menu import Menu
from app.models.query_history import QueryHistory
from app.models.user import User
from tests.conftest import TestingSessionLocal


def test_user_create_and_password_update_persist_across_sessions(
    client, admin_auth_headers
):
    create_response = client.post(
        "/api/users",
        headers=admin_auth_headers,
        json={
            "username": "persisted_user",
            "email": "persisted@example.com",
            "password": "initial-password",
        },
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/users/{user_id}",
        headers=admin_auth_headers,
        json={"password": "changed-password"},
    )
    assert update_response.status_code == 200

    with TestingSessionLocal() as verification_session:
        user = verification_session.query(User).filter(User.id == user_id).one()
        assert verify_password("changed-password", user.password_hash)
        assert not verify_password("initial-password", user.password_hash)


def test_menu_create_persists_across_sessions(client, admin_auth_headers):
    response = client.post(
        "/api/menus",
        headers=admin_auth_headers,
        json={"name": "持久化菜单", "path": "/persisted"},
    )
    assert response.status_code == 201
    menu_id = response.json()["id"]

    with TestingSessionLocal() as verification_session:
        menu = verification_session.query(Menu).filter(Menu.id == menu_id).one()
        assert menu.path == "/persisted"


def test_query_history_persists_after_request(
    client, auth_headers, db_session, test_user
):
    data_source = DataSource(
        name="历史记录数据源",
        type="MYSQL",
        host="localhost",
        port=3306,
        database="reporting",
        username="report_user",
        password_encrypted="encrypted",
        created_by=test_user.id,
        is_active=True,
    )
    db_session.add(data_source)
    db_session.commit()
    db_session.refresh(data_source)
    query_result = {
        "columns": ["id"],
        "rows": [[1]],
        "total": 1,
        "order_cols": ["id"],
    }

    with patch(
        "app.services.query_service.QueryService._execute_query",
        return_value=query_result,
    ):
        response = client.post(
            "/api/query/sql",
            headers=auth_headers,
            json={
                "data_source_id": data_source.id,
                "sql": "SELECT id FROM orders ORDER BY id",
            },
        )

    assert response.status_code == 200
    with TestingSessionLocal() as verification_session:
        history = verification_session.query(QueryHistory).filter(
            QueryHistory.user_id == test_user.id
        ).one()
        assert history.data_source_id == data_source.id
