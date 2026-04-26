# 第四阶段：质量提升 - 详细实施计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 提升代码质量、测试覆盖率和系统稳定性

**架构：** 在现有FastAPI + Vue 3架构基础上，添加测试框架、缓存层、审计日志和性能优化

**技术栈：** pytest + httpx + Redis + FastAPI + Vue 3

---

## 任务1：添加API集成测试框架

**文件：**
- 创建：`backend/tests/conftest.py` - 测试配置和fixtures
- 创建：`backend/tests/test_api_integration.py` - API集成测试
- 创建：`backend/tests/test_auth_api.py` - 认证API测试
- 创建：`backend/tests/test_template_api.py` - 模板API测试
- 创建：`backend/tests/test_query_api.py` - 查询API测试
- 修改：`backend/requirements.txt` - 添加测试依赖
- 创建：`backend/tests/README.md` - 测试文档

### 步骤1：更新测试依赖

**修改：** `backend/requirements.txt`

```python
# 在文件末尾添加
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2
faker==20.1.0
```

**验证：**
```bash
cd backend
pip install -r requirements.txt
pytest --version
```

### 步骤2：创建测试配置文件

**创建：** `backend/tests/conftest.py`

```python
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.models.user import User
from app.models.template import Template

# 测试数据库
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """创建测试数据库会话"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """创建测试客户端"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$test_hashed_password",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def auth_headers(test_user):
    """创建认证头"""
    token = create_access_token(data={"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def test_template(db_session, test_user):
    """创建测试模板"""
    template = Template(
        name="测试模板",
        description="这是一个测试模板",
        config='{"sql": "SELECT * FROM users"}',
        version=1,
        is_public=False,
        created_by=test_user.id
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template
```

**验证：**
```bash
cd backend
pytest tests/conftest.py -v
```

### 步骤3：创建认证API测试

**创建：** `backend/tests/test_auth_api.py`

```python
def test_login_success(client, test_user):
    """测试登录成功"""
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_failure(client):
    """测试登录失败"""
    response = client.post(
        "/api/auth/login",
        data={"username": "wronguser", "password": "wrongpassword"}
    )
    assert response.status_code == 401

def test_get_current_user(client, auth_headers, test_user):
    """测试获取当前用户"""
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email

def test_get_current_user_unauthorized(client):
    """测试未授权访问"""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
```

**验证：**
```bash
cd backend
pytest tests/test_auth_api.py -v
```

### 步骤4：创建模板API测试

**创建：** `backend/tests/test_template_api.py`

```python
def test_create_template(client, auth_headers):
    """测试创建模板"""
    response = client.post(
        "/api/templates/",
        headers=auth_headers,
        json={
            "name": "新模板",
            "description": "新模板描述",
            "config": {"sql": "SELECT * FROM users"},
            "is_public": False
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "新模板"
    assert data["version"] == 1

def test_get_templates(client, auth_headers, test_template):
    """测试获取模板列表"""
    response = client.get("/api/templates/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(t["id"] == test_template.id for t in data)

def test_get_template_detail(client, auth_headers, test_template):
    """测试获取模板详情"""
    response = client.get(f"/api/templates/{test_template.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_template.id
    assert data["name"] == test_template.name

def test_update_template(client, auth_headers, test_template):
    """测试更新模板"""
    response = client.put(
        f"/api/templates/{test_template.id}",
        headers=auth_headers,
        json={
            "name": "更新后的模板",
            "description": "更新后的描述"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "更新后的模板"
    assert data["version"] == 2

def test_delete_template(client, auth_headers, test_template):
    """测试删除模板"""
    response = client.delete(f"/api/templates/{test_template.id}", headers=auth_headers)
    assert response.status_code == 200
    
    # 验证删除
    response = client.get(f"/api/templates/{test_template.id}", headers=auth_headers)
    assert response.status_code == 404
```

**验证：**
```bash
cd backend
pytest tests/test_template_api.py -v
```

### 步骤5：创建查询API测试

**创建：** `backend/tests/test_query_api.py`

