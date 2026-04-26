# API集成测试文档

## 测试框架

本项目使用pytest作为测试框架，httpx用于HTTP客户端测试。

## 运行测试

### 运行所有测试
```bash
cd backend
pytest
```

### 运行特定测试文件
```bash
pytest tests/test_auth_api.py
```

### 运行特定测试用例
```bash
pytest tests/test_template_api.py::test_create_template
```

### 生成覆盖率报告
```bash
pytest --cov=app --cov-report=html
```

## 测试结构

- `conftest.py` - 测试配置和fixtures
- `test_auth_api.py` - 认证API测试
- `test_template_api.py` - 模板API测试
- `test_query_api.py` - 查询API测试
- `test_api_integration.py` - 集成测试

## 编写测试

### 基本测试结构
```python
def test_feature_name(client, auth_headers):
    """测试功能描述"""
    # 准备测试数据
    # 执行测试操作
    # 验证结果
    assert response.status_code == 200
    assert response.json()["expected_field"] == "expected_value"
```

### 使用Fixtures
```python
def test_with_user(client, auth_headers, test_user):
    """使用测试用户"""
    assert test_user.username == "testuser"
```

## 测试覆盖率目标

- API集成测试覆盖率 > 80%
- 核心业务逻辑覆盖率 > 90%
- 关键路径覆盖率 = 100%
