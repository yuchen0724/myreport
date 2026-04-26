def test_login_success(client, test_user):
    """测试登录成功"""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_failure(client):
    """测试登录失败"""
    response = client.post(
        "/api/auth/login",
        data={"username": "wronguser", "password": "wrongpassword"}
    )
    assert response.status_code == 401

def test_get_current_user(client, auth_headers, test_user):
    """测试获取当前用户"""
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email

def test_get_current_user_unauthorized(client):
    """测试未授权访问"""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