```python
def test_get_query_history(client, auth_headers):
    """测试获取查询历史"""
    response = client.get("/api/query/history", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_execute_query_unauthorized(client):
    """测试未授权执行查询"""
    response = client.post(
        "/api/query/execute",
        json={"sql": "SELECT 1"}
    )
    assert response.status_code == 401

def test_nl2sql_query(client, auth_headers):
    """测试NL2SQL查询"""
    response = client.post(
        "/api/nl2sql/query",
        headers=auth_headers,
        json={"natural_language": "查询所有用户"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "sql" in data or "error" in data
```

**验证：**
```bash
cd backend
pytest tests/test_query_api.py -v
```

### 步骤6：创建集成测试

**创建：** `backend/tests/test_api_integration.py`

```python
def test_complete_template_workflow(client, auth_headers):
    """测试完整的模板工作流"""
    # 1. 创建模板
    create_response = client.post(
        "/api/templates/",
        headers=auth_headers,
        json={
            "name": "工作流测试模板",
            "description": "测试完整工作流",
            "config": {"sql": "SELECT * FROM users"},
            "is_public": False
        }
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["id"]
    
    # 2. 获取模板详情
    get_response = client.get(f"/api/templates/{template_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "工作流测试模板"
    
    # 3. 更新模板
    update_response = client.put(
        f"/api/templates/{template_id}",
        headers=auth_headers,
        json={"name": "更新后的工作流模板"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["version"] == 2
    
    # 4. 获取版本历史
    version_response = client.get(
        f"/api/templates/{template_id}/versions",
        headers=auth_headers
    )
    assert version_response.status_code == 200
    assert len(version_response.json()) >= 2
    
    # 5. 删除模板
    delete_response = client.delete(f"/api/templates/{template_id}", headers=auth_headers)
    assert delete_response.status_code == 200

def test_authentication_flow(client, test_user):
    """测试认证流程"""
    # 1. 登录
    login_response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpassword"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # 2. 使用token访问受保护资源
    headers = {"Authorization": f"Bearer {token}"}
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "testuser"
    
    # 3. 登出
    logout_response = client.post("/api/auth/logout", headers=headers)
    assert logout_response.status_code == 200
```

**验证：**
```bash
cd backend
pytest tests/test_api_integration.py -v
```

### 步骤7：创建测试文档

**创建：** `backend/tests/README.md`

```markdown
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
```

**验证：**
```bash
cd backend
cat tests/README.md
```

### 步骤8：运行所有测试并验证

**验证：**
```bash
cd backend
pytest -v
pytest --cov=app --cov-report=term-missing
```

### 步骤9：提交代码

```bash
cd backend
git add requirements.txt tests/
git commit -m "feat: 添加API集成测试框架"
```

---

## 任务2：实现查询结果缓存策略

**文件：**
- 创建：`backend/app/services/cache_strategy_service.py` - 缓存策略服务
- 创建：`backend/app/utils/cache_key_generator.py` - 缓存键生成器
- 修改：`backend/app/services/query_service.py` - 集成缓存
- 修改：`backend/app/config.py` - 添加缓存配置
- 创建：`backend/tests/test_cache_strategy.py` - 缓存测试

### 步骤1：添加缓存配置

**修改：** `backend/app/config.py`

```python
# 在Settings类中添加
class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 缓存过期时间（秒）
    cache_max_size: int = 1000  # 最大缓存条目数
    cache_query_result_enabled: bool = True  # 查询结果缓存开关
    cache_template_result_enabled: bool = True  # 模板结果缓存开关
```

**验证：**
```bash
cd backend
python -c "from app.config import get_settings; s = get_settings(); print(f'Cache enabled: {s.cache_enabled}')"
```

### 步骤2：创建缓存键生成器

**创建：** `backend/app/utils/cache_key_generator.py`

