"""预测服务单元测试"""
import pytest
import pandas as pd
import numpy as np
from app.utils.feature_engineering import build_features_from_history, get_feature_columns


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


def test_train_with_mock_data(db_session, monkeypatch):
    """Mock 历史数据，验证训练流程可以走通"""
    from app.services.prediction_service import PredictionService

    # Mock _fetch_history_data 返回人工数据
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

    # Mock model_dir to not pollute production
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

        # 验证模型已保存
        import os
        model_path = os.path.join(tmpdir, f"lgb_1_{model_id}.pkl")
        assert os.path.exists(model_path), f"模型文件不存在: {model_path}"

        # 验证数据库记录
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


def test_predict_without_model(db_session):
    """验证没有训练好的模型时 predict 会报错"""
    from app.services.prediction_service import PredictionService

    service = PredictionService(db_session)
    with pytest.raises(ValueError, match="没有已训练好的模型"):
        service.predict(ds_id=1, forecast_days=7)
