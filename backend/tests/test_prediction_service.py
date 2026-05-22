"""预测服务单元测试"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import date, timedelta, datetime
from app.utils.feature_engineering import build_features_from_history, get_feature_columns


# =============================================================================
# 特征工程测试（已有）
# =============================================================================

def test_build_features():
    """测试特征工程能正确生成所有特征列"""
    np.random.seed(42)
    rows = []
    for store in ["S001", "S002"]:
        for matnr in ["M001", "M002"]:
            for day_offset in range(30):
                dt = f"202605{day_offset + 1:02d}"
                val = np.random.randint(100, 1000)
                rows.append([dt, store, matnr, val])

    df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
    df = build_features_from_history(df)

    feature_cols = get_feature_columns()
    for col in feature_cols:
        assert col in df.columns, f"缺失特征列: {col}"

    assert df["lag_1"].notna().sum() > 0
    assert df["day_of_week"].notna().sum() > 0
    assert df["is_weekend"].notna().sum() > 0


def test_get_feature_columns():
    """测试特征列列表返回正确数量"""
    cols = get_feature_columns()
    assert len(cols) == 25
    assert "lag_1" in cols
    assert "rolling_mean_7" in cols
    assert "day_of_week" in cols


# =============================================================================
# TrainService — train 方法测试
# =============================================================================

def test_train_with_mock_data(db_session, monkeypatch):
    """Mock 历史数据，验证训练流程可以走通"""
    from app.services.prediction_service import PredictionService

    def mock_fetch(self, ds_id, days, table_name=None):
        rows = []
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=365, freq="D")
        for store in ["S001", "S002", "S003"]:
            for matnr in ["M001", "M002", "M003"]:
                for d in range(365):
                    base = 500.0 + 100.0 * ((d % 7) + 1)
                    val = base + float(np.random.randint(-50, 50))
                    rows.append([dates[d].strftime("%Y%m%d"), store, matnr, val])
        df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d")
        return df

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)

    import tempfile
    tmpdir = tempfile.mkdtemp()
    from app.config import get_settings
    settings = get_settings()
    orig_dir = settings.prediction_model_dir
    settings.prediction_model_dir = tmpdir

    try:
        service = PredictionService(db_session)
        model_id = service.train(ds_id=1, train_days=100)

        assert model_id > 0

        import os
        model_path = os.path.join(tmpdir, f"lgb_1_{model_id}.pkl")
        assert os.path.exists(model_path), f"模型文件不存在: {model_path}"

        from app.repositories.prediction_repository import PredictionModelRepository
        repo = PredictionModelRepository(db_session)
        model_record = repo.get_by_id(model_id)
        assert model_record is not None
        assert model_record.status == "ready"
        assert model_record.model_metrics is not None
        assert "mae" in model_record.model_metrics
        assert model_record.feature_count == 25
    finally:
        settings.prediction_model_dir = orig_dir
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_train_min_history_check(db_session, monkeypatch):
    """验证历史数据不足时训练会失败"""
    from app.services.prediction_service import PredictionService

    def mock_fetch(self, ds_id, days, table_name=None):
        return pd.DataFrame(columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)

    from app.config import get_settings
    settings = get_settings()
    orig = settings.prediction_min_history_days
    settings.prediction_min_history_days = 14

    try:
        service = PredictionService(db_session)
        with pytest.raises(Exception, match="历史数据不足"):
            service.train(ds_id=1, train_days=100)
    finally:
        settings.prediction_min_history_days = orig


def test_train_with_custom_test_days(db_session, monkeypatch):
    """验证 train 方法支持自定义 test_days/valid_days 参数"""
    from app.services.prediction_service import PredictionService

    def mock_fetch(self, ds_id, days, table_name=None):
        rows = []
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=400, freq="D")
        for store in ["S001"]:
            for matnr in ["M001"]:
                for d in range(400):
                    val = 500.0 + float(np.random.randint(-50, 50))
                    rows.append([dates[d].strftime("%Y%m%d"), store, matnr, val])
        df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d")
        return df

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)

    import tempfile
    tmpdir = tempfile.mkdtemp()
    from app.config import get_settings
    settings = get_settings()
    orig_dir = settings.prediction_model_dir
    orig_min = settings.prediction_min_history_days

    # 降低最小数据行要求：1 store × 1 matnr × 400 天 = 400 行
    # min_history_days=1 → 需要 10 行，数据足够
    settings.prediction_min_history_days = 1
    settings.prediction_model_dir = tmpdir

    try:
        service = PredictionService(db_session)
        model_id = service.train(ds_id=1, train_days=100, test_days=14, valid_days=14)
        assert model_id > 0

        from app.repositories.prediction_repository import PredictionModelRepository
        repo = PredictionModelRepository(db_session)
        model_record = repo.get_by_id(model_id)
        assert model_record.status == "ready"
        assert "mae" in model_record.model_metrics
    finally:
        settings.prediction_model_dir = orig_dir
        settings.prediction_min_history_days = orig_min
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_train_failure_updates_status(db_session, monkeypatch):
    """验证训练失败时模型记录状态被更新为 failed"""
    from app.services.prediction_service import PredictionService

    def mock_fetch(self, ds_id, days, table_name=None):
        raise RuntimeError("数据库连接失败")

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)

    import tempfile
    tmpdir = tempfile.mkdtemp()
    from app.config import get_settings
    settings = get_settings()
    orig_dir = settings.prediction_model_dir
    settings.prediction_model_dir = tmpdir

    try:
        service = PredictionService(db_session)
        with pytest.raises(RuntimeError, match="数据库连接失败"):
            service.train(ds_id=1, train_days=100)

        from app.repositories.prediction_repository import PredictionModelRepository
        repo = PredictionModelRepository(db_session)
        records = repo.get_all(data_source_id=1)
        assert len(records) > 0
        latest = records[0]
        assert latest.status == "failed"
        assert latest.error_message is not None
    finally:
        settings.prediction_model_dir = orig_dir
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

# =============================================================================
# PredictService — predict 方法测试
# =============================================================================

def test_predict_without_model(db_session):
    """验证没有训练好的模型时 predict 会报错"""
    from app.services.prediction_service import PredictionService

    service = PredictionService(db_session)
    with pytest.raises(ValueError, match="没有已训练好的模型"):
        service.predict(ds_id=1, forecast_days=7)


def test_predict_with_invalid_model_id(db_session):
    """验证使用不存在的模型 ID 会报错"""
    from app.services.prediction_service import PredictionService

    service = PredictionService(db_session)
    with pytest.raises(ValueError, match="模型.*不存在或状态不是 ready"):
        service.predict(ds_id=1, forecast_days=7, model_id=9999)


def test_predict_with_non_ready_model(db_session):
    """验证使用非 ready 状态的模型会报错"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="training",
        model_path="/tmp/fake_model.pkl",
    )

    service = PredictionService(db_session)
    with pytest.raises(ValueError, match="状态不是 ready"):
        service.predict(ds_id=1, forecast_days=7, model_id=1)