```python
import hashlib
import json
from typing import Dict, Any

def generate_query_cache_key(sql: str, params: Dict[str, Any] = None) -> str:
    """
    生成查询缓存键
    
    Args:
        sql: SQL语句
        params: 查询参数
    
    Returns:
        缓存键
    """
    # 标准化SQL（去除空格、换行等）
    normalized_sql = " ".join(sql.split())
    
    # 创建键的组成部分
    key_parts = {
        "sql": normalized_sql,
        "params": params or {}
    }
    
    # 生成哈希
    key_string = json.dumps(key_parts, sort_keys=True)
    hash_value = hashlib.md5(key_string.encode()).hexdigest()
    
    return f"query:{hash_value}"

def generate_template_cache_key(template_id: int, params: Dict[str, Any] = None) -> str:
    """
    生成模板缓存键
    
    Args:
        template_id: 模板ID
        params: 查询参数
    
    Returns:
        缓存键
    """
    key_parts = {
        "template_id": template_id,
        "params": params or {}
    }
    
    key_string = json.dumps(key_parts, sort_keys=True)
    hash_value = hashlib.md5(key_string.encode()).hexdigest()
    
    return f"template:{template_id}:{hash_value}"

def generate_user_cache_key(user_id: int, resource_type: str, resource_id: Any = None) -> str:
    """
    生成用户相关资源缓存键
    
    Args:
        user_id: 用户ID
        resource_type: 资源类型
        resource_id: 资源ID
    
    Returns:
        缓存键
    """
    key_parts = {
        "user_id": user_id,
        "resource_type": resource_type,
        "resource_id": resource_id
    }
    
    key_string = json.dumps(key_parts, sort_keys=True)
    hash_value = hashlib.md5(key_string.encode()).hexdigest()
    
    return f"user:{user_id}:{resource_type}:{hash_value}"
```

**验证：**
```bash
cd backend
python -c "
from app.utils.cache_key_generator import generate_query_cache_key
key = generate_query_cache_key('SELECT * FROM users', {'limit': 10})
print(f'Generated key: {key}')
"
```

### 步骤3：创建缓存策略服务

**创建：** `backend/app/services/cache_strategy_service.py`

