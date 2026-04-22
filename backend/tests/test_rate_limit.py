# backend/tests/test_rate_limit.py
import pytest
from app.middleware.rate_limit import RateLimiter

def test_rate_limit():
    """测试限流功能"""
    limiter = RateLimiter()

    # 前100个请求应该被允许
    for i in range(100):
        assert limiter.is_allowed("test_key") is True

    # 第101个请求应该被拒绝
    assert limiter.is_allowed("test_key") is False

def test_rate_limit_remaining():
    """测试剩余请求数"""
    limiter = RateLimiter()

    # 发送10个请求
    for i in range(10):
        limiter.is_allowed("test_key")

    # 剩余请求数应该是90
    remaining = limiter.get_remaining("test_key")
    assert remaining == 90
