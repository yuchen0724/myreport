import os
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["LLM_API_KEY"] = "test-key"  # 避免 LLM 客户端初始化挂起
os.environ["LLM_PROVIDER"] = "openai"

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.models.user import User
from app.models.template import Template
from app.middleware.rate_limit import RateLimitMiddleware

# 测试数据库
TEST_DATABASE_URL = "sqlite:///:memory:"  # 使用 :memory: 确保每个测试完全隔离
engine = create_engine(TEST_DATABASE_URL, poolclass=StaticPool, connect_args={"check_same_thread": False})
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
    
    # 禁用限流中间件（测试环境）
    app.user_middleware = [
        m for m in app.user_middleware 
        if m.cls != RateLimitMiddleware
    ]
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
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
