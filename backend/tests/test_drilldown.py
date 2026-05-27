"""
钻取功能测试
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.models.template import Template
from app.models.dashboard_widget import DashboardWidgetConfig, DashboardLayout
from app.core.security import get_password_hash


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base

    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    user = User(
        username="testuser_drilldown",
        email="drill@test.com",
        password_hash=get_password_hash("testpass"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(data={"sub": test_user.username, "user_id": test_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_template(db_session, test_user):
    config = {
        "data_source_id": 999,
        "sql": "SELECT category, amount FROM orders WHERE category = ${category}",
    }
    template = Template(
        name="钻取模板",
        description="用于钻取测试",
        config=json.dumps(config),
        version=1,
        is_public=False,
        created_by=test_user.id,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


@pytest.fixture
def test_widget_with_drilldown(db_session, test_user):
    """创建带钻取配置的 widget"""
    layout = DashboardLayout(user_id=test_user.id, name="测试布局")
    db_session.add(layout)
    db_session.commit()
    db_session.refresh(layout)

    drilldown_config = {
        "enabled": True,
        "target_template_id": None,  # 将在测试中设置
        "param_mapping": {
            "category": "$click.value",
        },
    }
    widget = DashboardWidgetConfig(
        user_id=test_user.id,
        layout_id=layout.id,
        widget_type="chart",
        widget_subtype="bar",
        title="柱状图",
        position=0,
        visible=True,
        extra_config={},
        drilldown_config=drilldown_config,
    )
    db_session.add(widget)
    db_session.commit()
    db_session.refresh(widget)
    return widget


# ==================== Schema 测试 ====================

class TestDrilldownSchemas:
    """钻取 Schema 单元测试"""

    def test_drilldown_request_schema(self):
        from app.schemas.dashboard import DrilldownRequest, DrilldownClickData

        req = DrilldownRequest(
            widget_id=1,
            template_id=5,
            click_data=DrilldownClickData(field="category", value="电子产品", label="电子产品"),
        )
        assert req.widget_id == 1
        assert req.template_id == 5
        assert req.click_data.value == "电子产品"
        assert req.params == {}

    def test_drilldown_request_with_params(self):
        from app.schemas.dashboard import DrilldownRequest, DrilldownClickData

        req = DrilldownRequest(
            widget_id=1,
            template_id=5,
            click_data=DrilldownClickData(field="category", value="A"),
            params={"extra_key": "extra_val"},
        )
        assert req.params["extra_key"] == "extra_val"

    def test_drilldown_response_schema(self):
        from app.schemas.dashboard import DrilldownResponse

        resp = DrilldownResponse(
            columns=["category", "amount"],
            rows=[["电子产品", 1000]],
            total=1,
            execution_time_ms=50,
            title="钻取: 电子产品",
        )
        assert resp.total == 1
        assert resp.title == "钻取: 电子产品"


# ==================== Service 测试 ====================

class TestDrilldownService:
    """钻取 Service 单元测试"""

    def test_resolve_mapping_click_value(self):
        from app.services.drilldown_service import DrilldownService
        from app.schemas.dashboard import DrilldownClickData

        svc = DrilldownService.__new__(DrilldownService)
        click = DrilldownClickData(field="category", value="食品", label="食品")
        assert svc._resolve_mapping("$click.value", click) == "食品"

    def test_resolve_mapping_click_field(self):
        from app.services.drilldown_service import DrilldownService
        from app.schemas.dashboard import DrilldownClickData

        svc = DrilldownService.__new__(DrilldownService)
        click = DrilldownClickData(field="category", value="食品", label="食品")
        assert svc._resolve_mapping("$click.field", click) == "category"

    def test_resolve_mapping_click_label(self):
        from app.services.drilldown_service import DrilldownService
        from app.schemas.dashboard import DrilldownClickData

        svc = DrilldownService.__new__(DrilldownService)
        click = DrilldownClickData(field="category", value="食品", label="食品分类")
        assert svc._resolve_mapping("$click.label", click) == "食品分类"

    def test_resolve_mapping_literal(self):
        from app.services.drilldown_service import DrilldownService
        from app.schemas.dashboard import DrilldownClickData

        svc = DrilldownService.__new__(DrilldownService)
        click = DrilldownClickData(field="x", value="y")
        assert svc._resolve_mapping("literal_value", click) == "literal_value"


# ==================== API 测试 ====================

class TestDrilldownAPI:
    """钻取 API 集成测试"""

    def _get_client(self, db_session):
        def override_get_db():
            yield db_session
        from app.middleware.rate_limit import RateLimitMiddleware
        app.user_middleware = [m for m in app.user_middleware if m.cls != RateLimitMiddleware]
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        yield client
        app.dependency_overrides.clear()

    def test_execute_drilldown_widget_not_found(self, db_session, test_user, auth_headers):
        """Widget 不存在时应返回 400"""
        from app.schemas.dashboard import DrilldownRequest, DrilldownClickData

        def override_get_db():
            yield db_session
        from app.middleware.rate_limit import RateLimitMiddleware
        app.user_middleware = [m for m in app.user_middleware if m.cls != RateLimitMiddleware]
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        resp = client.post(
            "/api/drilldown/execute",
            json={
                "widget_id": 99999,
                "template_id": 1,
                "click_data": {"field": "category", "value": "A"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "不存在" in data.get("message", "") or "不存在" in data.get("detail", "")
        app.dependency_overrides.clear()

    def test_execute_drilldown_not_enabled(self, db_session, test_user, auth_headers):
        """钻取未启用时应返回 400"""
        layout = DashboardLayout(user_id=test_user.id, name="布局")
        db_session.add(layout)
        db_session.commit()
        db_session.refresh(layout)

        widget = DashboardWidgetConfig(
            user_id=test_user.id,
            layout_id=layout.id,
            widget_type="chart",
            widget_subtype="bar",
            title="图表",
            position=0,
            visible=True,
            extra_config={},
            drilldown_config={"enabled": False},
        )
        db_session.add(widget)
        db_session.commit()
        db_session.refresh(widget)

        def override_get_db():
            yield db_session
        from app.middleware.rate_limit import RateLimitMiddleware
        app.user_middleware = [m for m in app.user_middleware if m.cls != RateLimitMiddleware]
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        resp = client.post(
            "/api/drilldown/execute",
            json={
                "widget_id": widget.id,
                "template_id": 1,
                "click_data": {"field": "category", "value": "A"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "未启用" in data.get("message", "") or "未启用" in data.get("detail", "")
        app.dependency_overrides.clear()

    def test_get_drilldown_config_no_widget(self, db_session, test_user, auth_headers):
        """获取不存在的 widget 钻取配置"""
        def override_get_db():
            yield db_session
        from app.middleware.rate_limit import RateLimitMiddleware
        app.user_middleware = [m for m in app.user_middleware if m.cls != RateLimitMiddleware]
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        resp = client.get("/api/drilldown/config/99999", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        app.dependency_overrides.clear()

    def test_get_drilldown_config_exists(self, db_session, test_user, auth_headers, test_widget_with_drilldown):
        """获取已配置钻取的 widget 钻取配置"""
        def override_get_db():
            yield db_session
        from app.middleware.rate_limit import RateLimitMiddleware
        app.user_middleware = [m for m in app.user_middleware if m.cls != RateLimitMiddleware]
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        resp = client.get(f"/api/drilldown/config/{test_widget_with_drilldown.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert "param_mapping" in data
        app.dependency_overrides.clear()

    def test_execute_drilldown_template_not_found(self, db_session, test_user, auth_headers):
        """目标模板不存在时应返回 400"""
        layout = DashboardLayout(user_id=test_user.id, name="布局2")
        db_session.add(layout)
        db_session.commit()
        db_session.refresh(layout)

        widget = DashboardWidgetConfig(
            user_id=test_user.id,
            layout_id=layout.id,
            widget_type="chart",
            widget_subtype="bar",
            title="图表",
            position=0,
            visible=True,
            extra_config={},
            drilldown_config={"enabled": True, "param_mapping": {"category": "$click.value"}},
        )
        db_session.add(widget)
        db_session.commit()
        db_session.refresh(widget)

        def override_get_db():
            yield db_session
        from app.middleware.rate_limit import RateLimitMiddleware
        app.user_middleware = [m for m in app.user_middleware if m.cls != RateLimitMiddleware]
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        resp = client.post(
            "/api/drilldown/execute",
            json={
                "widget_id": widget.id,
                "template_id": 99999,
                "click_data": {"field": "category", "value": "A"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "模板不存在" in data.get("message", "") or "模板不存在" in data.get("detail", "")
        app.dependency_overrides.clear()


# ==================== Model 测试 ====================

class TestDrilldownModel:
    """Widget 模型 drilldown_config 字段测试"""

    def test_widget_has_drilldown_config_column(self, db_session, test_user):
        layout = DashboardLayout(user_id=test_user.id, name="布局")
        db_session.add(layout)
        db_session.commit()
        db_session.refresh(layout)

        drilldown = {"enabled": True, "param_mapping": {"cat": "$click.value"}}
        widget = DashboardWidgetConfig(
            user_id=test_user.id,
            layout_id=layout.id,
            widget_type="chart",
            widget_subtype="bar",
            title="测试",
            position=0,
            visible=True,
            extra_config={},
            drilldown_config=drilldown,
        )
        db_session.add(widget)
        db_session.commit()
        db_session.refresh(widget)

        assert widget.drilldown_config is not None
        assert widget.drilldown_config["enabled"] is True
        assert widget.drilldown_config["param_mapping"]["cat"] == "$click.value"

    def test_widget_drilldown_config_nullable(self, db_session, test_user):
        layout = DashboardLayout(user_id=test_user.id, name="布局2")
        db_session.add(layout)
        db_session.commit()
        db_session.refresh(layout)

        widget = DashboardWidgetConfig(
            user_id=test_user.id,
            layout_id=layout.id,
            widget_type="chart",
            widget_subtype="pie",
            title="饼图",
            position=0,
            visible=True,
            extra_config={},
        )
        db_session.add(widget)
        db_session.commit()
        db_session.refresh(widget)

        assert widget.drilldown_config is None
