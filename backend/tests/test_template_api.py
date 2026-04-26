def test_create_template(client, auth_headers):
    """测试创建模板"""
    response = client.post(
        "/api/templates/",
        headers=auth_headers,
        json={
            "name": "新模板",
            "description": "新模板描述",
            "config": {"sql": "SELECT * FROM users"},
            "is_public": False
        }
    )
    assert response.status_code == 201  # 创建资源应该返回201
    data = response.json()
    assert data["name"] == "新模板"
    assert data["version"] == 1

def test_get_templates(client, auth_headers, test_template):
    """测试获取模板列表"""
    response = client.get("/api/templates/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(t["id"] == test_template.id for t in data)

def test_get_template_detail(client, auth_headers, test_template):
    """测试获取模板详情"""
    response = client.get(f"/api/templates/{test_template.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_template.id
    assert data["name"] == test_template.name

def test_update_template(client, auth_headers, test_template):
    """测试更新模板"""
    response = client.put(
        f"/api/templates/{test_template.id}",
        headers=auth_headers,
        json={
            "name": "更新后的模板",
            "description": "更新后的描述"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "更新后的模板"
    assert data["version"] == 2

def test_delete_template(client, auth_headers, test_template):
    """测试删除模板"""
    response = client.delete(f"/api/templates/{test_template.id}", headers=auth_headers)
    assert response.status_code == 204  # 删除资源应该返回204
    
    # 验证删除
    response = client.get(f"/api/templates/{test_template.id}", headers=auth_headers)
    assert response.status_code == 404