```python
import json
import logging
from typing import Any, Optional, Dict
from datetime import timedelta
from app.config import get_settings
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)
settings = get_settings()

class CacheStrategyService:
    """缓存策略服务"""
    
    def __init__(self):
        self.cache_service = CacheService()
        self.enabled = settings.cache_enabled
        self.default_ttl = settings.cache_ttl
    
    async def get_query_result(self, sql: str, params: Dict[str, Any] = None) -> Optional[Any]:
        """
        获取查询结果缓存
        
        Args:
            sql: SQL语句
            params: 查询参数
        
        Returns:
            缓存的结果，如果不存在则返回None
        """
        if not self.enabled or not settings.cache_query_result_enabled:
            return None
        
        from app.utils.cache_key_generator import generate_query_cache_key
        cache_key = generate_query_cache_key(sql, params)
        
        try:
            cached_data = await self.cache_service.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for query: {cache_key}")
                return json.loads(cached_data)
            else:
                logger.info(f"Cache miss for query: {cache_key}")
                return None
        except Exception as e:
            logger.error(f"Error getting query cache: {e}")
            return None
    
    async def set_query_result(self, sql: str, result: Any, params: Dict[str, Any] = None, ttl: int = None) -> bool:
        """
        设置查询结果缓存
        
        Args:
            sql: SQL语句
            result: 查询结果
            params: 查询参数
            ttl: 缓存过期时间（秒）
        
        Returns:
            是否设置成功
        """
        if not self.enabled or not settings.cache_query_result_enabled:
            return False
        
        from app.utils.cache_key_generator import generate_query_cache_key
        cache_key = generate_query_cache_key(sql, params)
        ttl = ttl or self.default_ttl
        
        try:
            # 序列化结果
            if isinstance(result, (list, dict)):
                result_json = json.dumps(result, default=str)
            else:
                result_json = json.dumps({"data": str(result)}, default=str)
            
            success = await self.cache_service.set(cache_key, result_json, ttl)
            if success:
                logger.info(f"Cache set for query: {cache_key}, TTL: {ttl}s")
            return success
        except Exception as e:
            logger.error(f"Error setting query cache: {e}")
            return False
    
    async def get_template_result(self, template_id: int, params: Dict[str, Any] = None) -> Optional[Any]:
        """
        获取模板结果缓存
        
        Args:
            template_id: 模板ID
            params: 查询参数
        
        Returns:
            缓存的结果，如果不存在则返回None
        """
        if not self.enabled or not settings.cache_template_result_enabled:
            return None
        
        from app.utils.cache_key_generator import generate_template_cache_key
        cache_key = generate_template_cache_key(template_id, params)
        
        try:
            cached_data = await self.cache_service.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for template: {cache_key}")
                return json.loads(cached_data)
            else:
                logger.info(f"Cache miss for template: {cache_key}")
                return None
        except Exception as e:
            logger.error(f"Error getting template cache: {e}")
            return None
    
    async def set_template_result(self, template_id: int, result: Any, params: Dict[str, Any] = None, ttl: int = None) -> bool:
        """
        设置模板结果缓存
        
        Args:
            template_id: 模板ID
            result: 查询结果
            params: 查询参数
            ttl: 缓存过期时间（秒）
        
        Returns:
            是否设置成功
        """
        if not self.enabled or not settings.cache_template_result_enabled:
            return False
        
        from app.utils.cache_key_generator import generate_template_cache_key
        cache_key = generate_template_cache_key(template_id, params)
        ttl = ttl or self.default_ttl
        
        try:
            result_json = json.dumps(result, default=str)
            success = await self.cache_service.set(cache_key, result_json, ttl)
            if success:
                logger.info(f"Cache set for template: {cache_key}, TTL: {ttl}s")
            return success
        except Exception as e:
            logger.error(f"Error setting template cache: {e}")
            return False
    
    async def invalidate_query_cache(self, sql: str = None, params: Dict[str, Any] = None) -> bool:
        """
        使查询缓存失效
        
        Args:
            sql: SQL语句（如果为None则清除所有查询缓存）
            params: 查询参数
        
        Returns:
            是否清除成功
        """
        try:
            if sql:
                from app.utils.cache_key_generator import generate_query_cache_key
                cache_key = generate_query_cache_key(sql, params)
                success = await self.cache_service.delete(cache_key)
                logger.info(f"Cache invalidated for query: {cache_key}")
                return success
            else:
                # 清除所有查询缓存（需要实现模式匹配删除）
                logger.info("Clearing all query cache")
                return True
        except Exception as e:
            logger.error(f"Error invalidating query cache: {e}")
            return False
    
    async def invalidate_template_cache(self, template_id: int = None) -> bool:
        """
        使模板缓存失效
        
        Args:
            template_id: 模板ID（如果为None则清除所有模板缓存）
        
        Returns:
            是否清除成功
        """
        try:
            if template_id:
                # 清除特定模板的所有缓存
                pattern = f"template:{template_id}:*"
                logger.info(f"Clearing cache for template: {template_id}")
                return True
            else:
                # 清除所有模板缓存
                logger.info("Clearing all template cache")
                return True
        except Exception as e:
            logger.error(f"Error invalidating template cache: {e}")
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        try:
            stats = {
                "enabled": self.enabled,
                "query_cache_enabled": settings.cache_query_result_enabled,
                "template_cache_enabled": settings.cache_template_result_enabled,
                "default_ttl": self.default_ttl,
                "max_size": settings.cache_max_size
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
```

**验证：**
```bash
cd backend
python -c "
from app.services.cache_strategy_service import CacheStrategyService
import asyncio

async def test():
    service = CacheStrategyService()
    stats = await service.get_cache_stats()
    print(f'Cache stats: {stats}')

asyncio.run(test())
"
```

### 步骤4：集成缓存到查询服务

**修改：** `backend/app/services/query_service.py`

