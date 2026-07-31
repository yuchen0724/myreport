from app.core.security import create_access_token, get_password_hash
from app.models.scheduled_report import ScheduledReport
from app.models.user import User


def _create_other_user(db_session, username="boundary_other"):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=get_password_hash("testpassword"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token({"sub": user.username, "user_id": user.id})
    return user, {"Authorization": f"Bearer {token}"}


def test_regular_user_cannot_list_users(client, auth_headers):
    assert client.get("/api/users", headers=auth_headers).status_code == 403


def test_admin_can_list_users(client, admin_auth_headers):
    assert client.get("/api/users", headers=admin_auth_headers).status_code == 200


def test_disabled_user_token_is_rejected(client, db_session, test_user, auth_headers):
    test_user.is_active = False
    db_session.commit()

    response = client.get("/api/templates", headers=auth_headers)

    assert response.status_code == 403


def test_regular_user_cannot_create_global_menu(client, auth_headers):
    response = client.post(
        "/api/menus",
        headers=auth_headers,
        json={"name": "越权菜单", "path": "/forbidden"},
    )

    assert response.status_code == 403


def test_scheduled_reports_are_owner_scoped(
    client, db_session, auth_headers, test_user, test_template
):
    report = ScheduledReport(
        name="私有定时报表",
        cron_expression="0 8 * * *",
        template_id=test_template.id,
        output_format="excel",
        recipients=[],
        created_by=test_user.id,
        enabled=True,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    _, other_headers = _create_other_user(db_session)

    assert client.get("/api/scheduled-reports/", headers=other_headers).json() == []
    assert client.get(
        f"/api/scheduled-reports/{report.id}", headers=other_headers
    ).status_code == 404
    assert client.put(
        f"/api/scheduled-reports/{report.id}",
        headers=other_headers,
        json={"name": "越权修改"},
    ).status_code == 404
    assert client.get(
        f"/api/scheduled-reports/{report.id}/deliveries", headers=other_headers
    ).status_code == 404
