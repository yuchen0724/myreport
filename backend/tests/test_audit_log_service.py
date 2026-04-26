"""审计日志服务测试"""

import pytest
from app.services.audit_log_service import AuditLogService
from app.models.audit_log import AuditLog


def test_create_audit_log(db_session, test_user):
    """测试创建审计日志"""
    audit_service = AuditLogService(db_session)
    
    log = audit_service.create_log(
        user_id=test_user.id,
        action="CREATE",
        resource_type="template",
        resource_id="1",
        details={"name": "测试模板"},
        ip_address="127.0.0.1",
        user_agent="test-agent",
        status="success"
    )
    
    assert log.id is not None
    assert log.user_id == test_user.id
    assert log.action == "CREATE"
    assert log.resource_type == "template"
    assert log.status == "success"


def test_get_audit_logs(db_session, test_user):
    """测试获取审计日志列表"""
    audit_service = AuditLogService(db_session)
    
    # 创建多个日志
    for i in range(3):
        audit_service.create_log(
            user_id=test_user.id,
            action="CREATE",
            resource_type="template",
            resource_id=str(i),
            status="success"
        )
    
    # 获取日志列表
    logs = audit_service.get_logs(user_id=test_user.id)
    
    assert len(logs) >= 3
    assert all(log.user_id == test_user.id for log in logs)


def test_get_audit_log_by_id(db_session, test_user):
    """测试根据ID获取审计日志"""
    audit_service = AuditLogService(db_session)
    
    # 创建日志
    log = audit_service.create_log(
        user_id=test_user.id,
        action="UPDATE",
        resource_type="template",
        resource_id="1",
        status="success"
    )
    
    # 根据ID获取
    retrieved_log = audit_service.get_log_by_id(log.id)
    
    assert retrieved_log is not None
    assert retrieved_log.id == log.id
    assert retrieved_log.action == "UPDATE"


def test_get_user_activity(db_session, test_user):
    """测试获取用户活动统计"""
    audit_service = AuditLogService(db_session)
    
    # 创建多个日志
    audit_service.create_log(
        user_id=test_user.id,
        action="CREATE",
        resource_type="template",
        status="success"
    )
    audit_service.create_log(
        user_id=test_user.id,
        action="UPDATE",
        resource_type="template",
        status="success"
    )
    audit_service.create_log(
        user_id=test_user.id,
        action="DELETE",
        resource_type="template",
        status="failure"
    )
    
    # 获取用户活动统计
    activity = audit_service.get_user_activity(test_user.id)
    
    assert activity["total_actions"] == 3
    assert activity["success_count"] == 2
    assert activity["failure_count"] == 1
    assert activity["success_rate"] == 2/3
    assert "CREATE" in activity["action_counts"]
    assert "UPDATE" in activity["action_counts"]
    assert "DELETE" in activity["action_counts"]


def test_get_system_stats(db_session, test_user):
    """测试获取系统统计信息"""
    audit_service = AuditLogService(db_session)
    
    # 创建多个日志
    audit_service.create_log(
        user_id=test_user.id,
        action="CREATE",
        resource_type="template",
        status="success"
    )
    audit_service.create_log(
        user_id=test_user.id,
        action="QUERY",
        resource_type="query",
        status="success"
    )
    
    # 获取系统统计
    stats = audit_service.get_system_stats()
    
    assert stats["total_actions"] >= 2
    assert stats["active_users"] >= 1
    assert "template" in stats["resource_type_counts"]
    assert "query" in stats["resource_type_counts"]


def test_filter_audit_logs(db_session, test_user):
    """测试过滤审计日志"""
    audit_service = AuditLogService(db_session)
    
    # 创建不同类型的日志
    audit_service.create_log(
        user_id=test_user.id,
        action="CREATE",
        resource_type="template",
        status="success"
    )
    audit_service.create_log(
        user_id=test_user.id,
        action="UPDATE",
        resource_type="template",
        status="success"
    )
    audit_service.create_log(
        user_id=test_user.id,
        action="DELETE",
        resource_type="query",
        status="failure"
    )
    
    # 按操作类型过滤
    create_logs = audit_service.get_logs(user_id=test_user.id, action="CREATE")
    assert len(create_logs) >= 1
    assert all(log.action == "CREATE" for log in create_logs)
    
    # 按资源类型过滤
    template_logs = audit_service.get_logs(user_id=test_user.id, resource_type="template")
    assert len(template_logs) >= 2
    assert all(log.resource_type == "template" for log in template_logs)
    
    # 按状态过滤
    success_logs = audit_service.get_logs(user_id=test_user.id, status="success")
    assert len(success_logs) >= 2
    assert all(log.status == "success" for log in success_logs)
