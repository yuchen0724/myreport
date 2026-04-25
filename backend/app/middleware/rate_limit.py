"""限流中间件

基于 IP 地址的请求频率限制。
生产环境建议升级为 Redis 集中存储（支持多 worker/多实例）。
"""

import time
from collections import defaultdict
from typing import Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于内存的 IP 限流中间件。"""

    def __init__(self, app, max_requests: int = 100, window: int = 60):
        """
        Args:
            app: ASGI 应用
            max_requests: 时间窗口内最大请求数（默认 100）
            window: 时间窗口秒数（默认 60）
        """
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self.requests: Dict[str, list] = defaultdict(list)

    def _clean_expired(self, key: str, now: float):
        """清理过期记录"""
        self.requests[key] = [
            ts for ts in self.requests[key] if now - ts < self.window
        ]

    async def dispatch(self, request: Request, call_next):
        # 健康检查不限制
        if request.url.path in ("/health", "/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        now = time.time()

        self._clean_expired(key, now)

        if len(self.requests[key]) >= self.max_requests:
            remaining = self.max_requests - len(self.requests[key])
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "remaining": max(0, remaining),
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        self.requests[key].append(now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            self.max_requests - len(self.requests[key])
        )
        return response
