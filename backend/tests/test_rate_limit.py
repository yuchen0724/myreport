# backend/tests/test_rate_limit.py
import pytest
from app.middleware.rate_limit import MemoryRateLimiterBackend, _path_token

def test_rate_limit():
    """测试限流功能"""
    limiter = MemoryRateLimiterBackend(max_requests=100, window=60)

    # 使用不在 PATH_GROUPS 中的路径，使用默认 100 次的限制
    path = "/api/some_other"

    # 前100个请求应该被允许
    for i in range(100):
        assert limiter.is_allowed("test_key", path) is True

    # 第101个请求应该被拒绝
    assert limiter.is_allowed("test_key", path) is False

def test_rate_limit_remaining():
    """测试剩余请求数"""
    limiter = MemoryRateLimiterBackend(max_requests=100, window=60)

    path = "/api/some_other"

    # 发送10个请求
    for i in range(10):
        limiter.is_allowed("test_key", path)

    # 剩余请求数应该是90
    remaining = limiter.get_remaining("test_key", path)
    assert remaining == 90


def test_path_token_is_stable_and_path_specific():
    assert _path_token("/api/query/sql") == _path_token("/api/query/sql")
    assert _path_token("/api/query/sql") != _path_token("/api/nl2sql/parse")