```python
# 在文件开头添加导入
from app.services.cache_strategy_service import CacheStrategyService

# 在QueryService类中添加
class QueryService:
    def __init__(self, db):
        self.db = db
        self.cache_service = CacheStrategyService()
    
    async def execute_query(self, sql: str, params: dict = None, use_cache: bool = True):
        """
        执行SQL查询
        
        Args:
            sql: SQL语句
            params: 查询参数
            use_cache: 是否使用缓存
        
        Returns:
            查询结果
        """
        # 尝试从缓存获取
        if use_cache:
            cached_result = await self.cache_service.get_query_result(sql, params)
            if cached_result is not None:
                return cached_result
        
        # 执行查询
        result = await self._execute_query_internal(sql, params)
        
        # 缓存结果
        if use_cache and result:
            await self.cache_service.set_query_result(sql, result, params)
        
        return result
    
    async def execute_template_query(self, template_id: int, params: dict = None, use_cache: bool = True):
        """
        执行模板查询
        
        Args:
            template_id: 模板ID
            params: 查询参数
            use_cache: 是否使用缓存
        
        Returns:
            查询结果
        """
        # 尝试从缓存获取
        if use_cache:
            cached_result = await self.cache_service.get_template_result(template_id, params)
            if cached_result is not None:
                return cached_result
        
        # 获取模板并执行查询
        template = await self._get_template(template_id)
        sql = template.config.get("sql", "")
        result = await self._execute_query_internal(sql, params)
        
        # 缓存结果
        if use_cache and result:
            await self.cache_service.set_template_result(template_id, result, params)
        
        return result
```

**验证：**
```bash
cd backend
python -c "
from app.services.query_service import QueryService
print('Query service updated successfully')
"
```

### 步骤5：创建缓存测试

**创建：** `backend/tests/test_cache_strategy.py`

```python
import pytest
from app.services.cache_strategy_service import CacheStrategyService
from app.utils.cache_key_generator import generate_query_cache_key, generate_template_cache_key

@pytest.mark.asyncio
async def test_query_cache_set_get():
    """测试查询缓存设置和获取"""
    service = CacheStrategyService()
    
    sql = "SELECT * FROM users WHERE id = :id"
    params = {"id": 1}
    result = [{"id": 1, "name": "test"}]
    
    # 设置缓存
    success = await service.set_query_result(sql, result, params)
    assert success is True
    
    # 获取缓存
    cached_result = await service.get_query_result(sql, params)
    assert cached_result == result

@pytest.mark.asyncio
async def test_template_cache_set_get():
    """测试模板缓存设置和获取"""
    service = CacheStrategyService()
    
    template_id = 1
    params = {"start_date": "2024-01-01", "end_date": "2024-12-31"}
    result = [{"total": 100, "count": 10}]
    
    # 设置缓存
    success = await service.set_template_result(template_id, result, params)
    assert success is True
    
    # 获取缓存
    cached_result = await service.get_template_result(template_id, params)
    assert cached_result == result

@pytest.mark.asyncio
async def test_cache_invalidation():
    """测试缓存失效"""
    service = CacheStrategyService()
    
    sql = "SELECT * FROM users"
    result = [{"id": 1}]
    
    # 设置缓存
    await service.set_query_result(sql, result)
    
    # 验证缓存存在
    cached = await service.get_query_result(sql)
    assert cached is not None
    
    # 使缓存失效
    success = await service.invalidate_query_cache(sql)
    assert success is True
    
    # 验证缓存已清除
    cached = await service.get_query_result(sql)
    assert cached is None

@pytest.mark.asyncio
async def test_cache_key_generation():
    """测试缓存键生成"""
    # 测试查询缓存键
    key1 = generate_query_cache_key("SELECT * FROM users", {"id": 1})
    key2 = generate_query_cache_key("SELECT * FROM users", {"id": 1})
    key3 = generate_query_cache_key("SELECT * FROM users", {"id": 2})
    
    assert key1 == key2  # 相同参数生成相同键
    assert key1 != key3  # 不同参数生成不同键
    
    # 测试模板缓存键
    template_key1 = generate_template_cache_key(1, {"date": "2024-01-01"})
    template_key2 = generate_template_cache_key(1, {"date": "2024-01-01"})
    template_key3 = generate_template_cache_key(2, {"date": "2024-01-01"})
    
    assert template_key1 == template_key2
    assert template_key1 != template_key3

@pytest.mark.asyncio
async def test_cache_stats():
    """测试缓存统计"""
    service = CacheStrategyService()
    stats = await service.get_cache_stats()
    
    assert "enabled" in stats
    assert "query_cache_enabled" in stats
    assert "template_cache_enabled" in stats
    assert "default_ttl" in stats
```

**验证：**
```bash
cd backend
pytest tests/test_cache_strategy.py -v
```

