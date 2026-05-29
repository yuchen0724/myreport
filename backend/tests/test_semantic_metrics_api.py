import asyncio

import pytest
from fastapi import HTTPException

from app.api.semantic_metrics import (
    create_metric,
    delete_metric,
    execute_metric_query,
    get_metric,
    grant_metric_permission,
    list_metric_permissions,
    list_metric_versions,
    list_metrics,
    preview_metric_query,
    revoke_metric_permission,
    rollback_metric,
    update_metric,
)
from app.core.security import encrypt_password, get_password_hash
from app.models.data_source import DataSource
from app.models.role import Role
from app.models.user import User
from app.schemas.query import SQLQueryResponse
from app.schemas.semantic_metric import (
    SemanticMetricCreate,
    SemanticMetricPermissionCreate,
    SemanticMetricQueryRequest,
    SemanticMetricRollbackRequest,
    SemanticMetricUpdate,
)


def _run(coro):
    return asyncio.run(coro)


def _create_data_source(db_session, user_id):
    data_source = DataSource(
        name="语义层测试数据源",
        type="MYSQL",
        host="localhost",
        port=3306,
        database="reporting",
        username="report_user",
        password_encrypted=encrypt_password("password"),
        is_active=True,
        created_by=user_id,
    )
    db_session.add(data_source)
    db_session.commit()
    db_session.refresh(data_source)
    return data_source


def _create_user(db_session, username="metric_user", role=None):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=get_password_hash("testpassword"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_admin(db_session):
    role = Role(name="admin", description="管理员")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return _create_user(db_session, username="metric_admin", role=role)


def _payload(data_source_id, **overrides):
    payload = {
        "metric_key": "gmv",
        "name": "GMV",
        "description": "成交金额",
        "data_source_id": data_source_id,
        "base_sql": "SELECT order_id, biz_date, amount, store_id FROM fact_orders",
        "metric_expression": "SUM(amount)",
        "dimensions": ["store_id"],
        "time_column": "biz_date",
        "is_active": True,
    }
    payload.update(overrides)
    return SemanticMetricCreate(**payload)


def test_create_semantic_metric(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)

    metric = _run(create_metric(_payload(data_source.id), db_session, test_user))

    assert metric.metric_key == "gmv"
    assert metric.name == "GMV"
    assert metric.metric_expression == "SUM(amount)"
    assert metric.dimensions == ["store_id"]
    assert metric.created_by == test_user.id


def test_create_semantic_metric_rejects_duplicate_key(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    payload = _payload(data_source.id)
    _run(create_metric(payload, db_session, test_user))

    with pytest.raises(HTTPException) as exc_info:
        _run(create_metric(payload, db_session, test_user))

    assert exc_info.value.status_code == 409
    assert "metric_key" in exc_info.value.detail


def test_list_semantic_metrics_active_only(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _run(create_metric(_payload(data_source.id), db_session, test_user))
    _run(
        create_metric(
            _payload(data_source.id, metric_key="inactive_gmv", is_active=False),
            db_session,
            test_user,
        )
    )

    metrics = _run(list_metrics(0, 100, True, db_session, test_user))

    assert [metric.metric_key for metric in metrics] == ["gmv"]


def test_list_semantic_metrics_only_returns_owned_metrics(db_session, test_user):
    other_user = _create_user(db_session, username="metric_other")
    owner_source = _create_data_source(db_session, test_user.id)
    other_source = _create_data_source(db_session, other_user.id)
    _run(create_metric(_payload(owner_source.id), db_session, test_user))
    _run(create_metric(_payload(other_source.id, metric_key="other_gmv"), db_session, other_user))

    metrics = _run(list_metrics(0, 100, False, db_session, test_user))

    assert [metric.metric_key for metric in metrics] == ["gmv"]


def test_admin_can_list_all_semantic_metrics(db_session, test_user):
    admin_user = _create_admin(db_session)
    data_source = _create_data_source(db_session, test_user.id)
    admin_source = _create_data_source(db_session, admin_user.id)
    _run(create_metric(_payload(data_source.id), db_session, test_user))
    _run(create_metric(_payload(admin_source.id, metric_key="admin_gmv"), db_session, admin_user))

    metrics = _run(list_metrics(0, 100, False, db_session, admin_user))

    assert [metric.metric_key for metric in metrics] == ["admin_gmv", "gmv"]


def test_non_owner_cannot_read_or_mutate_semantic_metric(db_session, test_user):
    other_user = _create_user(db_session, username="metric_other")
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))

    with pytest.raises(HTTPException) as get_exc:
        _run(get_metric(created.id, db_session, other_user))
    with pytest.raises(HTTPException) as update_exc:
        _run(update_metric(created.id, SemanticMetricUpdate(name="越权修改"), db_session, other_user))
    with pytest.raises(HTTPException) as delete_exc:
        _run(delete_metric(created.id, db_session, other_user))
    with pytest.raises(HTTPException) as preview_exc:
        _run(preview_metric_query(SemanticMetricQueryRequest(metric_key="gmv"), db_session, other_user))

    assert get_exc.value.status_code == 404
    assert update_exc.value.status_code == 404
    assert delete_exc.value.status_code == 404
    assert preview_exc.value.status_code == 400
    assert preview_exc.value.detail == "指标不存在或已禁用"


def test_owner_can_share_viewer_permission(db_session, test_user):
    viewer = _create_user(db_session, username="metric_viewer")
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))

    permission = _run(
        grant_metric_permission(
            created.id,
            SemanticMetricPermissionCreate(user_id=viewer.id, permission_level="viewer"),
            db_session,
            test_user,
        )
    )
    permissions = _run(list_metric_permissions(created.id, db_session, test_user))
    shared_metrics = _run(list_metrics(0, 100, False, db_session, viewer))
    fetched = _run(get_metric(created.id, db_session, viewer))
    preview = _run(preview_metric_query(SemanticMetricQueryRequest(metric_key="gmv"), db_session, viewer))

    assert permission.permission_level == "viewer"
    assert len(permissions) == 1
    assert [metric.metric_key for metric in shared_metrics] == ["gmv"]
    assert fetched.id == created.id
    assert preview.data_source_id == data_source.id


