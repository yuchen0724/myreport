from unittest.mock import patch


def test_regular_user_cannot_manage_cache(client, auth_headers):
    response = client.post("/api/cache/clear", headers=auth_headers)

    assert response.status_code == 403


def test_admin_clear_is_limited_to_query_cache(client, admin_auth_headers):
    with patch("app.api.cache.cache_service.clear_pattern", return_value=True) as clear_pattern:
        response = client.post(
            "/api/cache/clear?pattern=*",
            headers=admin_auth_headers,
        )

    assert response.status_code == 200
    clear_pattern.assert_called_once_with("query_result:*")