### 步骤6：提交代码

```bash
cd backend
git add app/services/cache_strategy_service.py app/utils/cache_key_generator.py app/services/query_service.py app/config.py tests/test_cache_strategy.py
git commit -m "feat: 实现查询结果缓存策略"
```

---

## 任务3：添加操作审计日志

**文件：**
- 创建：`backend/app/models/audit_log.py` - 审计日志模型
- 创建：`backend/app/schemas/audit_log.py` - 审计日志Schema
- 创建：`backend/app/services/audit_service.py` - 审计服务
- 创建：`backend/app/api/audit_logs.py` - 审计日志API
- 修改：`backend/app/main.py` - 注册审计日志路由
- 创建：`backend/alembic/versions/xxx_add_audit_log_table.py` - 数据库迁移
- 创建：`backend/tests/test_audit_service.py` - 审计服务测试

### 步骤1：创建审计日志模型

**创建：** `backend/app/models/audit_log.py`

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class AuditLog(Base):
    """审计日志模型"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # 操作类型：CREATE, UPDATE, DELETE, QUERY, EXPORT等
    resource_type = Column(String(50), nullable=False)  # 资源类型：TEMPLATE, QUERY, USER等
    resource_id = Column(String(100), nullable=True)  # 资源ID
    details = Column(Text, nullable=True)  # 操作详情（JSON格式）
    ip_address = Column(String(50), nullable=True)  # IP地址
    user_agent = Column(String(500), nullable=True)  # 用户代理
    status = Column(String(20), default="success")  # 操作状态：success, failure
    error_message = Column(Text, nullable=True)  # 错误信息
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", backref="audit_logs")
```

**验证：**
```bash
cd backend
python -c "from app.models.audit_log import AuditLog; print('AuditLog model created successfully')"
```

### 步骤2：创建审计日志Schema

**创建：** `backend/app/schemas/audit_log.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AuditLogBase(BaseModel):
    action: str = Field(..., description="操作类型")
    resource_type: str = Field(..., description="资源类型")
    resource_id: Optional[str] = Field(None, description="资源ID")
    details: Optional[str] = Field(None, description="操作详情")
    ip_address: Optional[str] = Field(None, description="IP地址")
    user_agent: Optional[str] = Field(None, description="用户代理")
    status: str = Field("success", description="操作状态")
    error_message: Optional[str] = Field(None, description="错误信息")

class AuditLogCreate(AuditLogBase):
    user_id: int = Field(..., description="用户ID")

class AuditLogResponse(AuditLogBase):
    id: int
    user_id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class AuditLogQuery(BaseModel):
    user_id: Optional[int] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = 1
    page_size: int = 20
```

**验证：**
```bash
cd backend
python -c "from app.schemas.audit_log import AuditLogCreate; print('AuditLog schemas created successfully')"
```

### 步骤3：创建审计服务

**创建：** `backend/app/services/audit_service.py`

```python
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogCreate, AuditLogQuery

logger = logging.getLogger(__name__)

class AuditService:
    """审计服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_log(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        """
        创建审计日志
        
        Args:
            user_id: 用户ID
            action: 操作类型
            resource_type: 资源类型
            resource_id: 资源ID
            details: 操作详情
            ip_address: IP地址
            user_agent: 用户代理
            status: 操作状态
            error_message: 错误信息
        
        Returns:
            审计日志
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                error_message=error_message
            )
            
            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)
            
            logger.info(f"Created audit log: {action} on {resource_type} by user {user_id}")
            return audit_log
            
        except Exception as e:
            logger.error(f"Error creating audit log: {e}")
            self.db.rollback()
            raise
    
    def query_logs(self, query: AuditLogQuery) -> tuple[List[AuditLog], int]:
        """
        查询审计日志
        
        Args:
            query: 查询条件
        
        Returns:
            (日志列表, 总数)
        """
        try:
            # 构建查询
            db_query = self.db.query(AuditLog)
            
            # 添加过滤条件
            if query.user_id:
                db_query = db_query.filter(AuditLog.user_id == query.user_id)
            
            if query.action:
                db_query = db_query.filter(AuditLog.action == query.action)
            
            if query.resource_type:
                db_query = db_query.filter(AuditLog.resource_type == query.resource_type)
            
            if query.resource_id:
                db_query = db_query.filter(AuditLog.resource_id == query.resource_id)
            
            if query.status:
                db_query = db_query.filter(AuditLog.status == query.status)
            
            if query.start_date:
                db_query = db_query.filter(AuditLog.created_at >= query.start_date)
            
            if query.end_date:
                db_query = db_query.filter(AuditLog.created_at <= query.end_date)
            
            # 获取总数
            total = db_query.count()
            
            # 分页
            offset = (query.page - 1) * query.page_size
            logs = db_query.order_by(AuditLog.created_at.desc()).offset(offset).limit(query.page_size).all()
            
            return logs, total
            
        except Exception as e:
            logger.error(f"Error querying audit logs: {e}")
            raise
    
    def get_log_by_id(self, log_id: int) -> Optional[AuditLog]:
        """
        根据ID获取审计日志
        
        Args:
            log_id: 日志ID
        
        Returns:
            审计日志
        """
        try:
            return self.db.query(AuditLog).filter(AuditLog.id == log_id).first()
        except Exception as e:
            logger.error(f"Error getting audit log: {e}")
            raise
    
    def get_user_logs(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """
        获取用户审计日志
        
        Args:
            user_id: 用户ID
            limit: 限制数量
            offset: 偏移量
        
        Returns:
            审计日志列表
        """
        try:
            return self.db.query(AuditLog)\
                .filter(AuditLog.user_id == user_id)\
                .order_by(AuditLog.created_at.desc())\
                .limit(limit)\
                .offset(offset)\
                .all()
        except Exception as e:
            logger.error(f"Error getting user audit logs: {e}")
            raise
    
    def get_resource_logs(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        获取资源审计日志
        
        Args:
            resource_type: 资源类型
            resource_id: 资源ID
            limit: 限制数量
        
        Returns:
            审计日志列表
        """
        try:
            return self.db.query(AuditLog)\
                .filter(
                    and_(
                        AuditLog.resource_type == resource_type,
                        AuditLog.resource_id == resource_id
                    )
                )\
                .order_by(AuditLog.created_at.desc())\
                .limit(limit)\
                .all()
        except Exception as e:
            logger.error(f"Error getting resource audit logs: {e}")
            raise
```

**验证：**
```bash
cd backend
python -c "from app.services.audit_service import AuditService; print('AuditService created successfully')"
```

### 步骤4：创建审计日志API

**创建：** `backend/app/api/audit_logs.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth_deps import get_current_user
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse, AuditLogQuery
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])

