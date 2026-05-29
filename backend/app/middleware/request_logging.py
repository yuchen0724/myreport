"""
请求日志和性能监控中间件
"""
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.structured_logger import request_id_var, app_logger
from app.utils.metrics import metrics_collector
from app.utils.sensitive_masker import masker


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志和性能监控中间件"""
    
    # 跳过日志的路径
    SKIP_PATHS = {"/health", "/health/live", "/health/ready", "/metrics", "/api/stats/metrics"}
    
    # 需要脱敏的响应字段
    MASK_FIELDS = {"password", "token", "secret", "api_key"}
    
    async def dispatch(self, request: Request, call_next):
        # 生成请求ID
        request_id = str(uuid.uuid4())[:8]
        request_id_var.set(request_id)
        request.state.request_id = request_id
        
        # 记录请求开始
        start_time = time.time()
        
        # 继续处理请求
        response = await call_next(request)
        
        # 计算耗时
        process_time = (time.time() - start_time) * 1000
        
        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        # 记录性能指标
        if request.url.path not in self.SKIP_PATHS:
            metrics_collector.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=process_time
            )
            
            # 构建日志（脱敏处理）
            log_extra = {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time_ms": round(process_time, 2),
                "client_ip": request.client.host if request.client else "unknown",
            }
            
            # 脱敏查询参数
            if request.query_params:
                masked_params = masker.mask_dict(dict(request.query_params))
                log_extra["query_params"] = masked_params
            
            # 记录日志
            app_logger.info(
                f"{request.method} {request.url.path}",
                **log_extra
            )
        
        return response