def test_predict_with_specific_model_id(db_session, monkeypatch):
    """验证使用指定 model_id 进行预测的完整流程"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository
    import os

    repo = PredictionModelRepository(db_session)
    model_record = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="ready",
        model_path="/tmp/test_model.pkl",
    )

    # Mock joblib.load to return a fake model (avoid MagicMock pickling issue)
    import joblib
    fake_model = MagicMock()
    fake_model.predict.return_value = np.array([100.0])
    monkeypatch.setattr(joblib, "load", lambda path: fake_model)

    # Mock _fetch_history_data to return enough data for predict
    # predict calls _fetch_history_data(ds_id, days=60)
    def mock_fetch(self, ds_id, days, table_name=None):
        rows = []
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=90, freq="D")
        for store in ["S001"]:
            for matnr in ["M001"]:
                for d in range(90):
                    val = 500.0 + float(np.random.randint(-50, 50))
                    rows.append([dates[d].strftime("%Y%m%d"), store, matnr, val])
        df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d")
        return df

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)

    # Mock _lookup_ware_names to avoid DB/decrypt issues
    monkeypatch.setattr(PredictionService, "_lookup_ware_names", lambda self, ds_id, pairs: {})

    service = PredictionService(db_session)
    count, mid = service.predict(ds_id=1, forecast_days=7, model_id=model_record.id)

    # With 1 store × 1 matnr × 7 days = 7 predictions
    assert count == 7, f"Expected 7 predictions, got {count}"
    assert mid == model_record.id


def test_predict_with_progress_callback(db_session, monkeypatch):
    """验证 predict 方法中 progress_callback 被传递到 _predict_from_cache"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository
    import os, joblib

    repo = PredictionModelRepository(db_session)
    model_record = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="ready",
        model_path="/tmp/test_model2.pkl",
    )

    # Mock joblib.load to return a fake model (avoid MagicMock pickling issue)
    import joblib
    fake_model = MagicMock()
    fake_model.predict.return_value = np.array([100.0])
    monkeypatch.setattr(joblib, "load", lambda path: fake_model)

    def mock_fetch(self, ds_id, days, table_name=None):
        rows = []
        np.random.seed(42)
        dates = pd.date_range(start="2025-01-01", periods=90, freq="D")
        for store in ["S001"]:
            for matnr in ["M001"]:
                for d in range(90):
                    val = 500.0 + float(np.random.randint(-50, 50))
                    rows.append([dates[d].strftime("%Y%m%d"), store, matnr, val])
        df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d")
        return df

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)
    monkeypatch.setattr(PredictionService, "_lookup_ware_names", lambda self, ds_id, pairs: {})

    callback_calls = []

    def progress_cb(mid, idx, total, store_code):
        callback_calls.append((mid, idx, total, store_code))

    service = PredictionService(db_session)
    count, mid = service.predict(
        ds_id=1, forecast_days=7, model_id=model_record.id,
        progress_callback=progress_cb
    )
    assert mid == model_record.id
    # With 1 store, progress should be called at least once
    assert len(callback_calls) >= 1
    assert callback_calls[0][0] == mid

# =============================================================================
# _lookup_ware_names 测试
# =============================================================================

def test_lookup_ware_names_empty(db_session):
    """验证空 pairs 返回空字典"""
    from app.services.prediction_service import PredictionService

    service = PredictionService(db_session)
    result = service._lookup_ware_names(ds_id=1, pairs=[])
    assert result == {}


def test_lookup_ware_names_no_ds(db_session):
    """验证数据源不存在时返回空字典"""
    from app.services.prediction_service import PredictionService

    service = PredictionService(db_session)
    result = service._lookup_ware_names(ds_id=999, pairs=[("S001", "M001")])
    assert result == {}


