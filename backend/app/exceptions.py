"""自定义异常类"""

from typing import Optional, Any


class BaseAppException(Exception):
    """应用基础异常"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[dict] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BaseAppException):
    """验证错误"""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details
        )


class AuthenticationError(BaseAppException):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败", details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            details=details
        )


class AuthorizationError(BaseAppException):
    """授权错误"""
    
    def __init__(self, message: str = "权限不足", details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            details=details
        )


class NotFoundError(BaseAppException):
    """资源未找到错误"""
    
    def __init__(self, message: str = "资源不存在", details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND_ERROR",
            details=details
        )


class ConflictError(BaseAppException):
    """冲突错误"""
    
    def __init__(self, message: str = "资源冲突", details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT_ERROR",
            details=details
        )


class BusinessError(BaseAppException):
    """业务逻辑错误"""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="BUSINESS_ERROR",
            details=details
        )


class ExternalServiceError(BaseAppException):
    """外部服务错误"""
    
    def __init__(
        self,
        message: str = "外部服务调用失败",
        service_name: Optional[str] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        if service_name:
            details["service_name"] = service_name
        
        super().__init__(
            message=message,
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details
        )


class DatabaseError(BaseAppException):
    """数据库错误"""
    
    def __init__(self, message: str = "数据库操作失败", details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATABASE_ERROR",
            details=details
        )


class RateLimitError(BaseAppException):
    """限流错误"""
    
    def __init__(
        self,
        message: str = "请求过于频繁",
        retry_after: Optional[int] = None,
        details: Optional[dict] = None
    ):
        details = details or {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_ERROR",
            details=details
        )


class ConfigurationError(BaseAppException):
    """配置错误"""
    
    def __init__(self, message: str = "配置错误", details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="CONFIGURATION_ERROR",
            details=details
        )