def test_viewer_permission_cannot_mutate_or_manage_metric(db_session, test_user):
    viewer = _create_user(db_session, username="metric_viewer")
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))
    _run(
        grant_metric_permission(
            created.id,
            SemanticMetricPermissionCreate(user_id=viewer.id, permission_level="viewer"),
            db_session,
            test_user,
        )
    )

    with pytest.raises(HTTPException) as update_exc:
        _run(update_metric(created.id, SemanticMetricUpdate(name="viewer修改"), db_session, viewer))
    with pytest.raises(HTTPException) as rollback_exc:
        _run(rollback_metric(created.id, SemanticMetricRollbackRequest(version_number=1), db_session, viewer))
    with pytest.raises(HTTPException) as permissions_exc:
        _run(list_metric_permissions(created.id, db_session, viewer))

    assert update_exc.value.status_code == 404
    assert rollback_exc.value.status_code == 404
    assert permissions_exc.value.status_code == 404


def test_editor_permission_can_update_metric(db_session, test_user):
    editor = _create_user(db_session, username="metric_editor")
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))
    _run(
        grant_metric_permission(
            created.id,
            SemanticMetricPermissionCreate(user_id=editor.id, permission_level="editor"),
            db_session,
            test_user,
        )
    )

    updated = _run(update_metric(created.id, SemanticMetricUpdate(name="编辑者更新"), db_session, editor))
    versions = _run(list_metric_versions(created.id, db_session, editor))

    assert updated.name == "编辑者更新"
    assert versions[0].created_by == editor.id


