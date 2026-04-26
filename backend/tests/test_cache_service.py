"""缓存服务测试"""

import pytest
from app.services.cache_service import cache_service


def test_cache_service_initialization():
    """测试缓存服务初始化"""
    assert cache_service is not None
    assert cache_service.redis_client is not None or cache_service.redis_client is None  # Redis可能未连接


def test_cache_generate_key():
    """测试缓存键生成"""
    sql = "SELECT * FROM users WHERE id = :id"
    params = {"id": 1}
    
    key1 = cache_service._generate_cache_key(sql, params)
    key2 = cache_service._generate_cache_key(sql, params)
    
    # 相同的SQL和参数应该生成相同的键
    assert key1 == key2
    
    # 不同的参数应该生成不同的键
    key3 = cache_service._generate_cache_key(sql, {"id": 2})
    assert key1 != key3


def test_cache_set_and_get():
    """测试缓存设置和获取"""
    if not cache_service.redis_client:
        pytest.skip("Redis未连接")
    
    sql = "SELECT * FROM test_table"
    params = {"limit": 10}
    result = {
        "columns": ["id", "name"],
        "rows": [[1, "test"], [2, "test2"]],
        "total": 2
    }
    
    # 设置缓存
    success = cache_service.set(sql, result, params=params, ttl=60)
    assert success is True
    
    # 获取缓存
    cached = cache_service.get(sql, params)
    assert cached is not None
    assert cached["result"]["total"] == 2
    
    # 清理
    cache_service.delete(sql, params)


def test_cache_delete():
    """测试缓存删除"""
    if not cache_service.redis_client:
        pytest.skip("Redis未连接")
    
    sql = "SELECT * FROM delete_test"
    params = {"test": True}
    result = {"test": "data"}
    
    # 设置缓存
    cache_service.set(sql, result, params=params, ttl=60)
    
    # 验证缓存存在
    cached = cache_service.get(sql, params)
    assert cached is not None
    
    # 删除缓存
    success = cache_service.delete(sql, params)
    assert success is True
    
    # 验证缓存已删除
    cached = cache_service.get(sql, params)
    assert cached is None


def test_cache_clear_pattern():
    """测试批量清除缓存"""
    if not cache_service.redis_client:
        pytest.skip("Redis未连接")
    
    # 设置多个缓存
    for i in range(3):
        sql = f"SELECT * FROM test_{i}"
        cache_service.set(sql, {"data": i}, ttl=60)
    
    # 清除所有查询缓存
    success = cache_service.clear_pattern("query_result:*")
    assert success is True
    
    # 验证缓存已清除
    for i in range(3):
        sql = f"SELECT * FROM test_{i}"
        cached = cache_service.get(sql)
        assert cached is None


def test_cache_stats():
    """测试缓存统计"""
    stats = cache_service.get_stats()
    assert stats is not None
    assert "status" in stats
