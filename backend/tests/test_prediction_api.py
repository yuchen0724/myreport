"""预测 API 集成测试

测试所有 prediction API 端点：
  - 异步任务提交（train, predict, train-and-predict）
  - 任务状态查询
  - 预测结果查询 & 导出
  - 任务停止/取消
  - 历史记录管理 & 删除
  - 运行中任务查询

注意：prediction.py 中所有 Celery/Redis 导入都是惰性（在函数体内 import），
所以 mock 目标必须是源模块（app.tasks.prediction_tasks / app.celery_app），
而不是 app.api.prediction。
"""

import pytest
import json
import io
from unittest.mock import patch, MagicMock, PropertyMock, ANY, call
from datetime import date, datetime, timezone, timedelta
from fastapi.testclient import TestClient


# =============================================================================
# 通用 Fixtures
# =============================================================================


@pytest.fixture
def mock_celery_async_result():
    """返回一个 mock 的 Celery task，含 .id 属性"""
    task = MagicMock()
    task.id = "mock-celery-task-001"
    return task


@pytest.fixture
def mock_celery_app():
    """Mock celery_app.control.revoke（predictio.py 惰性导入 app.celery_app）"""
    with patch("app.celery_app.celery_app") as mock:
        mock.control = MagicMock()
        mock.control.revoke = MagicMock()
        yield mock


@pytest.fixture
def mock_tasks_get_progress():
    """Mock get_async_task_progress at source module"""
    with patch("app.tasks.prediction_tasks.get_async_task_progress") as mock:
        yield mock


