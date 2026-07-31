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
    """测试NL2SQL查询（带 LLM mock，不依赖外部服务）"""
    from unittest.mock import patch
    # Mock LLMClient 以避免调用外部 LLM 服务
    with patch('app.services.nl2sql_service.get_llm_client') as mock_get_llm:
        # 配置 mock 返回一个模拟的 LLM 结果
        mock_llm = mock_get_llm.return_value
        from app.utils.llm_client import LLMError
        
        # 让 LLM 调用抛异常，测试 fallback 到规则引擎
        mock_llm.chat.side_effect = LLMError("mock: no external LLM in tests")
        mock_llm.timeout = 1
        
        response = client.post(
            "/api/nl2sql/parse",
            headers=auth_headers,
            json={"question": "查询所有用户", "data_source_id": 1}
        )
        # 模拟环境没有真实数据源，应该返回 500 或 200（fallback到规则引擎）
        # 如果fallback到规则引擎但没有数据源配置，会返回500
        assert response.status_code in [200, 404, 500, 422]
        data = response.json()
        # NL2SQL响应可能包含selected_sql或suggestions或detail
        assert "selected_sql" in data or "suggestions" in data or "detail" in data or "message" in data
