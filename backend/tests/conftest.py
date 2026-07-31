import os
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["LLM_API_KEY"] = "test-key"  # 避免 LLM 客户端初始化挂起
os.environ["LLM_PROVIDER"] = "openai"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"

import pytest
import asyncio
import httpx
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.models.user import User
from app.models.role import Role
from app.models.template import Template
from app.middleware.rate_limit import RateLimitMiddleware

# 测试数据库
TEST_DATABASE_URL = "sqlite:///:memory:"  # 使用 :memory: 确保每个测试完全隔离
engine = create_engine(TEST_DATABASE_URL, poolclass=StaticPool, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ASGITestClient:
    """Small sync wrapper around httpx ASGITransport.

    Starlette's TestClient blocks in this sandbox with the current anyio stack.
    This wrapper keeps existing tests synchronous without using TestClient's
    thread portal.
    """

    def __init__(self, app):
        self.app = app

    def request(self, method: str, url: str, **kwargs):
        async def _request():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(_request())

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def patch(self, url: str, **kwargs):
        return self.request("PATCH", url, **kwargs)

    def close(self):
        return None

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
    async def override_get_db():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
    
    # 禁用限流中间件（测试环境）
    app.user_middleware = [
        m for m in app.user_middleware 
        if m.cls != RateLimitMiddleware
    ]
    
    app.dependency_overrides[get_db] = override_get_db
    test_client = ASGITestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user(db_session):
    """创建测试用户"""
    from app.core.security import get_password_hash
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def auth_headers(test_user):
    """创建认证头"""
    token = create_access_token(data={"sub": test_user.username, "user_id": test_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def test_admin(db_session):
    """创建管理员用户。"""
    from app.core.security import get_password_hash

    role = Role(name="admin", description="Administrator")
    db_session.add(role)
    db_session.flush()
    user = User(
        username="testadmin",
        email="admin@example.com",
        password_hash=get_password_hash("testpassword"),
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_auth_headers(test_admin):
    token = create_access_token(data={"sub": test_admin.username, "user_id": test_admin.id})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function", autouse=True)
def mock_llm(request):
    """全局 mock LLM 调用，防止测试中真实调用外部 API。

    自动应用于所有测试函数。单个测试可通过 patch 覆盖此 mock。
    chat() 返回固定 SQL 响应，避免真实 LLM 调用。
    """
    if request.node.path.name == "test_llm_client.py":
        yield None
        return

    mock_content = """
    ```sql
    SELECT * FROM users LIMIT 10
    ```
    """
    with patch("app.utils.llm_client.LLMClient.chat", return_value=mock_content) as mock_chat:
        with patch("app.utils.llm_client.LLMClient.chat_structured") as mock_structured:
            mock_structured.side_effect = Exception("Structured output disabled in tests")
            yield mock_chat


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
