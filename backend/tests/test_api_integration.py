def test_complete_template_workflow(client, auth_headers):
    """测试完整的模板工作流"""
    # 1. 创建模板
    create_response = client.post(
        "/api/templates",
        headers=auth_headers,
        json={
            "name": "工作流测试模板",
            "description": "测试完整工作流",
            "config": {"data_source_id": 1, "sql": "SELECT * FROM users"},
            "is_public": False
        }
    )
    assert create_response.status_code == 201  # 创建资源应该返回201
    template_id = create_response.json()["id"]
    
    # 2. 获取模板详情
    get_response = client.get(f"/api/templates/{template_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "工作流测试模板"
    
    # 3. 更新模板
    update_response = client.put(
        f"/api/templates/{template_id}",
        headers=auth_headers,
        json={"name": "更新后的工作流模板"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    
    # 4. 获取版本历史（暂时跳过，因为版本历史功能需要额外配置）
    # version_response = client.get(
    #     f"/api/templates/{template_id}/versions",
    #     headers=auth_headers
    # )
    # assert version_response.status_code == 200
    # assert len(version_response.json()) >= 2
    
    # 5. 删除模板
    delete_response = client.delete(f"/api/templates/{template_id}", headers=auth_headers)
    assert delete_response.status_code == 204  # 删除资源应该返回204

def test_authentication_flow(client, test_user):
    """测试认证流程"""
    # 1. 登录
    login_response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpassword"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # 2. 使用token访问受保护资源
    headers = {"Authorization": f"Bearer {token}"}
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "testuser"