def test_owner_can_revoke_metric_permission(db_session, test_user):
    viewer = _create_user(db_session, username="metric_viewer")
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))
    _run(
        grant_metric_permission(
            created.id,
            SemanticMetricPermissionCreate(user_id=viewer.id, permission_level="viewer"),
            db_session,
            test_user,
        )
    )

    _run(revoke_metric_permission(created.id, viewer.id, db_session, test_user))

    with pytest.raises(HTTPException) as exc_info:
        _run(get_metric(created.id, db_session, viewer))
    assert exc_info.value.status_code == 404


def test_admin_can_read_other_users_semantic_metric(db_session, test_user):
    admin_user = _create_admin(db_session)
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))

    fetched = _run(get_metric(created.id, db_session, admin_user))
    preview = _run(preview_metric_query(SemanticMetricQueryRequest(metric_key="gmv"), db_session, admin_user))

    assert fetched.id == created.id
    assert preview.data_source_id == data_source.id


def test_get_and_update_semantic_metric(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))

    updated = _run(
        update_metric(
            created.id,
            SemanticMetricUpdate(name="成交金额", dimensions=["store_id", "category_id"]),
            db_session,
            test_user,
        )
    )
    fetched = _run(get_metric(created.id, db_session, test_user))

    assert updated.name == "成交金额"
    assert fetched.dimensions == ["store_id", "category_id"]


def test_semantic_metric_versions_are_created_on_create_and_update(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))

    _run(update_metric(created.id, SemanticMetricUpdate(name="成交金额"), db_session, test_user))

    versions = _run(list_metric_versions(created.id, db_session, test_user))

    assert [version.version_number for version in versions] == [2, 1]
    assert versions[0].snapshot["name"] == "成交金额"
    assert versions[0].change_summary == "更新指标"
    assert versions[1].snapshot["name"] == "GMV"
    assert versions[1].change_summary == "创建指标"


def test_rollback_semantic_metric_restores_snapshot_and_creates_new_version(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))
    _run(
        update_metric(
            created.id,
            SemanticMetricUpdate(name="成交金额", metric_expression="AVG(amount)", dimensions=[]),
            db_session,
            test_user,
        )
    )

    rolled_back = _run(
        rollback_metric(created.id, SemanticMetricRollbackRequest(version_number=1), db_session, test_user)
    )
    versions = _run(list_metric_versions(created.id, db_session, test_user))

    assert rolled_back.name == "GMV"
    assert rolled_back.metric_expression == "SUM(amount)"
    assert rolled_back.dimensions == ["store_id"]
    assert [version.version_number for version in versions] == [3, 2, 1]
    assert versions[0].change_summary == "回滚到 v1"
    assert versions[0].snapshot["name"] == "GMV"


def test_non_owner_cannot_list_versions_or_rollback_semantic_metric(db_session, test_user):
    other_user = _create_user(db_session, username="metric_other")
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))

    with pytest.raises(HTTPException) as list_exc:
        _run(list_metric_versions(created.id, db_session, other_user))
    with pytest.raises(HTTPException) as rollback_exc:
        _run(rollback_metric(created.id, SemanticMetricRollbackRequest(version_number=1), db_session, other_user))

    assert list_exc.value.status_code == 404
    assert rollback_exc.value.status_code == 404


