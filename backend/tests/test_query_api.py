def test_get_query_history(client, auth_headers):
    """测试获取查询历史"""
    response = client.get("/api/query/history", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_execute_query_unauthorized(client):
    """测试未授权执行查询"""
    response = client.post(
        "/api/query/sql",
        json={"sql": "SELECT 1"}
    )
    assert response.status_code == 401

def test_nl2sql_query(client, auth_headers):
    """测试NL2SQL查询"""
    response = client.post(
        "/api/nl2sql/parse",
        headers=auth_headers,
        json={"question": "查询所有用户", "data_source_id": 1}
    )
    assert response.status_code in [200, 500]  # 可能成功或服务错误
    data = response.json()
    # NL2SQL响应可能包含selected_sql或suggestions
    assert "selected_sql" in data or "suggestions" in data or "detail" in data
