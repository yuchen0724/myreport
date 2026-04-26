"""错误响应模型"""

from pydantic import BaseModel, Field, field_serializer
from typing import Optional, Dict, Any
from datetime import datetime


class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = Field(None, description="错误字段")
    message: str = Field(..., description="错误消息")
    type: Optional[str] = Field(None, description="错误类型")


class ErrorResponse(BaseModel):
    """统一错误响应"""
    success: bool = Field(False, description="请求是否成功")
    error_code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    errors: Optional[list[ErrorDetail]] = Field(None, description="错误列表")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    path: Optional[str] = Field(None, description="请求路径")
    request_id: Optional[str] = Field(None, description="请求ID")
    
    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime) -> str:
        """序列化时间戳"""
        return value.isoformat()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ValidationErrorResponse(ErrorResponse):
    """验证错误响应"""
    error_code: str = Field("VALIDATION_ERROR", description="错误代码")
    errors: list[ErrorDetail] = Field(..., description="错误列表")


class AuthenticationErrorResponse(ErrorResponse):
    """认证错误响应"""
    error_code: str = Field("AUTHENTICATION_ERROR", description="错误代码")


class AuthorizationErrorResponse(ErrorResponse):
    """授权错误响应"""
    error_code: str = Field("AUTHORIZATION_ERROR", description="错误代码")


class NotFoundErrorResponse(ErrorResponse):
    """资源未找到错误响应"""
    error_code: str = Field("NOT_FOUND_ERROR", description="错误代码")


class ConflictErrorResponse(ErrorResponse):
    """冲突错误响应"""
    error_code: str = Field("CONFLICT_ERROR", description="错误代码")


class BusinessErrorResponse(ErrorResponse):
    """业务错误响应"""
    error_code: str = Field("BUSINESS_ERROR", description="错误代码")


class ExternalServiceErrorResponse(ErrorResponse):
    """外部服务错误响应"""
    error_code: str = Field("EXTERNAL_SERVICE_ERROR", description="错误代码")
    service_name: Optional[str] = Field(None, description="服务名称")


class DatabaseErrorResponse(ErrorResponse):
    """数据库错误响应"""
    error_code: str = Field("DATABASE_ERROR", description="错误代码")


class RateLimitErrorResponse(ErrorResponse):
    """限流错误响应"""
    error_code: str = Field("RATE_LIMIT_ERROR", description="错误代码")
    retry_after: Optional[int] = Field(None, description="重试时间（秒）")


class InternalErrorResponse(ErrorResponse):
    """内部错误响应"""
    error_code: str = Field("INTERNAL_ERROR", description="错误代码")
