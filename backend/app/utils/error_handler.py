"""错误处理工具类"""

from typing import Optional, Dict, Any, List
from functools import wraps
from fastapi import HTTPException, status
from app.exceptions import (
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    BusinessError,
    ExternalServiceError,
    DatabaseError,
    RateLimitError,
    ConfigurationError
)
import logging

logger = logging.getLogger(__name__)


class ErrorHandler:
    """错误处理工具类"""
    
    @staticmethod
    def raise_validation_error(
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出验证错误"""
        error_details = details or {}
        if field:
            error_details["field"] = field
        raise ValidationError(message, error_details)
    
    @staticmethod
    def raise_authentication_error(
        message: str = "认证失败",
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出认证错误"""
        raise AuthenticationError(message, details)
    
    @staticmethod
    def raise_authorization_error(
        message: str = "权限不足",
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出授权错误"""
        raise AuthorizationError(message, details)
    
    @staticmethod
    def raise_not_found_error(
        resource: str,
        resource_id: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出资源未找到错误"""
        message = f"{resource}不存在"
        if resource_id:
            message = f"{resource}(ID: {resource_id})不存在"
        
        error_details = details or {}
        error_details["resource"] = resource
        if resource_id:
            error_details["resource_id"] = str(resource_id)
        
        raise NotFoundError(message, error_details)
    
    @staticmethod
    def raise_conflict_error(
        message: str = "资源冲突",
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出冲突错误"""
        raise ConflictError(message, details)
    
    @staticmethod
    def raise_business_error(
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出业务错误"""
        raise BusinessError(message, details)
    
    @staticmethod
    def raise_external_service_error(
        service_name: str,
        message: str = "外部服务调用失败",
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出外部服务错误"""
        raise ExternalServiceError(message, service_name, details)
    
    @staticmethod
    def raise_database_error(
        message: str = "数据库操作失败",
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出数据库错误"""
        raise DatabaseError(message, details)
    
    @staticmethod
    def raise_rate_limit_error(
        retry_after: Optional[int] = None,
        message: str = "请求过于频繁",
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出限流错误"""
        raise RateLimitError(message, retry_after, details)
    
    @staticmethod
    def raise_configuration_error(
        message: str = "配置错误",
        details: Optional[Dict[str, Any]] = None
    ):
        """抛出配置错误"""
        raise ConfigurationError(message, details)


def handle_errors(error_handler: Optional[ErrorHandler] = None):
    """错误处理装饰器"""
    
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 如果是自定义异常，直接抛出
                if isinstance(e, (ValidationError, AuthenticationError, 
                                AuthorizationError, NotFoundError,
                                ConflictError, BusinessError,
                                ExternalServiceError, DatabaseError,
                                RateLimitError, ConfigurationError)):
                    raise
                
                # 其他异常记录日志后重新抛出
                logger.error(f"未处理的异常在 {func.__name__}: {str(e)}", 
                           exc_info=True)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 如果是自定义异常，直接抛出
                if isinstance(e, (ValidationError, AuthenticationError, 
                                AuthorizationError, NotFoundError,
                                ConflictError, BusinessError,
                                ExternalServiceError, DatabaseError,
                                RateLimitError, ConfigurationError)):
                    raise
                
                # 其他异常记录日志后重新抛出
                logger.error(f"未处理的异常在 {func.__name__}: {str(e)}", 
                           exc_info=True)
                raise
        
        # 根据函数类型返回对应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]):
    """验证必填字段"""
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        ErrorHandler.raise_validation_error(
            message=f"缺少必填字段: {', '.join(missing_fields)}",
            details={"missing_fields": missing_fields}
        )


def validate_field_type(data: Dict[str, Any], field: str, expected_type: type, field_name: Optional[str] = None):
    """验证字段类型"""
    if field in data and data[field] is not None:
        if not isinstance(data[field], expected_type):
            ErrorHandler.raise_validation_error(
                message=f"字段 '{field_name or field}' 类型错误，期望 {expected_type.__name__}",
                field=field,
                details={
                    "field": field,
                    "expected_type": expected_type.__name__,
                    "actual_type": type(data[field]).__name__
                }
            )


def validate_field_length(data: Dict[str, Any], field: str, min_length: Optional[int] = None, max_length: Optional[int] = None, field_name: Optional[str] = None):
    """验证字段长度"""
    if field in data and data[field] is not None:
        value = data[field]
        if not isinstance(value, (str, list)):
            return
        
        length = len(value)
        
        if min_length is not None and length < min_length:
            ErrorHandler.raise_validation_error(
                message=f"字段 '{field_name or field}' 长度不能少于 {min_length}",
                field=field,
                details={
                    "field": field,
                    "min_length": min_length,
                    "actual_length": length
                }
            )
        
        if max_length is not None and length > max_length:
            ErrorHandler.raise_validation_error(
                message=f"字段 '{field_name or field}' 长度不能超过 {max_length}",
                field=field,
                details={
                    "field": field,
                    "max_length": max_length,
                    "actual_length": length
                }
            )


def validate_field_range(data: Dict[str, Any], field: str, min_value: Optional[float] = None, max_value: Optional[float] = None, field_name: Optional[str] = None):
    """验证字段范围"""
    if field in data and data[field] is not None:
        value = data[field]
        if not isinstance(value, (int, float)):
            return
        
        if min_value is not None and value < min_value:
            ErrorHandler.raise_validation_error(
                message=f"字段 '{field_name or field}' 值不能小于 {min_value}",
                field=field,
                details={
                    "field": field,
                    "min_value": min_value,
                    "actual_value": value
                }
            )
        
        if max_value is not None and value > max_value:
            ErrorHandler.raise_validation_error(
                message=f"字段 '{field_name or field}' 值不能大于 {max_value}",
                field=field,
                details={
                    "field": field,
                    "max_value": max_value,
                    "actual_value": value
                }
            )