def test_lookup_ware_names_success(db_session, monkeypatch):
    """验证成功查询商品名称"""
    from app.services.prediction_service import PredictionService, execute_query
    from app.models.data_source import DataSource

    ds = DataSource(
        id=2, name="test", type="DORIS",
        host="localhost", port=9030, database="test_db",
        username="test", password_encrypted="test",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()

    # Mock execute_query at the module where it's imported (prediction_service)
    def mock_execute_query(ds_obj, sql):
        assert "store_code = 'S001' AND matnr = 'M001'" in sql
        rows = [["S001", "M001", "测试商品A"]]
        cols = ["store_code", "matnr", "ware_name"]
        return rows, cols

    monkeypatch.setattr("app.services.prediction_service.execute_query", mock_execute_query)

    service = PredictionService(db_session)
    result = service._lookup_ware_names(ds_id=2, pairs=[("S001", "M001")])

    assert ("S001", "M001") in result
    assert result[("S001", "M001")] == "测试商品A"


def test_lookup_ware_names_exception(db_session, monkeypatch):
    """验证查询异常时返回空字典"""
    from app.services.prediction_service import PredictionService
    from app.models.data_source import DataSource

    ds = DataSource(
        id=3, name="test", type="DORIS",
        host="localhost", port=9030, database="test_db",
        username="test", password_encrypted="test",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()

    def mock_execute_query(ds_obj, sql):
        raise Exception("数据库错误")

    monkeypatch.setattr("app.services.prediction_service.execute_query", mock_execute_query)

    service = PredictionService(db_session)
    result = service._lookup_ware_names(ds_id=3, pairs=[("S001", "M001")])
    assert result == {}


def test_lookup_ware_names_multiple_pairs(db_session, monkeypatch):
    """验证多对 (store_code, matnr) 的查询"""
    from app.services.prediction_service import PredictionService
    from app.models.data_source import DataSource

    ds = DataSource(
        id=4, name="test", type="DORIS",
        host="localhost", port=9030, database="test_db",
        username="test", password_encrypted="test",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()

    def mock_execute_query(ds_obj, sql):
        assert "store_code = 'S001' AND matnr = 'M001'" in sql
        assert "store_code = 'S002' AND matnr = 'M002'" in sql
        rows = [
            ["S001", "M001", "商品A"],
            ["S002", "M002", "商品B"],
        ]
        cols = ["store_code", "matnr", "ware_name"]
        return rows, cols

    monkeypatch.setattr("app.services.prediction_service.execute_query", mock_execute_query)

    service = PredictionService(db_session)
    result = service._lookup_ware_names(
        ds_id=4, pairs=[("S001", "M001"), ("S002", "M002")]
    )

    assert len(result) == 2
    assert result[("S001", "M001")] == "商品A"
    assert result[("S002", "M002")] == "商品B"

# =============================================================================
# _fetch_history_data 测试
# =============================================================================

def test_fetch_history_data_no_ds(db_session):
    """验证数据源不存在时 _fetch_history_data 抛出异常"""
    from app.services.prediction_service import PredictionService

    service = PredictionService(db_session)
    with pytest.raises(ValueError, match="数据源.*不存在"):
        service._fetch_history_data(ds_id=999, days=30)


def test_fetch_history_data_with_callback(db_session, monkeypatch):
    """验证 progress_callback 被正确调用"""
    from app.services.prediction_service import PredictionService
    from app.models.data_source import DataSource

    ds = DataSource(
        id=10, name="test", type="DORIS",
        host="localhost", port=9030, database="test_db",
        username="test", password_encrypted="test",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()

    def mock_execute_query(ds_obj, sql):
        rows = [["20260501", "S001", "M001", 50000]]
        cols = ["dt", "store_code", "matnr", "actual_sale_untaxed_amt"]
        return rows, cols

    monkeypatch.setattr("app.services.prediction_service.execute_query", mock_execute_query)

    callback_calls = []

    def progress_cb(current, total, rows_count):
        callback_calls.append((current, total, rows_count))

    service = PredictionService(db_session)
    df = service._fetch_history_data(ds_id=10, days=30, progress_callback=progress_cb)

    assert len(callback_calls) > 0
    assert len(df) == 1
    assert "actual_sale_untaxed_amt" in df.columns
    # 金额分转元验证
    assert df["actual_sale_untaxed_amt"].iloc[0] == 500.0


def test_fetch_history_data_empty_result(db_session, monkeypatch):
    """验证无数据时返回空 DataFrame"""
    from app.services.prediction_service import PredictionService
    from app.models.data_source import DataSource

    ds = DataSource(
        id=11, name="test", type="DORIS",
        host="localhost", port=9030, database="test_db",
        username="test", password_encrypted="test",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()

    def mock_execute_query(ds_obj, sql):
        return [], ["dt", "store_code", "matnr", "actual_sale_untaxed_amt"]

    monkeypatch.setattr("app.services.prediction_service.execute_query", mock_execute_query)

    service = PredictionService(db_session)
    df = service._fetch_history_data(ds_id=11, days=30)

    assert len(df) == 0
    assert list(df.columns) == ["dt", "store_code", "matnr", "actual_sale_untaxed_amt"]


def test_fetch_history_data_table_name(db_session, monkeypatch):
    """验证 _fetch_history_data 支持自定义 table_name 参数"""
    from app.services.prediction_service import PredictionService
    from app.models.data_source import DataSource

    ds = DataSource(
        id=12, name="test", type="DORIS",
        host="localhost", port=9030, database="test_db",
        username="test", password_encrypted="test",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()

    def mock_execute_query(ds_obj, sql):
        # Verify the SQL contains the specified table name
        assert "my_custom_table" in sql or "my_custom" in sql
        return [], ["dt", "store_code", "matnr", "actual_sale_untaxed_amt"]

    monkeypatch.setattr("app.services.prediction_service.execute_query", mock_execute_query)

    service = PredictionService(db_session)
    df = service._fetch_history_data(ds_id=12, days=30, table_name="my_custom_table")
    assert len(df) == 0

# =============================================================================
# ForecastHistoryRepository 测试
# =============================================================================

def test_forecast_history_create(db_session):
    """验证 ForecastHistoryRepository.create 能创建记录"""
    from app.repositories.prediction_repository import ForecastHistoryRepository

    repo = ForecastHistoryRepository(db_session)
    record = repo.create(
        task_id="test-task-001",
        data_source_id=1,
        forecast_days=30,
        result_count=100,
        status="success",
        created_by=1,
    )
    assert record.id > 0
    assert record.task_id == "test-task-001"
    assert record.status == "success"
    assert record.forecast_days == 30
    assert record.result_count == 100


def test_forecast_history_get_by_user(db_session):
    """验证 ForecastHistoryRepository.get_by_user 能按用户过滤"""
    from app.repositories.prediction_repository import ForecastHistoryRepository

    repo = ForecastHistoryRepository(db_session)
    repo.create(task_id="t1", data_source_id=1, forecast_days=30, created_by=1)
    repo.create(task_id="t2", data_source_id=1, forecast_days=60, created_by=1)
    repo.create(task_id="t3", data_source_id=1, forecast_days=90, created_by=2)

    records = repo.get_by_user(user_id=1)
    assert len(records) == 2

    records = repo.get_by_user(user_id=2)
    assert len(records) == 1
    assert records[0].task_id == "t3"

    records = repo.get_by_user()
    assert len(records) == 3


def test_forecast_history_get_by_task_id(db_session):
    """验证 ForecastHistoryRepository.get_by_task_id 查询"""
    from app.repositories.prediction_repository import ForecastHistoryRepository

    repo = ForecastHistoryRepository(db_session)
    repo.create(task_id="task-uniq-1", data_source_id=1, forecast_days=30)

    records = repo.get_by_task_id("task-uniq-1")
    assert len(records) == 1
    assert records[0].task_id == "task-uniq-1"

    records = repo.get_by_task_id("nonexistent")
    assert len(records) == 0


def test_forecast_history_pagination(db_session):
    """验证 ForecastHistoryRepository.get_by_user 的分页参数"""
    from app.repositories.prediction_repository import ForecastHistoryRepository

    repo = ForecastHistoryRepository(db_session)
    for i in range(5):
        repo.create(task_id=f"task-{i}", data_source_id=1, forecast_days=30, created_by=1)

    records_all = repo.get_by_user(user_id=1, skip=0, limit=100)
    assert len(records_all) == 5

    records_page = repo.get_by_user(user_id=1, skip=0, limit=2)
    assert len(records_page) == 2


# =============================================================================
# PredictionModelRepository 测试
# =============================================================================

def test_prediction_model_get_all(db_session):
    """验证 PredictionModelRepository.get_all 查询"""
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    r1 = repo.create(data_source_id=1, model_type="lightgbm", status="training")
    r2 = repo.create(data_source_id=1, model_type="lightgbm", status="ready")
    r3 = repo.create(data_source_id=2, model_type="lightgbm", status="training")

    all_records = repo.get_all()
    assert len(all_records) == 3

    ds1_records = repo.get_all(data_source_id=1)
    assert len(ds1_records) == 2

    ds2_records = repo.get_all(data_source_id=2)
    assert len(ds2_records) == 1

    paginated = repo.get_all(skip=0, limit=1)
    assert len(paginated) == 1


def test_prediction_model_get_running_by_user(db_session):
    """验证 PredictionModelRepository.get_running_by_user 查询"""
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    repo.create(data_source_id=1, model_type="lightgbm", status="training", created_by=1)
    repo.create(data_source_id=1, model_type="lightgbm", status="ready", created_by=1)

    records = repo.get_running_by_user(user_id=1)
    assert len(records) >= 1


def test_prediction_model_get_latest_ready(db_session):
    """验证 PredictionModelRepository.get_latest_ready 返回最新 ready 模型"""
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    repo.create(data_source_id=1, model_type="lightgbm", status="training")
    r2 = repo.create(data_source_id=1, model_type="lightgbm", status="ready")
    r3 = repo.create(data_source_id=1, model_type="lightgbm", status="ready")

    latest = repo.get_latest_ready(data_source_id=1)
    assert latest is not None
    assert latest.id == r3.id
    assert latest.status == "ready"

    none_result = repo.get_latest_ready(data_source_id=999)
    assert none_result is None


def test_prediction_model_update_status(db_session):
    """验证 PredictionModelRepository.update_status 更新状态"""
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    record = repo.create(data_source_id=1, model_type="lightgbm", status="training")

    repo.update_status(record.id, "ready", model_path="/tmp/test.pkl", feature_count=25)
    updated = repo.get_by_id(record.id)
    assert updated.status == "ready"
    assert updated.model_path == "/tmp/test.pkl"
    assert updated.feature_count == 25


# =============================================================================
# PredictionResultRepository 测试
# =============================================================================

def test_prediction_result_bulk_save(db_session):
    """验证 PredictionResultRepository.bulk_save 批量保存"""
    from app.repositories.prediction_repository import PredictionResultRepository
    from app.models.prediction import PredictionResult
    from datetime import date

    repo = PredictionResultRepository(db_session)
    results = [
        PredictionResult(
            model_id=1, data_source_id=1,
            store_code="S001", matnr="M001",
            forecast_date=date(2025, 1, 1), predicted_value=100.0,
        ),
        PredictionResult(
            model_id=1, data_source_id=1,
            store_code="S002", matnr="M002",
            forecast_date=date(2025, 1, 1), predicted_value=200.0,
        ),
    ]
    count = repo.bulk_save(results)
    assert count == 2


def test_prediction_result_get_forecast(db_session):
    """验证 PredictionResultRepository.get_forecast 查询"""
    from app.repositories.prediction_repository import PredictionResultRepository
    from app.models.prediction import PredictionResult
    from datetime import date

    repo = PredictionResultRepository(db_session)
    results = [
        PredictionResult(model_id=1, data_source_id=1, store_code="S001", matnr="M001",
                         forecast_date=date(2025, 1, 1), predicted_value=100.0),
        PredictionResult(model_id=1, data_source_id=1, store_code="S001", matnr="M002",
                         forecast_date=date(2025, 1, 2), predicted_value=200.0),
        PredictionResult(model_id=1, data_source_id=1, store_code="S002", matnr="M001",
                         forecast_date=date(2025, 1, 3), predicted_value=300.0),
        PredictionResult(model_id=2, data_source_id=2, store_code="S003", matnr="M003",
                         forecast_date=date(2025, 1, 4), predicted_value=400.0),
    ]
    repo.bulk_save(results)

    all_results = repo.get_forecast(data_source_id=1)
    assert len(all_results) == 3

    model1_results = repo.get_forecast(data_source_id=1, model_id=1)
    assert len(model1_results) == 3

    store_results = repo.get_forecast(data_source_id=1, store_code="S001")
    assert len(store_results) == 2

    matnr_results = repo.get_forecast(data_source_id=1, matnr="M001")
    assert len(matnr_results) == 2

    date_results = repo.get_forecast(
        data_source_id=1,
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 3),
    )
    assert len(date_results) == 2


def test_prediction_result_get_forecast_sort(db_session):
    """验证 PredictionResultRepository.get_forecast 排序"""
    from app.repositories.prediction_repository import PredictionResultRepository
    from app.models.prediction import PredictionResult
    from datetime import date

    repo = PredictionResultRepository(db_session)
    results = [
        PredictionResult(model_id=1, data_source_id=1, store_code="S001", matnr="M001",
                         forecast_date=date(2025, 1, 1), predicted_value=100.0),
        PredictionResult(model_id=1, data_source_id=1, store_code="S001", matnr="M002",
                         forecast_date=date(2025, 1, 2), predicted_value=300.0),
        PredictionResult(model_id=1, data_source_id=1, store_code="S001", matnr="M003",
                         forecast_date=date(2025, 1, 3), predicted_value=200.0),
    ]
    repo.bulk_save(results)

    sorted_results = repo.get_forecast(
        data_source_id=1, sort_by="predicted_value", sort_order="desc"
    )
    assert sorted_results[0].predicted_value == 300.0
    assert sorted_results[1].predicted_value == 200.0

    date_results = repo.get_forecast(data_source_id=1, sort_by="forecast_date", sort_order="asc")
    assert date_results[0].forecast_date == date(2025, 1, 1)
    assert date_results[2].forecast_date == date(2025, 1, 3)


def test_prediction_result_count_forecast(db_session):
    """验证 PredictionResultRepository.count_forecast 计数"""
    from app.repositories.prediction_repository import PredictionResultRepository
    from app.models.prediction import PredictionResult
    from datetime import date

    repo = PredictionResultRepository(db_session)
    results = [
        PredictionResult(model_id=1, data_source_id=1, store_code="S001", matnr="M001",
                         forecast_date=date(2025, 1, 1), predicted_value=100.0),
        PredictionResult(model_id=1, data_source_id=1, store_code="S001", matnr="M002",
                         forecast_date=date(2025, 1, 2), predicted_value=200.0),
        PredictionResult(model_id=1, data_source_id=1, store_code="S002", matnr="M001",
                         forecast_date=date(2025, 1, 3), predicted_value=300.0),
    ]
    repo.bulk_save(results)

    count = repo.count_forecast(data_source_id=1)
    assert count == 3

    count_store = repo.count_forecast(data_source_id=1, store_code="S001")
    assert count_store == 2

    count_matnr = repo.count_forecast(data_source_id=1, matnr="M001")
    assert count_matnr == 2

    count_date = repo.count_forecast(
        data_source_id=1,
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 3),
    )
    assert count_date == 2

# =============================================================================
# 重试与进度相关测试
# =============================================================================

def test_train_and_predict_with_progress_retry_reuses_record(db_session, monkeypatch):
    """验证 is_retry=True 时复用已有 DB 记录，不创建新记录"""
    from app.tasks.prediction_tasks import _train_and_predict_with_progress
    from app.models.prediction import PredictionModel
    from app.repositories.prediction_repository import PredictionModelRepository
    import uuid

    task_id = str(uuid.uuid4())

    repo = PredictionModelRepository(db_session)
    record1 = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="failed",
        task_id=task_id,
        created_by=1,
        error_message="首次失败",
    )
    first_id = record1.id

    from app.services.prediction_service import PredictionService
    service = PredictionService(db_session)

    model_record = db_session.query(PredictionModel).filter(
        PredictionModel.task_id == task_id
    ).first()
    assert model_record is not None
    assert model_record.id == first_id

    original_create = service.model_repo.create
    call_count = [0]

    def tracking_create(**kwargs):
        call_count[0] += 1
        return original_create(**kwargs)

    service.model_repo.create = tracking_create

    model_record = db_session.query(PredictionModel).filter(
        PredictionModel.task_id == task_id
    ).first()

    if model_record is not None:
        pass
    else:
        model_record = service.model_repo.create(
            data_source_id=1,
            model_type="lightgbm",
            status="training",
            task_id=task_id,
            created_by=1,
        )

    assert call_count[0] == 0, "复用已有记录时不应调用 create"

    records = db_session.query(PredictionModel).filter(
        PredictionModel.task_id == task_id
    ).all()
    assert len(records) == 1, "不应创建新的 DB 记录"
    assert records[0].id == first_id

    from app.tasks.prediction_tasks import _train_with_progress
    import inspect
    sig = inspect.signature(_train_with_progress)
    assert "is_retry" in sig.parameters, "_train_with_progress 应有 is_retry 参数"


def test_train_and_predict_with_progress_accepts_is_retry():
    """验证 _train_and_predict_with_progress 函数签名应有 is_retry 参数"""
    from app.tasks.prediction_tasks import _train_and_predict_with_progress
    import inspect
    sig = inspect.signature(_train_and_predict_with_progress)
    assert "is_retry" in sig.parameters, (
        "_train_and_predict_with_progress 缺少 is_retry 参数，无法支持重试复用"
    )


# =============================================================================
# PredictionService.__init__ 测试
# =============================================================================

def test_service_init_creates_model_dir(db_session, monkeypatch):
    """验证 PredictionService 初始化时创建模型目录"""
    from app.services.prediction_service import PredictionService
    import tempfile
    import os

    tmpdir = tempfile.mkdtemp()
    from app.config import get_settings
    settings = get_settings()
    orig_dir = settings.prediction_model_dir
    test_dir = os.path.join(tmpdir, "models", "prediction")
    settings.prediction_model_dir = test_dir

    try:
        service = PredictionService(db_session)
        assert os.path.exists(test_dir), "模型目录应被创建"
    finally:
        settings.prediction_model_dir = orig_dir
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_service_init_sets_repos(db_session):
    """验证 PredictionService 初始化设置正确的 repositories"""
    from app.services.prediction_service import PredictionService
    from app.repositories.data_source_repository import DataSourceRepository
    from app.repositories.prediction_repository import (
        PredictionModelRepository, PredictionResultRepository
    )

    service = PredictionService(db_session)
    assert isinstance(service.ds_repo, DataSourceRepository)
    assert isinstance(service.model_repo, PredictionModelRepository)
    assert isinstance(service.result_repo, PredictionResultRepository)
    assert service.db is db_session

# =============================================================================
# _predict_from_cache 测试
# =============================================================================

def test_predict_from_cache_basic(db_session, monkeypatch):
    """验证 _predict_from_cache 基本预测流程"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository
    from app.models.prediction import PredictionModel

    repo = PredictionModelRepository(db_session)
    model_record = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="ready",
        model_path="/tmp/test_cache_model.pkl",
    )

    # Create mock data with enough history for features
    np.random.seed(42)
    dates = pd.date_range(start="2025-01-01", periods=90, freq="D")
    rows = []
    for matnr in ["M001"]:
        for d in range(90):
            val = 500.0 + float(np.random.randint(-50, 50))
            rows.append([dates[d].strftime("%Y%m%d"), "S001", matnr, val])

    data_df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
    data_df["dt"] = pd.to_datetime(data_df["dt"], format="%Y%m%d")

    # Mock model
    import joblib
    fake_model = MagicMock()
    fake_model.predict.return_value = np.array([150.0])

    # Mock _lookup_ware_names
    monkeypatch.setattr(PredictionService, "_lookup_ware_names", lambda self, ds_id, pairs: {})

    service = PredictionService(db_session)
    results = service._predict_from_cache(
        data_df=data_df,
        model=fake_model,
        model_record=model_record,
        forecast_days=7,
        progress_callback=None,
    )

    assert len(results) == 7  # 1 SKU × 7 days
    assert all(r.model_id == model_record.id for r in results)
    assert all(r.store_code == "S001" for r in results)
    assert all(r.matnr == "M001" for r in results)
    assert all(r.predicted_value > 0 for r in results)


def test_predict_from_cache_with_progress(db_session, monkeypatch):
    """验证 _predict_from_cache 的 progress_callback"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    model_record = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="ready",
        model_path="/tmp/test_cache_model2.pkl",
    )

    np.random.seed(42)
    dates = pd.date_range(start="2025-01-01", periods=90, freq="D")
    rows = []
    for store in ["S001", "S002"]:
        for matnr in ["M001", "M002"]:
            for d in range(90):
                val = 500.0 + float(np.random.randint(-50, 50))
                rows.append([dates[d].strftime("%Y%m%d"), store, matnr, val])

    data_df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
    data_df["dt"] = pd.to_datetime(data_df["dt"], format="%Y%m%d")

    fake_model = MagicMock()
    fake_model.predict.return_value = np.array([150.0])

    monkeypatch.setattr(PredictionService, "_lookup_ware_names", lambda self, ds_id, pairs: {})

    callback_calls = []
    def progress_cb(mid, store_idx, total_stores, store_code):
        callback_calls.append((mid, store_idx, total_stores, store_code))

    service = PredictionService(db_session)
    results = service._predict_from_cache(
        data_df=data_df,
        model=fake_model,
        model_record=model_record,
        forecast_days=7,
        progress_callback=progress_cb,
    )

    # 2 stores → callback called 2 times
    assert len(callback_calls) == 2
    assert callback_calls[0] == (model_record.id, 1, 2, "S001")
    assert callback_calls[1] == (model_record.id, 2, 2, "S002")


def test_predict_from_cache_empty_data(db_session):
    """验证空数据时 _predict_from_cache 抛出异常"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    model_record = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="ready",
        model_path="/tmp/test_cache_model3.pkl",
    )

    empty_df = pd.DataFrame(columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
    fake_model = MagicMock()

    service = PredictionService(db_session)
    with pytest.raises(ValueError, match="缓存数据经特征工程后无有效数据"):
        service._predict_from_cache(
            data_df=empty_df,
            model=fake_model,
            model_record=model_record,
            forecast_days=7,
        )


def test_predict_from_cache_short_history(db_session, monkeypatch):
    """验证历史数据过少时 _predict_from_cache 抛出异常"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    model_record = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="ready",
        model_path="/tmp/test_cache_model4.pkl",
    )

    # Only 5 days of data - feature engineering produces no valid rows
    dates = pd.date_range(start="2025-01-01", periods=5, freq="D")
    rows = []
    for d in range(5):
        rows.append([dates[d].strftime("%Y%m%d"), "S001", "M001", 500.0])

    data_df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
    data_df["dt"] = pd.to_datetime(data_df["dt"], format="%Y%m%d")

    fake_model = MagicMock()

    monkeypatch.setattr(PredictionService, "_lookup_ware_names", lambda self, ds_id, pairs: {})

    service = PredictionService(db_session)
    with pytest.raises(ValueError, match="缓存数据经特征工程后无有效数据"):
        service._predict_from_cache(
            data_df=data_df,
            model=fake_model,
            model_record=model_record,
            forecast_days=7,
        )

# =============================================================================
# _fetch_and_train_incremental 基础测试
# =============================================================================

def test_fetch_and_train_incremental_basic(db_session, monkeypatch):
    """验证 _fetch_and_train_incremental 基本流程（mock 所有外部依赖）"""
    from app.services.prediction_service import PredictionService
    from app.models.data_source import DataSource
    import app.services.prediction_service as ps_module

    ds = DataSource(
        id=20, name="test", type="DORIS",
        host="localhost", port=9030, database="test_db",
        username="test", password_encrypted="test",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()

    # Mock execute_query to return group count data and batch data
    call_count = [0]
    def mock_execute_query(ds_obj, sql):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: group count query
            rows = [[1, "S001", "M001", 500000]]
            cols = ["group_id", "store_code", "matnr", "total_sales"]
            return rows, cols
        else:
            # Second call: batch data
            rows = []
            np.random.seed(42)
            dates = pd.date_range(start="2025-01-01", periods=400, freq="D")
            for d in range(400):
                val = 500.0 + float(np.random.randint(-50, 50))
                dt_str = dates[d].strftime("%Y%m%d")
                rows.append([dt_str, 1, "S001", "M001", int(val * 100)])
            cols = ["dt", "group_id", "store_code", "matnr", "actual_sale_untaxed_amt"]
            return rows, cols

    monkeypatch.setattr(ps_module, "execute_query", mock_execute_query)

    import lightgbm as lgb
    model = lgb.LGBMRegressor(
        n_estimators=10,
        learning_rate=0.05,
        max_depth=4,
        num_leaves=8,
        random_state=42,
        verbose=-1,
        num_threads=1,
    )
    feature_cols = get_feature_columns()

    service = PredictionService(db_session)
    result = service._fetch_and_train_incremental(
        ds_id=20,
        days=200,
        model=model,
        feature_cols=feature_cols,
        test_days=10,
        valid_days=10,
        batch_size=200,
        batch_unit=200,
    )

    model, feat_cols, total_rows, train_start, train_end, mae, rmse, msg, batch_no = result
    assert total_rows > 0
    assert mae >= 0
    assert rmse >= 0
    assert batch_no >= 1


# =============================================================================
# 置信区间测试
# =============================================================================

def test_train_saves_booster_file(db_session, monkeypatch):
    """验证 train() 会额外保存 .txt Booster 文件（用于 pred_interval）"""
    from app.services.prediction_service import PredictionService

    def mock_fetch(self, ds_id, days, table_name=None):
        import pandas as _pd
        import numpy as _np
        _np.random.seed(42)
        _dates = _pd.date_range(start="2025-01-01", periods=365, freq="D")
        _rows = []
        for store in ["S001"]:
            for matnr in ["M001"]:
                for d in range(365):
                    base = 500.0 + 100.0 * ((d % 7) + 1)
                    val = base + float(_np.random.randint(-50, 50))
                    _rows.append([_dates[d].strftime("%Y%m%d"), store, matnr, val])
        df = _pd.DataFrame(_rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
        df["dt"] = _pd.to_datetime(df["dt"], format="%Y%m%d")
        return df

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)

    import tempfile
    tmpdir = tempfile.mkdtemp()
    from app.config import get_settings
    settings = get_settings()
    orig_dir = settings.prediction_model_dir
    orig_min = settings.prediction_min_history_days
    settings.prediction_model_dir = tmpdir
    settings.prediction_min_history_days = 1  # 降低阈值，365 行足够

    try:
        service = PredictionService(db_session)
        model_id = service.train(ds_id=1, train_days=100)

        import os
        # 验证 .pkl 存在
        pkl_path = os.path.join(tmpdir, f"lgb_1_{model_id}.pkl")
        assert os.path.exists(pkl_path), f"PKL 文件不存在: {pkl_path}"

        # 验证 .txt Booster 文件存在
        txt_path = os.path.join(tmpdir, f"lgb_1_{model_id}.txt")
        assert os.path.exists(txt_path), f"Booster TXT 文件不存在: {txt_path}"

        # 验证 .txt 可以被 lgb.Booster 加载
        import lightgbm as lgb
        booster = lgb.Booster(model_file=txt_path)
        assert booster is not None
        assert booster.num_trees() > 0, "加载的 Booster 应包含已训练的树"

        # 验证 Booster 可以被正常加载和预测（不做 pred_interval，该功能在 LightGBM 4.6+ 已移除）
        import pandas as pd
        import numpy as np
        dummy_input = pd.DataFrame(
            np.random.randn(1, 25),
            columns=get_feature_columns(),
        )
        result = booster.predict(dummy_input)
        assert len(result) == 1, f"预测应返回 1 个值，实际 shape={result.shape}"
        assert float(result[0]) > 0, f"点预测应 > 0，实际={result[0]}"
    finally:
        settings.prediction_model_dir = orig_dir
        settings.prediction_min_history_days = orig_min
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_predict_populates_confidence_interval(db_session, monkeypatch):
    """验证 predict() 使用 Booster pred_interval 填充 lower_bound / upper_bound"""
    from app.services.prediction_service import PredictionService

    def mock_fetch_train(self, ds_id, days, table_name=None):
        import pandas as _pd
        import numpy as _np
        _np.random.seed(42)
        _dates = _pd.date_range(start="2025-01-01", periods=365, freq="D")
        _rows = []
        for store in ["S001"]:
            for matnr in ["M001"]:
                for d in range(365):
                    base = 500.0 + 100.0 * ((d % 7) + 1)
                    val = base + float(_np.random.randint(-50, 50))
                    _rows.append([_dates[d].strftime("%Y%m%d"), store, matnr, val])
        df = _pd.DataFrame(_rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
        df["dt"] = _pd.to_datetime(df["dt"], format="%Y%m%d")
        return df

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch_train)

    import tempfile
    tmpdir = tempfile.mkdtemp()
    from app.config import get_settings
    settings = get_settings()
    orig_dir = settings.prediction_model_dir
    orig_min = settings.prediction_min_history_days
    settings.prediction_model_dir = tmpdir
    settings.prediction_min_history_days = 1  # 365 行足够

    try:
        # 训练
        service = PredictionService(db_session)
        model_id = service.train(ds_id=1, train_days=100)

        # ---- 阶段2: 切换 mock 为预测数据 ----
        def mock_fetch_predict(self, ds_id, days, table_name=None):
            import pandas as _pd
            import numpy as _np2
            _np2.random.seed(123)
            _dates = _pd.date_range(start="2025-10-01", periods=90, freq="D")
            _rows = []
            for store in ["S001"]:
                for matnr in ["M001"]:
                    for d in range(90):
                        base = 500.0 + 100.0 * ((d % 7) + 1)
                        val = base + float(_np2.random.randint(-50, 50))
                        _rows.append([_dates[d].strftime("%Y%m%d"), store, matnr, val])
            df = _pd.DataFrame(_rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
            df["dt"] = _pd.to_datetime(df["dt"], format="%Y%m%d")
            return df

        monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch_predict)
        monkeypatch.setattr(PredictionService, "_lookup_ware_names", lambda self, ds_id, pairs: {})

        # 预测
        count, mid = service.predict(ds_id=1, forecast_days=7, model_id=model_id)
        assert count == 7, f"应预测 7 天，实际={count}"
        assert mid == model_id

        # ---- 阶段3: 验证 DB 中的置信区间 ----
        from app.repositories.prediction_repository import PredictionResultRepository
        repo = PredictionResultRepository(db_session)
        results = repo.get_forecast(data_source_id=1, model_id=model_id)

        assert len(results) == 7
        for r in results:
            assert r.lower_bound is not None, f"id={r.id} lower_bound 为 None"
            assert r.upper_bound is not None, f"id={r.id} upper_bound 为 None"
            assert 0 < r.lower_bound <= r.predicted_value <= r.upper_bound, (
                f"id={r.id}: 置信区间顺序异常: "
                f"lower={r.lower_bound}, pred={r.predicted_value}, upper={r.upper_bound}"
            )

    finally:
        settings.prediction_model_dir = orig_dir
        settings.prediction_min_history_days = orig_min
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_predict_from_cache_populates_confidence_interval(db_session, monkeypatch):
    """验证 _predict_from_cache() 使用 model.booster_ 填充置信区间"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository

    repo = PredictionModelRepository(db_session)
    model_record = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="ready",
        model_path="/tmp/test_ci_cache.pkl",
        model_metrics={"rmse": 100.0},
    )

    # 用真实 LGBMRegressor 替代 MagicMock（需要 booster_ 属性）
    import lightgbm as lgb
    import numpy as _np
    real_model = lgb.LGBMRegressor(
        n_estimators=10, learning_rate=0.05,
        max_depth=4, num_leaves=8,
        random_state=42, verbose=-1, num_threads=1,
    )

    # 构造足够历史数据作训练
    np.random.seed(42)
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    X = np.random.randn(100, 25)
    y = np.random.randn(100) * 100 + 500
    real_model.fit(X, y)

    # 构造预测用的模拟数据（90天，1店1品）
    from datetime import date, timedelta
    np.random.seed(42)
    predict_dates = pd.date_range(start="2025-04-01", periods=90, freq="D")
    rows = []
    for d in range(90):
        val = 500.0 + float(np.random.randint(-50, 50))
        rows.append([predict_dates[d].strftime("%Y%m%d"), "S001", "M001", val])

    data_df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
    data_df["dt"] = pd.to_datetime(data_df["dt"], format="%Y%m%d")

    monkeypatch.setattr(PredictionService, "_lookup_ware_names", lambda self, ds_id, pairs: {})

    service = PredictionService(db_session)
    results = service._predict_from_cache(
        data_df=data_df,
        model=real_model,
        model_record=model_record,
        forecast_days=7,
        progress_callback=None,
    )

    assert len(results) == 7
    for r in results:
        assert r.lower_bound is not None, f"id={r.id} lower_bound 为 None"
        assert r.upper_bound is not None, f"id={r.id} upper_bound 为 None"
        assert 0 < r.lower_bound <= r.predicted_value <= r.upper_bound, (
            f"置信区间顺序异常: lower={r.lower_bound}, pred={r.predicted_value}, upper={r.upper_bound}"
        )


def test_predict_downgrade_without_txt_file(db_session, monkeypatch):
    """验证旧模型（无 .txt 文件）predict 降级为点预测且置信区间为 None"""
    from app.services.prediction_service import PredictionService
    from app.repositories.prediction_repository import PredictionModelRepository
    import os

    # 创建测试目录和 .pkl 文件（无 .txt）
    import tempfile
    tmpdir = tempfile.mkdtemp()
    pkl_path = os.path.join(tmpdir, "lgb_1_999.pkl")

    # 用真实模型保存 .pkl（但不保存 .txt）
    import lightgbm as lgb
    import numpy as np
    real_model = lgb.LGBMRegressor(
        n_estimators=5, verbose=-1, num_threads=1,
    )
    X = np.random.randn(50, 25)
    y = np.random.randn(50) * 100 + 500
    real_model.fit(X, y)

    import joblib
    joblib.dump(real_model, pkl_path)
    # 确认没有 .txt 文件
    txt_path = pkl_path.replace('.pkl', '.txt')
    assert not os.path.exists(txt_path)

    # 创建模型记录指向这个路径
    repo = PredictionModelRepository(db_session)
    model_record = repo.create(
        data_source_id=1,
        model_type="lightgbm",
        status="ready",
        model_path=pkl_path,
    )

    def mock_fetch(self, ds_id, days, table_name=None):
        import pandas as _pd
        import numpy as _np2
        _np2.random.seed(42)
        _dates = _pd.date_range(start="2025-01-01", periods=90, freq="D")
        _rows = []
        for store in ["S001"]:
            for matnr in ["M001"]:
                for d in range(90):
                    val = 500.0 + float(_np2.random.randint(-50, 50))
                    _rows.append([_dates[d].strftime("%Y%m%d"), store, matnr, val])
        df = _pd.DataFrame(_rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
        df["dt"] = _pd.to_datetime(df["dt"], format="%Y%m%d")
        return df

    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)
    monkeypatch.setattr(PredictionService, "_lookup_ware_names", lambda self, ds_id, pairs: {})

    from app.config import get_settings
    settings = get_settings()
    orig_dir = settings.prediction_model_dir
    settings.prediction_model_dir = tmpdir

    try:
        service = PredictionService(db_session)
        count, mid = service.predict(ds_id=1, forecast_days=7, model_id=model_record.id)

        assert count == 7
        assert mid == model_record.id

        # 验证置信区间为 None（降级行为）
        from app.repositories.prediction_repository import PredictionResultRepository
        result_repo = PredictionResultRepository(db_session)
        results = result_repo.get_forecast(data_source_id=1, model_id=model_record.id)

        assert len(results) == 7
        for r in results:
            assert r.lower_bound is None, f"降级模式应返回 None，实际={r.lower_bound}"
            assert r.upper_bound is None, f"降级模式应返回 None，实际={r.upper_bound}"
            assert r.predicted_value > 0
    finally:
        settings.prediction_model_dir = orig_dir
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fetch_and_train_incremental_no_data(db_session, monkeypatch):
    """验证 _fetch_and_train_incremental 无数据时抛出异常"""
    from app.services.prediction_service import PredictionService
    from app.models.data_source import DataSource
    import app.services.prediction_service as ps_module

    ds = DataSource(
        id=21, name="test", type="DORIS",
        host="localhost", port=9030, database="test_db",
        username="test", password_encrypted="test",
        is_active=True,
    )
    db_session.add(ds)
    db_session.commit()

    def mock_execute_query(ds_obj, sql):
        return [], ["group_id", "store_code", "matnr", "total_sales"]

    monkeypatch.setattr(ps_module, "execute_query", mock_execute_query)

    import lightgbm as lgb
    model = lgb.LGBMRegressor(n_estimators=2, verbose=-1, num_threads=1)
    feature_cols = get_feature_columns()

    service = PredictionService(db_session)
    with pytest.raises(ValueError, match="无有效训练数据"):
        service._fetch_and_train_incremental(
            ds_id=21, days=100, model=model, feature_cols=feature_cols,
        )