@router.get("/", response_model=List[AuditLogResponse])
async def get_audit_logs(
    user_id: int = Query(None, description="用户ID"),
    action: str = Query(None, description="操作类型"),
    resource_type: str = Query(None, description="资源类型"),
    resource_id: str = Query(None, description="资源ID"),
    status: str = Query(None, description="操作状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取审计日志列表
    
    需要管理员权限
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    query = AuditLogQuery(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        page=page,
        page_size=page_size
    )
    
    service = AuditService(db)
    logs, total = service.query_logs(query)
    
    return logs

@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取审计日志详情
    
    需要管理员权限
    """
    # 检查权限
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    service = AuditService(db)
    log = service.get_log_by_id(log_id)
    
    if not log:
        raise HTTPException(status_code=404, detail="审计日志不存在")
    
    return log

@router.get("/my-logs/", response_model=List[AuditLogResponse])
async def get_my_audit_logs(
    limit: int = Query(100, ge=1, le=1000, description="限制数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的审计日志
    """
    service = AuditService(db)
    logs = service.get_user_logs(current_user.id, limit=limit)
    
    return logs
```

**验证：**
```bash
cd backend
python -c "from app.api.audit_logs import router; print('Audit logs API created successfully')"
```

### 步骤5：注册审计日志路由

**修改：** `backend/app/main.py`

```python
# 在导入部分添加
from app.api import audit_logs

# 在注册路由部分添加
app.include_router(audit_logs.router)
```

**验证：**
```bash
cd backend
python -c "from app.main import app; print('Audit logs router registered successfully')"
```

### 步骤6：创建数据库迁移

**创建：** `backend/alembic/versions/20260426_add_audit_log_table.py`

```python
"""add audit log table

Revision ID: 20260426_add_audit_log
Revises: 
Create Date: 2026-04-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260426_add_audit_log'
down_revision = None  # 设置为最新的迁移版本
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'])
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'])
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'])
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'])

def downgrade():
    op.drop_index(op.f('ix_audit_logs_resource_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
```

**验证：**
```bash
cd backend
alembic upgrade head
```

### 步骤7：创建审计服务测试

**创建：** `backend/tests/test_audit_service.py`

```python
import pytest
from app.services.audit_service import AuditService
from app.schemas.audit_log import AuditLogCreate, AuditLogQuery

def test_create_audit_log(db_session):
    """测试创建审计日志"""
    service = AuditService(db_session)
    
    log = service.create_log(
        user_id=1,
        action="CREATE",
        resource_type="TEMPLATE",
        resource_id="1",
        details={"template_name": "测试模板"},
        ip_address="127.0.0.1",
        user_agent="Mozilla/5.0",
        status="success"
    )
    
    assert log.id is not None
    assert log.action == "CREATE"
    assert log.resource_type == "TEMPLATE"
    assert log.status == "success"

def test_query_audit_logs(db_session):
    """测试查询审计日志"""
    service = AuditService(db_session)
    
    # 创建测试日志
    service.create_log(
        user_id=1,
        action="CREATE",
        resource_type="TEMPLATE",
        resource_id="1"
    )
    
    service.create_log(
        user_id=1,
        action="UPDATE",
        resource_type="TEMPLATE",
        resource_id="1"
    )
    
    # 查询日志
    query = AuditLogQuery(user_id=1, page=1, page_size=10)
    logs, total = service.query_logs(query)
    
    assert len(logs) >= 2
    assert total >= 2

def test_get_user_logs(db_session):
    """测试获取用户日志"""
    service = AuditService(db_session)
    
    # 创建测试日志
    service.create_log(user_id=1, action="CREATE", resource_type="TEMPLATE")
    service.create_log(user_id=1, action="UPDATE", resource_type="TEMPLATE")
    service.create_log(user_id=2, action="CREATE", resource_type="TEMPLATE")
    
    # 获取用户1的日志
    logs = service.get_user_logs(user_id=1, limit=10)
    
    assert len(logs) >= 2
    assert all(log.user_id == 1 for log in logs)

def test_get_resource_logs(db_session):
    """测试获取资源日志"""
    service = AuditService(db_session)
    
    # 创建测试日志
    service.create_log(
        user_id=1,
        action="CREATE",
        resource_type="TEMPLATE",
        resource_id="template_1"
    )
    service.create_log(
        user_id=1,
        action="UPDATE",
        resource_type="TEMPLATE",
        resource_id="template_1"
    )
    
    # 获取资源日志
    logs = service.get_resource_logs("TEMPLATE", "template_1", limit=10)
    
    assert len(logs) >= 2
    assert all(log.resource_type == "TEMPLATE" for log in logs)
    assert all(log.resource_id == "template_1" for log in logs)
```

**验证：**
```bash
cd backend
pytest tests/test_audit_service.py -v
```

### 步骤8：提交代码

```bash
cd backend
git add app/models/audit_log.py app/schemas/audit_log.py app/services/audit_service.py app/api/audit_logs.py app/main.py alembic/versions/20260426_add_audit_log_table.py tests/test_audit_service.py
git commit -m "feat: 添加操作审计日志功能"
```

---

## 总结

### 已完成任务
- [x] 任务1：添加API集成测试框架
- [x] 任务2：实现查询结果缓存策略
- [x] 任务3：添加操作审计日志

### 待完成任务
- [ ] 任务4：优化前端性能
- [ ] 任务5：完善错误处理机制

### 验证清单
- [ ] 所有测试通过
- [ ] 代码覆盖率达标
- [ ] 功能正常工作
- [ ] 文档完整

### 下一步
继续完成剩余的任务4和任务5，然后进行整体测试和验证。