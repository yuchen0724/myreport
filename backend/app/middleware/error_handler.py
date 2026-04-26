"""错误处理中间件"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
import traceback
import uuid
from typing import Union
from app.exceptions import (
    BaseAppException,
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
from app.schemas.error import ErrorResponse, ErrorDetail

logger = logging.getLogger(__name__)


async def base_app_exception_handler(
    request: Request,
    exc: BaseAppException
) -> JSONResponse:
    """处理应用自定义异常"""
    request_id = str(uuid.uuid4())
    
    # 记录错误日志
    logger.error(
        f"Request ID: {request_id} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Error Code: {exc.error_code} | "
        f"Message: {exc.message} | "
        f"Details: {exc.details}"
    )
    
    # 构建错误响应
    error_response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        path=request.url.path,
        request_id=request_id
    )
    
    # 添加重试时间头（如果是限流错误）
    headers = {}
    if isinstance(exc, RateLimitError) and exc.details.get("retry_after"):
        headers["Retry-After"] = str(exc.details["retry_after"])
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict(),
        headers=headers
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """处理请求验证异常"""
    request_id = str(uuid.uuid4())
    
    # 记录错误日志
    logger.warning(
        f"Request ID: {request_id} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Validation Error: {exc.errors()}"
    )
    
    # 构建错误详情
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append(
            ErrorDetail(
                field=field,
                message=error["msg"],
                type=error["type"]
            )
        )
    
    # 构建错误响应
    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="请求参数验证失败",
        errors=errors,
        path=request.url.path,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.dict()
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """处理HTTP异常"""
    request_id = str(uuid.uuid4())
    
    # 记录错误日志
    logger.warning(
        f"Request ID: {request_id} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"HTTP Error: {exc.status_code} | "
        f"Detail: {exc.detail}"
    )
    
    # 构建错误响应
    error_response = ErrorResponse(
        error_code="HTTP_ERROR",
        message=exc.detail or "HTTP错误",
        path=request.url.path,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict()
    )


async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """处理SQLAlchemy异常"""
    request_id = str(uuid.uuid4())
    
    # 记录错误日志
    logger.error(
        f"Request ID: {request_id} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Database Error: {str(exc)} | "
        f"Traceback: {traceback.format_exc()}"
    )
    
    # 判断错误类型
    if isinstance(exc, IntegrityError):
        message = "数据完整性错误，可能存在重复数据或外键约束"
        error_code = "INTEGRITY_ERROR"
    else:
        message = "数据库操作失败"
        error_code = "DATABASE_ERROR"
    
    # 构建错误响应
    error_response = ErrorResponse(
        error_code=error_code,
        message=message,
        details={"original_error": str(exc)} if logger.level == logging.DEBUG else None,
        path=request.url.path,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.dict()
    )


async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """处理未捕获的异常"""
    request_id = str(uuid.uuid4())
    
    # 记录错误日志
    logger.error(
        f"Request ID: {request_id} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Unhandled Exception: {str(exc)} | "
        f"Traceback: {traceback.format_exc()}"
    )
    
    # 构建错误响应
    error_response = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="服务器内部错误",
        details={"original_error": str(exc)} if logger.level == logging.DEBUG else None,
        path=request.url.path,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.dict()
    )


def register_exception_handlers(app):
    """注册所有异常处理器"""
    
    # 自定义应用异常
    app.add_exception_handler(BaseAppException, base_app_exception_handler)
    
    # FastAPI验证异常
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # HTTP异常
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # SQLAlchemy异常
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    
    # 通用异常
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("所有异常处理器已注册")
