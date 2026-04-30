"""审计日志中间件"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.database import SessionLocal
from app.services.audit_log_service import AuditLogService
from app.core.auth_deps import get_current_user_id


class AuditLogMiddleware(BaseHTTPMiddleware):
    """审计日志中间件 - 自动记录API调用"""
    
    # 不需要审计的路径
    SKIP_PATHS = {
        "/health",
        "/",
        "/docs",
        "/openapi.json",
        "/api/auth/login",
        "/api/auth/me"
    }
    
    # 资源类型映射
    RESOURCE_TYPE_MAP = {
        "/api/templates": "template",
        "/api/query": "query",
        "/api/nl2sql": "nl2sql",
        "/api/data-sources": "data_source",
        "/api/users": "user",
        "/api/reports": "report",
        "/api/charts": "chart"
    }
    
    # 操作类型映射
    ACTION_MAP = {
        "GET": "VIEW",
        "POST": "CREATE",
        "PUT": "UPDATE",
        "DELETE": "DELETE",
        "PATCH": "UPDATE"
    }
    
    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 跳过不需要审计的路径
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        # 使用 SessionLocal 直接创建会话（避免 next(get_db()) 问题）
        db = SessionLocal()
        
        try:
            # 获取用户ID
            user_id = None
            try:
                user_id = await get_current_user_id(
                    request.headers.get("authorization", "").replace("Bearer ", ""),
                    db
                )
            except:
                # 未认证用户
                pass
            
            # 执行请求
            response = await call_next(request)
            
            # 确定资源类型和操作类型
            resource_type = self._get_resource_type(request.url.path)
            action = self._get_action_type(request.method)
            
            # 提取资源ID
            resource_id = self._extract_resource_id(request.url.path)
            
            # 记录审计日志
            if user_id and resource_type and action:
                audit_service = AuditLogService(db)
                audit_service.create_log(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "query_params": str(request.query_params),
                        "status_code": response.status_code
                    },
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    status="success" if response.status_code < 400 else "failure"
                )
            
            return response
        except Exception as e:
            # 记录错误
            if user_id:
                audit_service = AuditLogService(db)
                audit_service.create_log(
                    user_id=user_id,
                    action="ERROR",
                    resource_type="system",
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(e)
                    },
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    status="failure",
                    error_message=str(e)
                )
            raise
        finally:
            db.close()
    
    def _get_resource_type(self, path: str) -> str:
        """获取资源类型"""
        for prefix, resource_type in self.RESOURCE_TYPE_MAP.items():
            if path.startswith(prefix):
                return resource_type
        return "unknown"
    
    def _get_action_type(self, method: str) -> str:
        """获取操作类型"""
        return self.ACTION_MAP.get(method, "UNKNOWN")
    
    def _extract_resource_id(self, path: str) -> str:
        """从路径中提取资源ID"""
        parts = path.split("/")
        # 尝试获取最后一个数字部分作为ID
        for part in reversed(parts):
            if part.isdigit():
                return part
        return None
