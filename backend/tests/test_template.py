# backend/tests/test_template.py
import pytest
from app.services.template_service import TemplateService
from app.schemas.template import TemplateCreate

def test_create_template(db_session):
    """测试创建模板"""
    service = TemplateService(db_session)

    template_data = TemplateCreate(
        name="测试模板",
        description="这是一个测试模板",
        config={"data_source_id": 1, "sql": "SELECT * FROM users"},
        is_public=False
    )

    template = service.create_template(template_data, user_id=3)

    assert template.id is not None
    assert template.name == "测试模板"
    assert template.version == 1

def test_get_template(db_session):
    """测试获取模板"""
    service = TemplateService(db_session)

    # 先创建模板
    template_data = TemplateCreate(
        name="测试模板",
        description="这是一个测试模板",
        config={"data_source_id": 1, "sql": "SELECT * FROM users"},
        is_public=False
    )
    created = service.create_template(template_data, user_id=3)

    # 获取模板
    template = service.get_template(created.id)

    assert template is not None
    assert template.id == created.id
    assert template.name == "测试模板"

def test_update_template(db_session):
    """测试更新模板"""
    service = TemplateService(db_session)

    # 先创建模板
    template_data = TemplateCreate(
        name="测试模板",
        description="这是一个测试模板",
        config={"data_source_id": 1, "sql": "SELECT * FROM users"},
        is_public=False
    )
    created = service.create_template(template_data, user_id=3)

    # 更新模板
    from app.schemas.template import TemplateUpdate
    update_data = TemplateUpdate(
        name="更新后的模板",
        description="更新后的描述"
    )
    updated = service.update_template(created.id, update_data, user_id=3)

    assert updated.name == "更新后的模板"
    assert updated.description == "更新后的描述"
    assert updated.version == 2

def test_delete_template(db_session):
    """测试删除模板"""
    service = TemplateService(db_session)

    # 先创建模板
    template_data = TemplateCreate(
        name="测试模板",
        description="这是一个测试模板",
        config={"data_source_id": 1, "sql": "SELECT * FROM users"},
        is_public=False
    )
    created = service.create_template(template_data, user_id=3)

    # 删除模板
    success = service.delete_template(created.id, user_id=3)

    assert success is True

    # 验证已删除
    template = service.get_template(created.id)
    assert template is None
