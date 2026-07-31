"""错误处理测试"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
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
from app.utils.error_handler import ErrorHandler


def test_validation_error_response(client, auth_headers):
    """测试验证错误响应"""
    # 测试验证错误
    response = client.post(
        "/api/templates",
        headers=auth_headers,
        json={
            # 缺少必填字段
            "description": "测试"
        }
    )
    
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "errors" in data


def test_authentication_error_response(client):
    """测试认证错误响应"""
    response = client.get("/api/templates")
    
    assert response.status_code == 401
    data = response.json()
    assert data["error_code"] in ["AUTHENTICATION_ERROR", "HTTP_ERROR"]


def test_not_found_error_response(client, auth_headers):
    """测试资源未找到错误响应"""
    response = client.get("/api/templates/999999", headers=auth_headers)
    
    assert response.status_code == 404
    data = response.json()
    # HTTP异常处理器会返回HTTP_ERROR，这是正常行为
    assert data["error_code"] in ["NOT_FOUND_ERROR", "HTTP_ERROR"]
    assert "Template not found" in data["message"] or "不存在" in data["message"]


def test_custom_exception_handler():
    """测试自定义异常处理器"""
    from app.middleware.error_handler import base_app_exception_handler
    from fastapi import Request
    
    # 创建测试异常
    exc = ValidationError("测试验证错误", {"field": "test"})
    
    # 创建模拟请求
    request = Request({
        "type": "http",
        "method": "POST",
        "url": "http://test.com/api/test",
        "headers": {},
        "query_string": b"",
        "path": "/api/test"
    })
    
    # 测试异常处理器
    import asyncio
    
    async def test_handler():
        response = await base_app_exception_handler(request, exc)
        assert response.status_code == 400
        data = response.body.decode()
        assert "VALIDATION_ERROR" in data
        assert "测试验证错误" in data
    
    asyncio.run(test_handler())


def test_error_handler_utility():
    """测试错误处理工具类"""
    
    # 测试验证错误
    with pytest.raises(ValidationError) as exc_info:
        ErrorHandler.raise_validation_error("测试错误", "test_field")
    assert exc_info.value.message == "测试错误"
    assert exc_info.value.details["field"] == "test_field"
    
    # 测试认证错误
    with pytest.raises(AuthenticationError) as exc_info:
        ErrorHandler.raise_authentication_error("认证失败")
    assert exc_info.value.message == "认证失败"
    
    # 测试授权错误
    with pytest.raises(AuthorizationError) as exc_info:
        ErrorHandler.raise_authorization_error("权限不足")
    assert exc_info.value.message == "权限不足"
    
    # 测试资源未找到错误
    with pytest.raises(NotFoundError) as exc_info:
        ErrorHandler.raise_not_found_error("模板", 123)
    assert "模板" in exc_info.value.message
    assert exc_info.value.details["resource"] == "模板"
    assert exc_info.value.details["resource_id"] == "123"
    
    # 测试冲突错误
    with pytest.raises(ConflictError) as exc_info:
        ErrorHandler.raise_conflict_error("资源冲突")
    assert exc_info.value.message == "资源冲突"
    
    # 测试业务错误
    with pytest.raises(BusinessError) as exc_info:
        ErrorHandler.raise_business_error("业务逻辑错误")
    assert exc_info.value.message == "业务逻辑错误"
    
    # 测试外部服务错误
    with pytest.raises(ExternalServiceError) as exc_info:
        ErrorHandler.raise_external_service_error("测试服务", "服务调用失败")
    assert exc_info.value.message == "服务调用失败"
    assert exc_info.value.details["service_name"] == "测试服务"
    
    # 测试数据库错误
    with pytest.raises(DatabaseError) as exc_info:
        ErrorHandler.raise_database_error("数据库错误")
    assert exc_info.value.message == "数据库错误"
    
    # 测试限流错误
    with pytest.raises(RateLimitError) as exc_info:
        ErrorHandler.raise_rate_limit_error(retry_after=60)
    assert exc_info.value.details["retry_after"] == 60
    
    # 测试配置错误
    with pytest.raises(ConfigurationError) as exc_info:
        ErrorHandler.raise_configuration_error("配置错误")
    assert exc_info.value.message == "配置错误"


def test_validate_required_fields():
    """测试必填字段验证"""
    from app.utils.error_handler import validate_required_fields
    
    # 正常情况
    validate_required_fields({"name": "test", "value": 123}, ["name", "value"])
    
    # 缺少字段
    with pytest.raises(ValidationError):
        validate_required_fields({"name": "test"}, ["name", "value"])


def test_validate_field_type():
    """测试字段类型验证"""
    from app.utils.error_handler import validate_field_type
    
    # 正常情况
    validate_field_type({"name": "test"}, "name", str)
    
    # 类型错误
    with pytest.raises(ValidationError):
        validate_field_type({"name": 123}, "name", str)


def test_validate_field_length():
    """测试字段长度验证"""
    from app.utils.error_handler import validate_field_length
    
    # 正常情况
    validate_field_length({"name": "test"}, "name", min_length=2, max_length=10)
    
    # 长度不足
    with pytest.raises(ValidationError):
        validate_field_length({"name": "t"}, "name", min_length=2)
    
    # 长度超限
    with pytest.raises(ValidationError):
        validate_field_length({"name": "testtesttesttest"}, "name", max_length=10)


def test_validate_field_range():
    """测试字段范围验证"""
    from app.utils.error_handler import validate_field_range
    
    # 正常情况
    validate_field_range({"value": 5}, "value", min_value=0, max_value=10)
    
    # 值过小
    with pytest.raises(ValidationError):
        validate_field_range({"value": -1}, "value", min_value=0)
    
    # 值过大
    with pytest.raises(ValidationError):
        validate_field_range({"value": 11}, "value", max_value=10)


def test_error_response_structure():
    """测试错误响应结构"""
    from app.schemas.error import ErrorResponse, ErrorDetail
    
    # 测试基本错误响应
    error_response = ErrorResponse(
        error_code="TEST_ERROR",
        message="测试错误",
        path="/api/test",
        request_id="test-123"
    )
    
    assert error_response.success is False
    assert error_response.error_code == "TEST_ERROR"
    assert error_response.message == "测试错误"
    assert error_response.path == "/api/test"
    assert error_response.request_id == "test-123"
    
    # 测试带详情的错误响应
    error_response_with_details = ErrorResponse(
        error_code="TEST_ERROR",
        message="测试错误",
        details={"field": "test"},
        errors=[
            ErrorDetail(field="name", message="名称不能为空", type="required")
        ]
    )
    
    assert error_response_with_details.details is not None
    assert error_response_with_details.errors is not None
    assert len(error_response_with_details.errors) == 1
    assert error_response_with_details.errors[0].field == "name"
