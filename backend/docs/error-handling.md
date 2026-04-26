# 错误处理机制

## 概述

本系统实现了完整的错误处理机制，包括自定义异常类、统一错误响应、异常处理器和错误处理工具类，确保所有错误都能被正确捕获、记录和返回给客户端。

## 功能特性

### 1. 自定义异常类

系统定义了多种自定义异常类，用于不同类型的错误：

- **BaseAppException**: 应用基础异常
- **ValidationError**: 验证错误 (400)
- **AuthenticationError**: 认证错误 (401)
- **AuthorizationError**: 授权错误 (403)
- **NotFoundError**: 资源未找到错误 (404)
- **ConflictError**: 冲突错误 (409)
- **BusinessError**: 业务逻辑错误 (400)
- **ExternalServiceError**: 外部服务错误 (502)
- **DatabaseError**: 数据库错误 (500)
- **RateLimitError**: 限流错误 (429)
- **ConfigurationError**: 配置错误 (500)

### 2. 统一错误响应

所有错误都返回统一的响应格式：

```json
{
  "success": false,
  "error_code": "ERROR_CODE",
  "message": "错误消息",
  "details": {},
  "errors": [],
  "timestamp": "2024-01-01T00:00:00",
  "path": "/api/endpoint",
  "request_id": "uuid"
}
```

### 3. 异常处理器

系统注册了多种异常处理器：

- **自定义应用异常处理器**: 处理所有自定义异常
- **验证异常处理器**: 处理请求验证错误
- **HTTP异常处理器**: 处理HTTP异常
- **SQLAlchemy异常处理器**: 处理数据库异常
- **通用异常处理器**: 处理未捕获的异常

### 4. 错误处理工具类

提供便捷的错误处理方法：

```python
from app.utils.error_handler import ErrorHandler

# 抛出验证错误
ErrorHandler.raise_validation_error("字段不能为空", field="name")

# 抛出资源未找到错误
ErrorHandler.raise_not_found_error("模板", 123)

# 抛出业务错误
ErrorHandler.raise_business_error("业务逻辑错误")
```

### 5. 验证工具

提供字段验证工具：

```python
from app.utils.error_handler import (
    validate_required_fields,
    validate_field_type,
    validate_field_length,
    validate_field_range
)

# 验证必填字段
validate_required_fields(data, ["name", "value"])

# 验证字段类型
validate_field_type(data, "age", int)

# 验证字段长度
validate_field_length(data, "name", min_length=2, max_length=50)

# 验证字段范围
validate_field_range(data, "age", min_value=0, max_value=120)
```

## 使用示例

### 在服务层使用自定义异常

```python
from app.exceptions import NotFoundError, BusinessError
from app.utils.error_handler import ErrorHandler

class TemplateService:
    def get_template(self, template_id: int):
        template = self.template_repo.get_by_id(template_id)
        if not template:
            ErrorHandler.raise_not_found_error("模板", template_id)
        return template
    
    def create_template(self, data: dict):
        if self.template_repo.exists_by_name(data["name"]):
            ErrorHandler.raise_conflict_error("模板名称已存在")
        return self.template_repo.create(data)
```

### 在API层使用错误处理

```python
from fastapi import APIRouter, Depends
from app.exceptions import ValidationError
from app.utils.error_handler import validate_required_fields

router = APIRouter()

@router.post("/templates/")
def create_template(
    data: dict,
    current_user_id: int = Depends(get_current_user_id)
):
    # 验证必填字段
    validate_required_fields(data, ["name", "sql"])
    
    # 验证字段长度
    validate_field_length(data, "name", min_length=1, max_length=100)
    
    # 创建模板
    template = template_service.create_template(data, current_user_id)
    return template
```

### 使用错误处理装饰器

```python
from app.utils.error_handler import handle_errors

@handle_errors()
async def some_function():
    # 函数逻辑
    pass
```

## 错误代码规范

错误代码采用大写字母和下划线的命名规范：

- `VALIDATION_ERROR`: 验证错误
- `AUTHENTICATION_ERROR`: 认证错误
- `AUTHORIZATION_ERROR`: 授权错误
- `NOT_FOUND_ERROR`: 资源未找到错误
- `CONFLICT_ERROR`: 冲突错误
- `BUSINESS_ERROR`: 业务错误
- `EXTERNAL_SERVICE_ERROR`: 外部服务错误
- `DATABASE_ERROR`: 数据库错误
- `RATE_LIMIT_ERROR`: 限流错误
- `CONFIGURATION_ERROR`: 配置错误
- `INTERNAL_ERROR`: 内部错误

## 日志记录

所有错误都会被记录到日志中，包括：

- 请求ID
- 请求路径
- 请求方法
- 错误代码
- 错误消息
- 错误详情
- 堆栈跟踪（仅内部错误）

## 测试

系统包含完整的错误处理测试：

```bash
# 运行错误处理测试
pytest tests/test_error_handling.py -v
```

测试覆盖：
- 验证错误响应
- 认证错误响应
- 资源未找到错误响应
- 自定义异常处理器
- 错误处理工具类
- 字段验证工具
- 错误响应结构

## 最佳实践

1. **使用自定义异常**: 不要直接抛出HTTPException，使用自定义异常类
2. **提供详细错误信息**: 在details中提供更多上下文信息
3. **记录错误日志**: 确保所有错误都被正确记录
4. **统一错误响应**: 使用统一的错误响应格式
5. **验证输入数据**: 在处理前验证输入数据
6. **处理异常情况**: 考虑所有可能的异常情况
7. **提供有意义的错误消息**: 错误消息应该清晰、具体、可操作

## 扩展

### 添加新的异常类型

```python
# 在 app/exceptions.py 中添加
class NewCustomError(BaseAppException):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="NEW_CUSTOM_ERROR",
            details=details
        )
```

### 添加新的错误处理方法

```python
# 在 app/utils/error_handler.py 中添加
class ErrorHandler:
    @staticmethod
    def raise_new_custom_error(message: str, details: Optional[dict] = None):
        """抛出新自定义错误"""
        raise NewCustomError(message, details)
```

## 总结

本系统的错误处理机制提供了：

- ✅ 完整的自定义异常体系
- ✅ 统一的错误响应格式
- ✅ 全面的异常处理器
- ✅ 便捷的错误处理工具
- ✅ 完善的验证工具
- ✅ 详细的错误日志
- ✅ 完整的测试覆盖

通过这套错误处理机制，系统能够：
- 提供一致的用户体验
- 简化错误处理逻辑
- 提高代码可维护性
- 增强系统稳定性
- 便于问题排查和调试
