"""预测 API 集成测试

测试策略：
- 所有需要 Celery 的任务类接口，直接 Mock 底层 task 模块的函数
- 预测功能默认 disabled，测试中通过 fixture 动态注册路由
- 状态查询/查询类接口不 Mock，直接访问（空数据也应返回合理结果）
"""

import os
import pytest
from unittest.mock import MagicMock
from app.config import get_settings


# ============================================================
# 启用预测路由的 fixture
# ============================================================

@pytest.fixture(scope="module")
def prediction_enabled():
    """临时启用预测路由"""
    from app.api.prediction import router as prediction_router
    from app.main import app
    path_set = {r.path for r in app.routes if hasattr(r, "path")}
    if "/api/prediction/train" not in path_set:
        app.include_router(prediction_router)
    yield


# ============================================================
# 验证
# ============================================================

def test_train_endpoint_validation(client, auth_headers):
    """测试 /api/prediction/train POST 端点请求验证"""
    response = client.post(
        "/api/prediction/train",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_train_endpoint_returns_task(client, auth_headers, prediction_enabled, monkeypatch):
    """Mock Celery task，验证训练任务能正确提交"""
    mock_async_result = MagicMock()
    mock_async_result.id = "mock-task-id-001"

    mock_task = MagicMock()
    mock_task.delay.return_value = mock_async_result

    # patch 模块级别的导入引用
    monkeypatch.setattr(
        "app.tasks.prediction_tasks.train_prediction_model_async",
        mock_task
    )

    response = client.post(
        "/api/prediction/train",
        json={
            "data_source_id": 1,
            "train_days": 90,
            "table_name": "test_db.test_table",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["task_id"] == "mock-task-id-001"
    assert "已提交" in data["message"]


def test_train_and_predict_endpoint(client, auth_headers, prediction_enabled, monkeypatch):
    """Mock Celery task，验证训练+预测合一接口"""
    mock_async_result = MagicMock()
    mock_async_result.id = "mock-task-id-002"

    mock_task = MagicMock()
    mock_task.delay.return_value = mock_async_result

    monkeypatch.setattr(
        "app.tasks.prediction_tasks.train_and_predict_prediction_async",
        mock_task
    )

    response = client.post(
        "/api/prediction/train-and-predict",
        json={
            "data_source_id": 1,
            "train_days": 90,
            "forecast_days": 30,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["task_id"] == "mock-task-id-002"


def test_predict_endpoint(client, auth_headers, prediction_enabled, monkeypatch):
    """Mock Celery task，验证预测接口"""
    mock_async_result = MagicMock()
    mock_async_result.id = "mock-task-id-003"

    mock_task = MagicMock()
    mock_task.delay.return_value = mock_async_result

    monkeypatch.setattr(
        "app.tasks.prediction_tasks.predict_prediction_model_async",
        mock_task
    )

    response = client.post(
        "/api/prediction/predict",
        json={
            "data_source_id": 1,
            "forecast_days": 30,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["task_id"] == "mock-task-id-003"


def test_train_status_endpoint(client, auth_headers, prediction_enabled):
    """不存在的 task_id 返回 200（API 设计为有默认值）"""
    response = client.get(
        "/api/prediction/train/status/nonexistent-task-id",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "percent" in data or "status" in data


def test_predict_status_endpoint(client, auth_headers, prediction_enabled):
    """不存在的 task_id 返回 200（API 设计为有默认值）"""
    response = client.get(
        "/api/prediction/predict/status/nonexistent-task-id",
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_forecast_query_endpoint(client, auth_headers, prediction_enabled):
    """预测结果查询（空结果应返回合理结构）"""
    response = client.get(
        "/api/prediction/forecast?data_source_id=1",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] == 0


def test_delete_history_by_task_id(client, auth_headers, prediction_enabled):
    """按 task_id 删除：无模型记录时也应正常返回"""
    response = client.delete(
        "/api/prediction/train/by-task/nonexistent-task-id/history",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_my_train_tasks_endpoint(client, auth_headers, prediction_enabled):
    """训练任务列表应返回列表"""
    response = client.get(
        "/api/prediction/train/tasks",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_forecast_running_endpoint(client, auth_headers, prediction_enabled):
    """运行中预���任务应返回列表"""
    response = client.get(
        "/api/prediction/forecast/running",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_forecast_history_endpoint(client, auth_headers, prediction_enabled):
    """预测历史应返回列表"""
    response = client.get(
        "/api/prediction/forecast/history",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_unauthorized_access(client):
    """未认证用户访问预测 API 应被拒绝"""
    response = client.post(
        "/api/prediction/train",
        json={"data_source_id": 1},
    )
    assert response.status_code in (401, 403)


def test_celery_failure_returns_500(client, auth_headers, prediction_enabled, monkeypatch):
    """Celery 连接异常时返回友好 500 而非 raw traceback"""
    mock_task = MagicMock()
    mock_task.delay.side_effect = ConnectionError("Redis connection refused")

    monkeypatch.setattr(
        "app.tasks.prediction_tasks.train_prediction_model_async",
        mock_task
    )

    response = client.post(
        "/api/prediction/train",
        json={"data_source_id": 1},
        headers=auth_headers,
    )
    assert response.status_code == 500
    data = response.json()
    # error_handler 将 detail 映射到 message 字段
    assert any("Celery" in str(v) or "连接异常" in str(v) for v in data.values())


def test_delete_forecast_progress(client, auth_headers, prediction_enabled):
    """删除进度记录"""
    response = client.delete(
        "/api/prediction/forecast/progress/nonexistent-task",
        headers=auth_headers,
    )
    assert response.status_code == 200


def test_forecast_export_endpoint_validation(client, auth_headers, prediction_enabled):
    """导出接口缺少必要参数应返回 422"""
    response = client.post(
        "/api/prediction/forecast/export",
        headers=auth_headers,
        json={},
    )
    # 缺少 data_source_id
    assert response.status_code == 422