def test_delete_semantic_metric(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    created = _run(create_metric(_payload(data_source.id), db_session, test_user))

    _run(delete_metric(created.id, db_session, test_user))

    with pytest.raises(HTTPException) as exc_info:
        _run(get_metric(created.id, db_session, test_user))

    assert exc_info.value.status_code == 404


def test_create_semantic_metric_rejects_invalid_sql(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)

    with pytest.raises(ValueError):
        _payload(data_source.id, base_sql="DELETE FROM fact_orders")


def test_create_semantic_metric_rejects_missing_data_source(db_session, test_user):
    with pytest.raises(HTTPException) as exc_info:
        _run(create_metric(_payload(999999), db_session, test_user))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "数据源不存在"


def test_preview_metric_query_compiles_sql(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _run(create_metric(_payload(data_source.id), db_session, test_user))

    preview = _run(
        preview_metric_query(
            SemanticMetricQueryRequest(
                metric_key="gmv",
                start_time="2026-05-01",
                end_time="2026-06-01",
                dimensions=["store_id"],
                filters={"store_id": "S001"},
                page=2,
                page_size=20,
            ),
            db_session,
            test_user,
        )
    )

    assert preview.data_source_id == data_source.id
    assert preview.page == 2
    assert preview.page_size == 20
    assert preview.params == {
        "start_time": "2026-05-01",
        "end_time": "2026-06-01",
        "filter_0": "S001",
    }
    assert preview.sql == (
        "SELECT store_id, metric_value FROM "
        "(SELECT store_id, SUM(amount) AS metric_value FROM "
        "(SELECT order_id, biz_date, amount, store_id FROM fact_orders) AS metric_base "
        "WHERE biz_date >= :start_time AND biz_date < :end_time AND store_id = :filter_0 "
        "GROUP BY store_id) AS metric_result ORDER BY store_id"
    )


def test_preview_metric_query_supports_count_star_default(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _run(
        create_metric(
            _payload(
                data_source.id,
                metric_key="order_count",
                metric_expression="COUNT(*)",
                dimensions=[],
            ),
            db_session,
            test_user,
        )
    )

    preview = _run(
        preview_metric_query(
            SemanticMetricQueryRequest(metric_key="order_count", dimensions=[]),
            db_session,
            test_user,
        )
    )

    assert preview.sql == (
        "SELECT metric_value FROM "
        "(SELECT COUNT(*) AS metric_value FROM "
        "(SELECT order_id, biz_date, amount, store_id FROM fact_orders) AS metric_base) "
        "AS metric_result ORDER BY metric_value"
    )


def test_preview_metric_query_rejects_unknown_dimension(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _run(create_metric(_payload(data_source.id), db_session, test_user))

    with pytest.raises(HTTPException) as exc_info:
        _run(
            preview_metric_query(
                SemanticMetricQueryRequest(metric_key="gmv", dimensions=["unknown_dimension"]),
                db_session,
                test_user,
            )
        )

    assert exc_info.value.status_code == 400
    assert "未知维度" in exc_info.value.detail


def test_create_semantic_metric_rejects_unsafe_metric_expression(db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)

    with pytest.raises(ValueError):
        _payload(data_source.id, metric_expression="SUM(amount); DROP TABLE users")


def test_execute_metric_query_uses_query_service(monkeypatch, db_session, test_user):
    data_source = _create_data_source(db_session, test_user.id)
    _run(create_metric(_payload(data_source.id), db_session, test_user))
    captured = {}

    class FakeQueryService:
        def __init__(self, db):
            self.db = db

        def execute_sql(self, request, user_id):
            captured["request"] = request
            captured["user_id"] = user_id
            return SQLQueryResponse(
                columns=["store_id", "metric_value"],
                rows=[["S001", 10]],
                total=1,
                page=request.page,
                page_size=request.page_size,
                execution_time_ms=3,
            )

    monkeypatch.setattr(
        "app.services.semantic_metric_query_service.QueryService",
        FakeQueryService,
    )

    response = _run(
        execute_metric_query(
            SemanticMetricQueryRequest(metric_key="gmv", dimensions=["store_id"], page=1, page_size=10),
            db_session,
            test_user,
        )
    )

    assert response.metric.metric_key == "gmv"
    assert response.query.rows == [["S001", 10]]
    assert captured["user_id"] == test_user.id
    assert captured["request"].data_source_id == data_source.id
    assert captured["request"].page_size == 10
    assert captured["request"].skip_deep_pagination_check is False
