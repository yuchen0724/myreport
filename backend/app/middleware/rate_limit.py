# backend/app/middleware/rate_limit.py
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from typing import Dict

class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.max_requests = 100  # 每分钟最大请求数
        self.window = 60  # 时间窗口（秒）

    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        now = time.time()

        # 清理过期记录
        self.requests[key] = [
            timestamp for timestamp in self.requests[key]
            if now - timestamp < self.window
        ]

        # 检查是否超过限制
        if len(self.requests[key]) >= self.max_requests:
            return False

        # 记录请求
        self.requests[key].append(now)
        return True

    def get_remaining(self, key: str) -> int:
        """获取剩余请求数"""
        now = time.time()
        self.requests[key] = [
            timestamp for timestamp in self.requests[key]
            if now - timestamp < self.window
        ]
        return self.max_requests - len(self.requests[key])

# 全局限流器
rate_limiter = RateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    """限流中间件"""
    # 使用 IP 地址作为限流键
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"

    # 检查是否允许请求
    if not rate_limiter.is_allowed(key):
        remaining = rate_limiter.get_remaining(key)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "请求过于频繁，请稍后再试",
                "remaining": remaining
            }
        )

    # 添加限流信息到响应头
    response = await call_next(request)
    remaining = rate_limiter.get_remaining(key)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)

    return response