@pytest.fixture
def sample_data_source(db_session):
    """创建一个测试数据源"""
    from app.models.data_source import DataSource
    ds = DataSource(
        name="测试数据源",
        type="DORIS",
        host="localhost",
        port=9030,
        database="test_db",
        username="test",
        password_encrypted="encrypted",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()
    db_session.refresh(ds)
    return ds


@pytest.fixture
def sample_model_record(db_session, sample_data_source, test_user):
    """创建一个 ready 状态的模型记录"""
    from app.repositories.prediction_repository import PredictionModelRepository
    repo = PredictionModelRepository(db_session)
    record = repo.create(
        data_source_id=sample_data_source.id,
        model_type="lightgbm",
        status="ready",
        task_id="model-task-001",
        created_by=test_user.id,
        model_path="/tmp/test_model.pkl",
        feature_count=25,
        train_start_date=date(2025, 1, 1),
        train_end_date=date(2025, 12, 31),
        train_row_count=1000,
        model_metrics={"mae": 50.0, "rmse": 100.0},
    )
    return record


@pytest.fixture
def sample_training_model(db_session, sample_data_source, test_user):
    """创建一个 training 状态的模型记录"""
    from app.repositories.prediction_repository import PredictionModelRepository
    repo = PredictionModelRepository(db_session)
    record = repo.create(
        data_source_id=sample_data_source.id,
        model_type="lightgbm",
        status="training",
        task_id="training-task-to-stop",
        created_by=test_user.id,
    )
    return record


@pytest.fixture
def sample_forecast_results(db_session, sample_data_source, sample_model_record):
    """创建一批预测结果记录"""
    from app.models.prediction import PredictionResult
    results = []
    for day_offset in range(10):
        results.append(PredictionResult(
            model_id=sample_model_record.id,
            data_source_id=sample_data_source.id,
            store_code="S001", matnr="M001",
            forecast_date=date(2026, 6, 1 + day_offset),
            predicted_value=float(500 + day_offset * 10),
            lower_bound=float(400 + day_offset * 10),
            upper_bound=float(600 + day_offset * 10),
            ware_name="测试商品",
        ))
    for day_offset in range(5):
        results.append(PredictionResult(
            model_id=sample_model_record.id,
            data_source_id=sample_data_source.id,
            store_code="S002", matnr="M002",
            forecast_date=date(2026, 6, 1 + day_offset),
            predicted_value=float(300 + day_offset * 5),
            lower_bound=float(200 + day_offset * 5),
            upper_bound=float(400 + day_offset * 5),
            ware_name="测试商品2",
        ))
    for r in results:
        db_session.add(r)
    db_session.commit()
    return results


@pytest.fixture
def sample_forecast_history(db_session, sample_data_source, test_user):
    """创建 ForecastHistory 记录"""
    from app.models.prediction import ForecastHistory
    hist = ForecastHistory(
        task_id="hist-task-001",
        model_id=1,
        data_source_id=sample_data_source.id,
        forecast_days=30,
        result_count=100,
        status="success",
        created_by=test_user.id,
    )
    db_session.add(hist)
    db_session.commit()
    db_session.refresh(hist)
    return hist


# =============================================================================
# 异步任务提交测试
# =============================================================================


class TestTrainEndpoint:
    """POST /api/prediction/train"""

    def test_train_submit_success(self, client, auth_headers, mock_celery_async_result):
        """验证训练任务提交成功"""
        with patch("app.tasks.prediction_tasks.train_prediction_model_async") as mock_task:
            mock_task.delay.return_value = mock_celery_async_result
            resp = client.post(
                "/api/prediction/train",
                json={"data_source_id": 1, "train_days": 365},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "mock-celery-task-001"
        assert data["status"] == "pending"
        assert "已提交" in data["message"]

    def test_train_submit_with_optional_params(self, client, auth_headers, mock_celery_async_result):
        """验证训练任务支持可选参数"""
        with patch("app.tasks.prediction_tasks.train_prediction_model_async") as mock_task:
            mock_task.delay.return_value = mock_celery_async_result
            resp = client.post(
                "/api/prediction/train",
                json={
                    "data_source_id": 1,
                    "train_days": 180,
                    "test_days": 14,
                    "valid_days": 7,
                    "table_name": "my_table",
                    "date_field": "dt",
                    "store_field": "store_code",
                    "sku_field": "matnr",
                    "target_field": "sales_amt",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "mock-celery-task-001"

    def test_train_submit_without_auth(self, client):
        """验证未认证时返回 401/403"""
        resp = client.post("/api/prediction/train", json={"data_source_id": 1})
        assert resp.status_code in (401, 403)

    def test_train_submit_celery_failure(self, client, auth_headers):
        """验证 Celery 不可用时返回 500"""
        with patch("app.tasks.prediction_tasks.train_prediction_model_async.delay") as mock_delay:
            mock_delay.side_effect = Exception("Redis connection refused")
            resp = client.post(
                "/api/prediction/train",
                json={"data_source_id": 1},
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "Celery" in resp.json()["message"]

    def test_train_submit_missing_data_source(self, client, auth_headers):
        """验证缺少 data_source_id 时返回 422"""
        resp = client.post("/api/prediction/train", json={}, headers=auth_headers)
        assert resp.status_code == 422


class TestPredictEndpoint:
    """POST /api/prediction/predict"""

    def test_predict_submit_success(self, client, auth_headers, mock_celery_async_result):
        """验证预测任务提交成功"""
        with patch("app.tasks.prediction_tasks.predict_prediction_model_async") as mock_task:
            mock_task.delay.return_value = mock_celery_async_result
            resp = client.post(
                "/api/prediction/predict",
                json={"data_source_id": 1},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "mock-celery-task-001"
        assert data["status"] == "pending"

    def test_predict_with_model_id(self, client, auth_headers, mock_celery_async_result):
        """验证预测支持指定 model_id"""
        with patch("app.tasks.prediction_tasks.predict_prediction_model_async") as mock_task:
            mock_task.delay.return_value = mock_celery_async_result
            resp = client.post(
                "/api/prediction/predict",
                json={"data_source_id": 1, "model_id": 42, "forecast_days": 60},
            )
        assert resp.status_code == 200

    def test_predict_with_table_name(self, client, auth_headers, mock_celery_async_result):
        """验证预测支持自定义表名"""
        with patch("app.tasks.prediction_tasks.predict_prediction_model_async") as mock_task:
            mock_task.delay.return_value = mock_celery_async_result
            resp = client.post(
                "/api/prediction/predict",
                json={"data_source_id": 1, "table_name": "(SELECT * FROM t) AS t"},
            )
        assert resp.status_code == 200


class TestTrainAndPredictEndpoint:
    """POST /api/prediction/train-and-predict"""

    def test_submit(self, client, auth_headers, mock_celery_async_result):
        """验证训练+预测任务提交成功"""
        with patch("app.tasks.prediction_tasks.train_and_predict_prediction_async") as mock_task:
            mock_task.delay.return_value = mock_celery_async_result
            resp = client.post(
                "/api/prediction/train-and-predict",
                json={"data_source_id": 1, "train_days": 365, "forecast_days": 30},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "mock-celery-task-001"
        assert data["status"] == "pending"

    def test_submit_passes_params(self, client, auth_headers, mock_celery_async_result):
        """验证参数被正确传递给 Celery task"""
        with patch("app.tasks.prediction_tasks.train_and_predict_prediction_async") as mock_task:
            mock_task.delay.return_value = mock_celery_async_result
            client.post(
                "/api/prediction/train-and-predict",
                json={
                    "data_source_id": 1,
                    "train_days": 180,
                    "test_days": 14,
                    "valid_days": 7,
                    "forecast_days": 60,
                    "table_name": "my_table",
                    "batch_size": 500,
                    "batch_unit": 20,
                },
                headers=auth_headers,
            )
        mock_task.delay.assert_called_once_with(
            data_source_id=1,
            model_type="lightgbm",
            train_days=180,
            test_days=14,
            valid_days=7,
            forecast_days=60,
            table_name="my_table",
            user_id=ANY,
            batch_size=500,
            batch_unit=20,
        )

    def test_submit_celery_failure(self, client, auth_headers):
        """验证 Celery 不可用时返回 500"""
        with patch("app.tasks.prediction_tasks.train_and_predict_prediction_async.delay") as mock_delay:
            mock_delay.side_effect = Exception("Broker error")
            resp = client.post(
                "/api/prediction/train-and-predict",
                json={"data_source_id": 1},
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "Celery" in resp.json()["message"]


# =============================================================================
# 任务状态查询测试
# =============================================================================


class TestTrainStatusEndpoint:
    """GET /api/prediction/train/status/{task_id}"""

    def test_running(self, client, auth_headers, mock_tasks_get_progress):
        """验证运行中的任务状态"""
        mock_tasks_get_progress.return_value = {
            "status": "running", "model_id": None, "error": None,
            "percent": 45, "phase": "拉取历史数据", "detail": "拉取中 3/10 批",
        }
        resp = client.get("/api/prediction/train/status/task-456", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["percent"] == 45

    def test_success(self, client, auth_headers, mock_tasks_get_progress):
        """验证已完成的任务状态"""
        mock_tasks_get_progress.return_value = {
            "status": "success", "model_id": 1, "error": None,
            "percent": 100, "phase": "完成", "detail": "训练完成",
        }
        resp = client.get("/api/prediction/train/status/task-789", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["model_id"] == 1

    def test_failed(self, client, auth_headers, mock_tasks_get_progress):
        """验证失败的任务状态"""
        mock_tasks_get_progress.return_value = {
            "status": "failed", "model_id": None, "error": "数据源不存在",
            "percent": 0, "phase": "失败", "detail": "数据源 999 不存在",
        }
        resp = client.get("/api/prediction/train/status/task-999", headers=auth_headers)
        assert resp.status_code == 200
        assert "数据源" in resp.json()["error"]


class TestPredictStatusEndpoint:
    """GET /api/prediction/predict/status/{task_id}"""

    def test_status(self, client, auth_headers, mock_tasks_get_progress):
        """验证预测任务状态查询"""
        mock_tasks_get_progress.return_value = {
            "status": "running", "model_id": 1, "error": None,
            "percent": 60, "phase": "门店预测", "detail": "预测中 3/10 店",
        }
        resp = client.get("/api/prediction/predict/status/predict-task", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["phase"] == "门店预测"


# =============================================================================
# 训练任务列表测试
# =============================================================================


class TestTrainTasksEndpoint:
    """GET /api/prediction/train/tasks"""

    def test_empty(self, client, auth_headers):
        resp = client.get("/api/prediction/train/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_with_records(self, client, auth_headers, db_session, test_user,
                          sample_model_record, sample_training_model):
        resp = client.get("/api/prediction/train/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_filter_by_status(self, client, auth_headers, db_session, test_user,
                               sample_model_record, sample_training_model):
        resp = client.get("/api/prediction/train/tasks?status=ready", headers=auth_headers)
        assert all(r["status"] == "ready" for r in resp.json())

        resp = client.get("/api/prediction/train/tasks?status=training", headers=auth_headers)
        assert all(r["status"] in ("training",) for r in resp.json())

    def test_filter_by_data_source(self, client, auth_headers, db_session, test_user,
                                    sample_data_source):
        from app.repositories.prediction_repository import PredictionModelRepository
        repo = PredictionModelRepository(db_session)
        repo.create(data_source_id=999, model_type="lightgbm", status="failed",
                     created_by=test_user.id)
        ds_id = sample_data_source.id
        resp = client.get(f"/api/prediction/train/tasks?data_source_id={ds_id}",
                          headers=auth_headers)
        assert all(r["data_source_id"] == ds_id for r in resp.json())

    def test_with_progress_arg(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        repo = PredictionModelRepository(db_session)
        repo.create(data_source_id=1, model_type="lightgbm", status="ready",
                     task_id="tp-task", created_by=test_user.id)
        resp = client.get("/api/prediction/train/tasks?with_progress=true",
                          headers=auth_headers)
        assert resp.status_code == 200

    def test_requires_auth(self, client):
        resp = client.get("/api/prediction/train/tasks")
        assert resp.status_code in (401, 403)


# =============================================================================
# 预测结果查询 & 导出测试
# =============================================================================


class TestForecastEndpoint:
    """GET /api/prediction/forecast"""

    def test_requires_data_source(self, client, auth_headers):
        resp = client.get("/api/prediction/forecast", headers=auth_headers)
        assert resp.status_code == 422

    def test_empty(self, client, auth_headers):
        resp = client.get("/api/prediction/forecast?data_source_id=999",
                          headers=auth_headers)
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_with_results(self, client, auth_headers, sample_data_source,
                           sample_forecast_results):
        resp = client.get(f"/api/prediction/forecast?data_source_id={sample_data_source.id}",
                          headers=auth_headers)
        data = resp.json()
        assert data["total"] > 0
        item = data["items"][0]
        assert "store_code" in item and "matnr" in item and "forecast_date" in item

    def test_filter_by_store(self, client, auth_headers, sample_data_source,
                              sample_forecast_results):
        resp = client.get(f"/api/prediction/forecast?data_source_id={sample_data_source.id}"
                          f"&store_code=S001", headers=auth_headers)
        assert all(r["store_code"] == "S001" for r in resp.json()["items"])

    def test_filter_by_matnr(self, client, auth_headers, sample_data_source,
                              sample_forecast_results):
        resp = client.get(f"/api/prediction/forecast?data_source_id={sample_data_source.id}"
                          f"&matnr=M001", headers=auth_headers)
        assert all(r["matnr"] == "M001" for r in resp.json()["items"])

    def test_filter_by_date_range(self, client, auth_headers, sample_data_source,
                                   sample_forecast_results):
        resp = client.get(
            f"/api/prediction/forecast?data_source_id={sample_data_source.id}"
            f"&start_date=2026-06-05&end_date=2026-06-10",
            headers=auth_headers,
        )
        for r in resp.json()["items"]:
            assert "2026-06-05" <= r["forecast_date"] <= "2026-06-10"

    def test_filter_by_model(self, client, auth_headers, sample_data_source,
                              sample_model_record, sample_forecast_results):
        resp = client.get(
            f"/api/prediction/forecast?data_source_id={sample_data_source.id}"
            f"&model_id={sample_model_record.id}",
            headers=auth_headers,
        )
        assert resp.json()["total"] == 15

    def test_pagination(self, client, auth_headers, sample_data_source,
                         sample_forecast_results):
        resp = client.get(
            f"/api/prediction/forecast?data_source_id={sample_data_source.id}"
            f"&page=1&page_size=5",
            headers=auth_headers,
        )
        data = resp.json()
        assert len(data["items"]) <= 5
        assert data["total"] == 15

    def test_sort_by_predicted_value_desc(self, client, auth_headers, sample_data_source,
                                           sample_forecast_results):
        resp = client.get(
            f"/api/prediction/forecast?data_source_id={sample_data_source.id}"
            f"&sort_by=predicted_value&sort_order=desc",
            headers=auth_headers,
        )
        items = resp.json()["items"]
        for i in range(len(items) - 1):
            assert items[i]["predicted_value"] >= items[i + 1]["predicted_value"]

    def test_invalid_sort_field(self, client, auth_headers, sample_data_source):
        """非法排序字段应降级为默认排序"""
        resp = client.get(
            f"/api/prediction/forecast?data_source_id={sample_data_source.id}"
            f"&sort_by=nonexistent",
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestForecastExportEndpoint:
    """POST /api/prediction/forecast/export"""

    def test_requires_data_source(self, client, auth_headers):
        resp = client.post("/api/prediction/forecast/export", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_export_with_results(self, client, auth_headers, sample_data_source,
                                  sample_forecast_results):
        resp = client.post(
            "/api/prediction/forecast/export",
            json={"data_source_id": sample_data_source.id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")

    def test_export_empty(self, client, auth_headers):
        resp = client.post(
            "/api/prediction/forecast/export",
            json={"data_source_id": 99999},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")

    def test_export_with_filters(self, client, auth_headers, sample_data_source,
                                  sample_forecast_results):
        resp = client.post(
            "/api/prediction/forecast/export",
            json={"data_source_id": sample_data_source.id, "store_code": "S001"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_export_validates_data_source_required(self, client, auth_headers):
        resp = client.post(
            "/api/prediction/forecast/export",
            json={"store_code": "S001"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# =============================================================================
# 历史记录 & 删除测试
# =============================================================================


class TestForecastHistoryEndpoint:
    """GET /api/prediction/forecast/history"""

    def test_empty(self, client, auth_headers):
        resp = client.get("/api/prediction/forecast/history", headers=auth_headers)
        assert isinstance(resp.json(), list)

    def test_with_records(self, client, auth_headers, sample_forecast_history):
        resp = client.get("/api/prediction/forecast/history", headers=auth_headers)
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["task_id"] == "hist-task-001"

    def test_pagination(self, client, auth_headers, sample_forecast_history):
        resp = client.get("/api/prediction/forecast/history?skip=0&limit=10",
                          headers=auth_headers)
        assert len(resp.json()) >= 1


class TestForecastRunningEndpoint:
    """GET /api/prediction/forecast/running"""

    def test_empty(self, client, auth_headers):
        with patch("app.tasks.prediction_tasks.get_running_task_ids") as mock_ids:
            mock_ids.return_value = set()
            resp = client.get("/api/prediction/forecast/running", headers=auth_headers)
            assert isinstance(resp.json(), list)

    def test_with_running_tasks(self, client, auth_headers, mock_tasks_get_progress):
        with (
            patch("app.tasks.prediction_tasks.get_running_task_ids") as mock_ids,
        ):
            mock_ids.return_value = {"running-001"}
            mock_tasks_get_progress.return_value = {
                "status": "running", "model_id": 1,
                "percent": 50, "phase": "门店预测", "detail": "...",
            }
            resp = client.get("/api/prediction/forecast/running", headers=auth_headers)
            # 没有 forecast_history 记录时返回空列表
            assert isinstance(resp.json(), list)


class TestDeleteModelHistory:
    """DELETE /api/prediction/history/{model_id}"""

    def test_not_found(self, client, auth_headers):
        assert client.delete("/api/prediction/history/99999", headers=auth_headers).status_code == 404

    def test_delete_own(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="failed", created_by=test_user.id)
        resp = client.delete(f"/api/prediction/history/{m.id}", headers=auth_headers)
        assert resp.status_code == 200 and resp.json()["status"] == "deleted"

    def test_delete_others(self, client, auth_headers, db_session):
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="failed", created_by=999)
        assert client.delete(f"/api/prediction/history/{m.id}", headers=auth_headers).status_code == 404

    def test_requires_auth(self, client, db_session):
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="failed", created_by=1)
        assert client.delete(f"/api/prediction/history/{m.id}").status_code in (401, 403)


class TestDeleteTrainHistory:
    """DELETE /api/prediction/train/{model_id}/history"""

    def test_delete(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="ready", created_by=test_user.id)
        resp = client.delete(f"/api/prediction/train/{m.id}/history", headers=auth_headers)
        assert resp.status_code == 200 and resp.json()["status"] == "deleted"

    def test_training_model_fails(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="training", created_by=test_user.id)
        resp = client.delete(f"/api/prediction/train/{m.id}/history", headers=auth_headers)
        assert resp.status_code == 400 and "训练中" in resp.json()["message"]

    def test_not_found(self, client, auth_headers):
        resp = client.delete("/api/prediction/train/99999/history", headers=auth_headers)
        assert resp.status_code == 404


class TestDeleteTrainHistoryByTask:
    """DELETE /api/prediction/train/by-task/{task_id}/history"""

    def test_delete(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="ready",
            task_id="by-task-del", created_by=test_user.id)
        resp = client.delete("/api/prediction/train/by-task/by-task-del/history",
                             headers=auth_headers)
        assert resp.status_code == 200 and resp.json()["status"] == "deleted"

    def test_training_fails(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="training",
            task_id="by-task-training", created_by=test_user.id)
        resp = client.delete("/api/prediction/train/by-task/by-task-training/history",
                             headers=auth_headers)
        assert resp.status_code == 400

    def test_no_model_still_ok(self, client, auth_headers):
        resp = client.delete("/api/prediction/train/by-task/nonexistent/history",
                             headers=auth_headers)
        assert resp.status_code == 200


class TestDeleteForecastProgress:
    """DELETE /api/prediction/forecast/progress/{task_id}"""

    def test_delete(self, client, auth_headers):
        with patch("app.tasks.prediction_tasks._get_redis") as mock_get_redis:
            mock_get_redis.return_value = MagicMock()
            resp = client.delete("/api/prediction/forecast/progress/task-001",
                                 headers=auth_headers)
        assert resp.status_code == 200 and resp.json()["success"] is True

    def test_redis_down(self, client, auth_headers):
        with patch("app.tasks.prediction_tasks._get_redis") as mock_get_redis:
            mock_get_redis.return_value = None
            resp = client.delete("/api/prediction/forecast/progress/redis-down",
                                 headers=auth_headers)
        assert resp.status_code == 200


# =============================================================================
# 任务停止测试
# =============================================================================


class TestStopTrain:
    """POST /api/prediction/train/{task_id}/stop"""

    def test_stop_training(self, client, auth_headers, db_session, test_user, mock_celery_app):
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="training",
            task_id="stop-train", created_by=test_user.id)
        resp = client.post("/api/prediction/train/stop-train/stop", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"
        updated = PredictionModelRepository(db_session).get_by_id(m.id)
        assert updated.status == "failed"
        assert "用户手动停止" in (updated.error_message or "")

    def test_stop_failed_cleanup(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="failed",
            task_id="stop-failed", created_by=test_user.id)
        resp = client.post("/api/prediction/train/stop-failed/stop", headers=auth_headers)
        assert resp.status_code == 200
        assert "已清理" in resp.json()["action"]

    def test_not_found(self, client, auth_headers):
        assert client.post("/api/prediction/train/no-such-task/stop",
                           headers=auth_headers).status_code == 404

    def test_stop_others(self, client, auth_headers, db_session, mock_celery_app):
        from app.repositories.prediction_repository import PredictionModelRepository
        PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="training",
            task_id="stop-others", created_by=999)
        assert client.post("/api/prediction/train/stop-others/stop",
                           headers=auth_headers).status_code == 404


class TestStopTrainAndPredict:
    """POST /api/prediction/train-and-predict/{task_id}/stop"""

    def test_stop(self, client, auth_headers, db_session, test_user, mock_celery_app):
        from app.repositories.prediction_repository import PredictionModelRepository
        PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="training",
            task_id="stop-tp", created_by=test_user.id)
        with patch("app.tasks.prediction_tasks._get_redis") as mock_get_redis:
            mock_get_redis.return_value = MagicMock()
            resp = client.post("/api/prediction/train-and-predict/stop-tp/stop",
                               headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"
        mock_celery_app.control.revoke.assert_called_once()

    def test_stop_cleans_forecast_history(self, client, auth_headers, db_session, test_user,
                                           mock_celery_app):
        from app.models.prediction import ForecastHistory
        hist = ForecastHistory(task_id="stop-tp-hist", data_source_id=1,
                                forecast_days=30, status="running", created_by=test_user.id)
        db_session.add(hist)
        db_session.commit()

        with patch("app.tasks.prediction_tasks._get_redis") as mock_get_redis:
            mock_get_redis.return_value = MagicMock()
            resp = client.post("/api/prediction/train-and-predict/stop-tp-hist/stop",
                               headers=auth_headers)
        assert resp.status_code == 200

        db_session.expire_all()
        updated = db_session.query(ForecastHistory).filter(
            ForecastHistory.task_id == "stop-tp-hist").first()
        assert updated is not None
        assert updated.status == "failed"
        assert "用户手动停止" == updated.error_message


# =============================================================================
# 边界情况 & 错误处理
# =============================================================================


class TestErrorHandling:

    def test_invalid_json_body(self, client, auth_headers):
        resp = client.post(
            "/api/prediction/train",
            content="not-json",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 422)

    def test_stop_updates_db_status(self, client, auth_headers, db_session, test_user,
                                     mock_celery_app):
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="training",
            task_id="stop-and-check", created_by=test_user.id)
        client.post("/api/prediction/train/stop-and-check/stop", headers=auth_headers)
        updated = PredictionModelRepository(db_session).get_by_id(m.id)
        assert updated.status == "failed"

    def test_delete_cleans_redis_progress(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="ready",
            task_id="redis-cleanup", created_by=test_user.id)
        resp = client.delete(f"/api/prediction/train/{m.id}/history", headers=auth_headers)
        assert resp.status_code == 200


# =============================================================================
# 响应结构验证
# =============================================================================


class TestResponseStructure:

    def test_forecast_response(self, client, auth_headers, sample_data_source,
                                sample_forecast_results):
        resp = client.get(f"/api/prediction/forecast?data_source_id={sample_data_source.id}"
                          f"&page_size=1", headers=auth_headers)
        data = resp.json()
        assert "items" in data and "total" in data
        if data["items"]:
            item = data["items"][0]
            for key in ("id", "store_code", "matnr", "ware_name",
                        "forecast_date", "predicted_value", "lower_bound", "upper_bound"):
                assert key in item

    def test_train_tasks_response(self, client, auth_headers, db_session, test_user):
        from app.repositories.prediction_repository import PredictionModelRepository
        PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="ready", created_by=test_user.id)
        resp = client.get("/api/prediction/train/tasks", headers=auth_headers)
        if resp.json():
            item = resp.json()[0]
            for key in ("model_id", "data_source_id", "status", "task_id"):
                assert key in item

    def test_task_status_response(self, client, auth_headers, mock_tasks_get_progress):
        mock_tasks_get_progress.return_value = {
            "status": "running", "model_id": 1, "error": None,
            "percent": 50, "phase": "进行中", "detail": "",
        }
        resp = client.get("/api/prediction/train/status/test-struct",
                          headers=auth_headers)
        data = resp.json()
        for key in ("task_id", "status", "percent", "phase", "detail"):
            assert key in data


# =============================================================================
# 集成场景测试
# =============================================================================


class TestIntegrationScenarios:

    def test_create_and_query_forecast(self, client, auth_headers, sample_data_source,
                                        sample_model_record, sample_forecast_results):
        """完整场景：创建预测结果并查询"""
        ds_id = sample_data_source.id
        r1 = client.get(f"/api/prediction/forecast?data_source_id={ds_id}", headers=auth_headers)
        assert r1.json()["total"] == 15

        r2 = client.get(f"/api/prediction/forecast?data_source_id={ds_id}&store_code=S001",
                        headers=auth_headers)
        assert r2.json()["total"] == 10

        r3 = client.get(f"/api/prediction/forecast?data_source_id={ds_id}&matnr=M002",
                        headers=auth_headers)
        assert r3.json()["total"] == 5

        r4 = client.get(f"/api/prediction/forecast?data_source_id={ds_id}"
                        f"&store_code=S001&start_date=2026-06-01&end_date=2026-06-05",
                        headers=auth_headers)
        assert r4.json()["total"] == 5

    def test_submit_and_query_train(self, client, auth_headers, mock_celery_async_result,
                                     mock_tasks_get_progress):
        """完整场景：提交训练并查询状态"""
        with patch("app.tasks.prediction_tasks.train_prediction_model_async") as mock_task:
            mock_task.delay.return_value = mock_celery_async_result
            submit_resp = client.post(
                "/api/prediction/train",
                json={"data_source_id": 1},
                headers=auth_headers,
            )
        assert submit_resp.status_code == 200
        task_id = submit_resp.json()["task_id"]

        mock_tasks_get_progress.return_value = {
            "status": "running", "model_id": None, "error": None,
            "percent": 50, "phase": "模型训练", "detail": "",
        }
        status_resp = client.get(f"/api/prediction/train/status/{task_id}", headers=auth_headers)
        assert status_resp.json()["percent"] == 50

    def test_export_then_delete(self, client, auth_headers, db_session, test_user,
                                 sample_data_source, sample_forecast_results):
        """完整场景：导出结果后删除模型"""
        export_resp = client.post(
            "/api/prediction/forecast/export",
            json={"data_source_id": sample_data_source.id},
            headers=auth_headers,
        )
        assert "spreadsheetml" in export_resp.headers.get("content-type", "")

        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=sample_data_source.id, model_type="lightgbm",
            status="ready", created_by=test_user.id)
        delete_resp = client.delete(f"/api/prediction/train/{m.id}/history",
                                    headers=auth_headers)
        assert delete_resp.json()["status"] == "deleted"

    def test_stop_then_delete(self, client, auth_headers, db_session, test_user,
                               mock_celery_app):
        """完整场景：停止运行中的任务后删除"""
        from app.repositories.prediction_repository import PredictionModelRepository
        m = PredictionModelRepository(db_session).create(
            data_source_id=1, model_type="lightgbm", status="training",
            task_id="int-stop-del", created_by=test_user.id)
        client.post("/api/prediction/train/int-stop-del/stop", headers=auth_headers)
        client.delete(f"/api/prediction/train/{m.id}/history", headers=auth_headers)

        get_resp = client.get("/api/prediction/train/tasks", headers=auth_headers)
        model_ids = [r["model_id"] for r in get_resp.json() if "model_id" in r]
        assert m.id not in model_ids
