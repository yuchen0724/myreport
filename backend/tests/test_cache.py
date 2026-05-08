"""缓存服务测试 - 使用 mock Redis 避免依赖真实 Redis 实例"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.cache_service import CacheService


@pytest.fixture
def mock_redis():
    """创建 mock Redis 客户端"""
    client = MagicMock()
    # get() 默认返回 None
    client.get.return_value = None
    # setex() 默认成功
    client.setex.return_value = True
    # delete() 默认成功
    client.delete.return_value = 1
    # exists() 默认返回 0
    client.exists.return_value = 0
    return client


def test_cache_set_get(mock_redis):
    """测试缓存设置和获取"""
    cache = CacheService(redis_client=mock_redis)

    # 模拟 set 后的 get 返回值
    expected = {"result": {"data": "test_value"}, "cached_at": "2024-01-01", "ttl": 300}
    cache.set("SELECT 1", {"data": "test_value"})

    # 验证 Redis setex 被调用
    assert mock_redis.setex.called

    # 模拟 get 返回
    cache_key = cache._generate_cache_key("SELECT 1")
    mock_redis.get.return_value = '{"result": {"data": "test_value"}, "cached_at": "2024-01-01", "ttl": 300}'

    result = cache.get("SELECT 1")
    assert result is not None
    assert result["result"]["data"] == "test_value"
    mock_redis.get.assert_called_with(cache_key)


def test_cache_delete(mock_redis):
    """测试缓存删除"""
    cache = CacheService(redis_client=mock_redis)

    cache.delete("SELECT 1")
    cache_key = cache._generate_cache_key("SELECT 1")
    mock_redis.delete.assert_called_with(cache_key)


def test_cache_exists(mock_redis):
    """测试缓存存在性检查"""
    cache = CacheService(redis_client=mock_redis)

    # 不存在
    mock_redis.exists.return_value = 0
    assert cache.exists("SELECT 1") is False

    # 存在
    mock_redis.exists.return_value = 1
    assert cache.exists("SELECT 1") is True


def test_cache_no_redis_fallback():
    """测试无 Redis 连接时的降级行为 — mock redis ping 失败"""
    cache = CacheService(redis_client=None)
    # 手动设置 redis_client=None 来模拟连接失败后已降级场景
    cache.redis_client = None

    assert cache.get("SELECT 1") is None
    assert cache.set("SELECT 1", {}) is False
    assert cache.delete("SELECT 1") is False
    assert cache.exists("SELECT 1") is False
    assert cache.clear_pattern("*") is False
    assert cache.get_stats() == {"status": "disconnected"}
