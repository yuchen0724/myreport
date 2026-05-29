"""限流中间件

基于 IP 地址或用户 ID + 路径的请求频率限制。
- 已认证用户：使用 user_id + path_hash 作为限流键
- 未认证用户：使用 client_ip + path_hash 作为限流键
支持内存模式和 Redis 模式（生产环境推荐）。
当 Redis 可用时自动切换至 Redis 后端以支持多 worker 场景。
"""

import time
import threading
from collections import defaultdict
from typing import Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.config import get_settings
from app.core.security import decode_access_token


_PATH_GROUPS = {
    "/api/query": {"max_requests": 30, "window": 60},
    "/api/nl2sql": {"max_requests": 20, "window": 60},
    "/api/report": {"max_requests": 10, "window": 60},
    "/api/datasources": {"max_requests": 50, "window": 60},
    "/api/templates": {"max_requests": 100, "window": 60},
    "/api/stats": {"max_requests": 60, "window": 60},
}


def _get_path_config(path: str) -> Dict:
    """获取路径对应的限流配置"""
    for prefix, config in _PATH_GROUPS.items():
        if path.startswith(prefix):
            return config
    return {"max_requests": 100, "window": 60}


class MemoryRateLimiterBackend:
    """内存限流后端（单 worker 场景）"""

    def __init__(self, max_requests: int, window: int):
        self.default_max_requests = max_requests
        self.default_window = window
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str, path: str) -> bool:
        config = _get_path_config(path)
        max_r = config["max_requests"]
        window = config["window"]
        now = time.time()
        with self._lock:
            self._requests[key] = [ts for ts in self._requests[key] if now - ts < window]
            if len(self._requests[key]) >= max_r:
                return False
            self._requests[key].append(now)
            return True

    def get_remaining(self, key: str, path: str) -> int:
        config = _get_path_config(path)
        max_r = config["max_requests"]
        window = config["window"]
        now = time.time()
        with self._lock:
            self._requests[key] = [ts for ts in self._requests[key] if now - ts < window]
            return max(0, max_r - len(self._requests[key]))

    def get_limit(self, path: str) -> int:
        return _get_path_config(path)["max_requests"]

    def clear(self):
        with self._lock:
            self._requests.clear()


class RedisRateLimiterBackend:
    """Redis 限流后端（多 worker 场景，滑动窗口）"""

    def __init__(self, redis_client, max_requests: int, window: int):
        self._redis = redis_client
        self.default_max_requests = max_requests
        self.default_window = window

    def _redis_key(self, key: str, path: str) -> str:
        config = _get_path_config(path)
        # 不同路径组使用不同后缀以确保键的分布
        return f"{key}:{hash(path) % 100}"

    def is_allowed(self, key: str, path: str) -> bool:
        config = _get_path_config(path)
        max_r = config["max_requests"]
        window = config["window"]
        rkey = self._redis_key(key, path)
        now = time.time()
        pipe = self._redis.pipeline()
        # 移除窗口外的记录
        pipe.zremrangebyscore(rkey, 0, now - window)
        # 添加当前请求
        pipe.zadd(rkey, {str(now): now})
        # 设置过期时间
        pipe.expire(rkey, window + 10)
        # 统计窗口内请求数
        pipe.zcard(rkey)
        results = pipe.execute()
        count = results[3]
        return count <= max_r

    def get_remaining(self, key: str, path: str) -> int:
        config = _get_path_config(path)
        max_r = config["max_requests"]
        window = config["window"]
        rkey = self._redis_key(key, path)
        now = time.time()
        self._redis.zremrangebyscore(rkey, 0, now - window)
        count = self._redis.zcard(rkey)
        return max(0, max_r - count)

    def get_limit(self, path: str) -> int:
        return _get_path_config(path)["max_requests"]

    def clear(self):
        """清空所有限流键（测试用）"""
        keys = self._redis.keys("rate_limit:*")
        if keys:
            self._redis.delete(*keys)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""

    SKIP_PATHS = {
        "/health", "/health/live", "/health/ready", "/metrics", "/api/stats/metrics",
        "/docs", "/openapi.json", "/redoc",
        "/api/auth/login", "/api/auth/register",
        "/login", "/register",
    }
    SKIP_PREFIXES = ["/static", "/assets", "/_nuxt", "/node_modules"]

    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        max_r = getattr(settings, 'rate_limit_max_requests', 100)
        window = getattr(settings, 'rate_limit_window', 60)

        # 尝试使用 Redis 后端，不可用时回退到内存后端
        self._backend = self._init_backend(max_r, window)

    def _init_backend(self, max_r: int, window: int):
        try:
            from app.core.redis import redis_client
            redis_client.ping()
            return RedisRateLimiterBackend(redis_client, max_r, window)
        except Exception:
            return MemoryRateLimiterBackend(max_r, window)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in self.SKIP_PATHS:
            return await call_next(request)

        for prefix in self.SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        client_ip = self._get_client_ip(request)
        path_hash = hash(request.url.path) % 100
        user_id = self._get_user_id_from_request(request)
        if user_id is not None:
            key = f"rate_limit:user:{user_id}:{path_hash}"
        else:
            key = f"rate_limit:ip:{client_ip}:{path_hash}"

        if not self._backend.is_allowed(key, request.url.path):
            limit = self._backend.get_limit(request.url.path)
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "limit": limit,
                    "remaining": 0,
                    "retry_after": 60,
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + 60),
                    "Retry-After": "60",
                },
            )

        response = await call_next(request)

        limit = self._backend.get_limit(request.url.path)
        remaining = self._backend.get_remaining(key, request.url.path)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    def _get_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"

    def _get_user_id_from_request(self, request: Request) -> Optional[int]:
        """从 Authorization: Bearer <token> 中提取 user_id，失败时返回 None"""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        token = auth_header[len("Bearer "):]
        payload = decode_access_token(token)
        if payload is None:
            return None
        user_id = payload.get("user_id")
        return user_id if isinstance(user_id, int) else None
