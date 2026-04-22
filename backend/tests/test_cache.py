# backend/tests/test_cache.py
import pytest
from app.services.cache_service import CacheService

def test_cache_set_get():
    """测试缓存设置和获取"""
    cache = CacheService()

    cache.set("test_key", {"data": "test_value"})
    result = cache.get("test_key")

    assert result is not None
    assert result["data"] == "test_value"

def test_cache_delete():
    """测试缓存删除"""
    cache = CacheService()

    cache.set("test_key", {"data": "test_value"})
    cache.delete("test_key")
    result = cache.get("test_key")

    assert result is None

def test_cache_exists():
    """测试缓存存在性检查"""
    cache = CacheService()

    cache.set("test_key", {"data": "test_value"})
    assert cache.exists("test_key") is True

    cache.delete("test_key")
    assert cache.exists("test_key") is False
