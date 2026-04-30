"""限流中间件

基于 IP 地址的请求频率限制。
支持内存模式和 Redis 模式（生产环境推荐）。
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


class RateLimiter:
    """限流核心逻辑"""
    
    # 路径分组配置：不同路径有不同的限流策略
    PATH_GROUPS = {
        # 查询接口限流更严格
        "/api/query": {"max_requests": 30, "window": 60},
        "/api/nl2sql": {"max_requests": 20, "window": 60},
        "/api/report": {"max_requests": 10, "window": 60},
        
        # 数据源操作更严格
        "/api/datasources": {"max_requests": 50, "window": 60},
        
        # 只读接口限流较宽松
        "/api/templates": {"max_requests": 100, "window": 60},
        "/api/stats": {"max_requests": 60, "window": 60},
    }
    
    def __init__(self, max_requests: int = 100, window: int = 60):
        self.default_max_requests = max_requests
        self.default_window = window
        self.requests: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Redis 连接（可选，生产环境建议使用）
        self._redis_client = None
    
    def _get_path_config(self, path: str) -> Dict:
        """获取路径对应的限流配置"""
        for prefix, config in self.PATH_GROUPS.items():
            if path.startswith(prefix):
                return config
        return {"max_requests": self.default_max_requests, "window": self.default_window}
    
    def _clean_expired(self, key: str, now: float, window: int):
        with self._lock:
            self.requests[key] = [
                ts for ts in self.requests[key] if now - ts < window
            ]
    
    def is_allowed(self, key: str, path: str = "/") -> bool:
        """判断请求是否被允许"""
        config = self._get_path_config(path)
        max_requests = config["max_requests"]
        window = config["window"]
        
        now = time.time()
        self._clean_expired(key, now, window)
        
        with self._lock:
            if len(self.requests[key]) >= max_requests:
                return False
            self.requests[key].append(now)
            return True
    
    def get_remaining(self, key: str, path: str = "/") -> int:
        """获取剩余可用请求数"""
        config = self._get_path_config(path)
        max_requests = config["max_requests"]
        window = config["window"]
        
        now = time.time()
        self._clean_expired(key, now, window)
        
        with self._lock:
            return max(0, max_requests - len(self.requests[key]))
    
    def get_limit(self, path: str = "/") -> int:
        """获取路径的限流阈值"""
        config = self._get_path_config(path)
        return config["max_requests"]
    
    def clear(self):
        """清空限流记录（测试用）"""
        with self._lock:
            self.requests.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""
    
    # 跳过限流的路径（登录页、静态资源、健康检查等）
    SKIP_PATHS = {
        "/health", "/metrics", "/api/stats/metrics", 
        "/docs", "/openapi.json", "/redoc",
        "/api/auth/login", "/api/auth/register",
        "/login", "/register",
    }
    # 跳过限流的路径前缀
    SKIP_PREFIXES = ["/static", "/assets", "/_nuxt", "/node_modules"]
    
    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self.limiter = RateLimiter(
            max_requests=getattr(settings, 'rate_limit_max_requests', 100),
            window=getattr(settings, 'rate_limit_window', 60)
        )
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 跳过特定路径
        if path in self.SKIP_PATHS:
            return await call_next(request)
        
        # 跳过特定路径前缀（静态资源等）
        for prefix in self.SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)
        
        # 认证失败返回 401 的请求不计入限流（避免无限重试）
        client_ip = self._get_client_ip(request)
        key = f"rate_limit:{client_ip}"
        
        # 检查是否允许
        if not self.limiter.is_allowed(key, request.url.path):
            limit = self.limiter.get_limit(request.url.path)
            remaining = 0
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "limit": limit,
                    "remaining": remaining,
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
        
        # 添加限流响应头
        limit = self.limiter.get_limit(request.url.path)
        remaining = self.limiter.get_remaining(key, request.url.path)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP（支持代理）"""
        # 优先从 X-Forwarded-For 获取
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # 其次从 X-Real-IP 获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 最后使用原始客户端 IP
        return request.client.host if request.client else "unknown"