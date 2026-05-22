"""预测算法单元测试 — NaivePredictor, SARIMAPredictor

测试策略：每个算法测试 train / predict / save / load 四个接口方法。
使用 DataFrame 构造模拟时序数据，不需要数据库连接。
"""

import pytest
import os
import tempfile
import shutil
import numpy as np
import pandas as pd
from unittest.mock import MagicMock
from datetime import date, timedelta, datetime

from app.algorithms.base import MIN_PREDICTION
from app.algorithms.naive_predictor import NaivePredictor
from app.algorithms.sarima_predictor import SARIMAPredictor


def _make_history(days: int = 90, stores: int = 2, skus: int = 2) -> pd.DataFrame:
    """构造带周季节性的模拟历史销售数据

    基础值 500 + 周末上浮 100 + 随机噪声。
    """
    np.random.seed(42)
    rows = []
    end = date(2026, 5, 22)
    dates = [end - timedelta(days=i) for i in range(days - 1, -1, -1)]
    for store_idx in range(stores):
        store_code = f"S{store_idx + 1:03d}"
        for sku_idx in range(skus):
            matnr = f"M{sku_idx + 1:03d}"
            for d in dates:
                # 周季节性：周末高 100
                base = 500.0 + (100.0 if d.weekday() >= 5 else 0.0)
                val = base + float(np.random.randint(-30, 30))
                rows.append([d.strftime("%Y%m%d"), store_code, matnr, val])
    df = pd.DataFrame(
        rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"]
    )
    df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d")
    return df


def _make_model_record(model_type: str = "naive") -> MagicMock:
    """构造模型记录 mock"""
    m = MagicMock()
    m.id = 1
    m.data_source_id = 1
    m.model_type = model_type
    m.model_path = "/tmp/test_model.pkl"
    m.model_metrics = {}
    return m


# =============================================================================
# NaivePredictor
# =============================================================================


class TestNaivePredictor:
    """Naive 季节性基线测试"""

    def test_model_type(self):
        assert NaivePredictor.MODEL_TYPE == "naive"

    def test_train_organizes_groups(self):
        """验证 train 按 (store, matnr) 分组整理历史"""
        df = _make_history(days=60, stores=2, skus=2)
        algo = NaivePredictor()
        model_record = _make_model_record("naive")

        data, metrics = algo.train(df, model_record, service=None)

        # 4 个分组
        assert len(data) == 4
        for key, grp in data.items():
            store, matnr = key
            assert isinstance(store, str)
            assert isinstance(matnr, str)
            assert TARGET_COL in grp.columns
            assert "dow" in grp.columns
            # 最多 56 天（LOOKBACK_WEEKS=8）
            assert len(grp) <= 56
        assert metrics["model_count"] == 4

    def test_train_drops_short_groups(self):
        """验证历史不足 7 天的分组被丢弃"""
        df = _make_history(days=5, stores=1, skus=1)  # 只有 5 天
        algo = NaivePredictor()
        model_record = _make_model_record("naive")

        with pytest.raises(ValueError, match="无有效分组"):
            algo.train(df, model_record, service=None)

    def test_train_metrics_structure(self):
        """验证训练返回指标结构"""
        df = _make_history(days=60, stores=2, skus=1)
        algo = NaivePredictor()
        model_record = _make_model_record("naive")

        data, metrics = algo.train(df, model_record, service=None)
        assert "model_count" in metrics
        assert metrics["model_count"] == 2

    def test_predict_returns_results(self):
        """验证 predict 返回 PredictionResult 列表"""
        df = _make_history(days=90, stores=1, skus=1)
        algo = NaivePredictor()
        model_record = _make_model_record("naive")
        service = MagicMock()
        service._lookup_ware_names.return_value = {}

        data, _ = algo.train(df, model_record, service=service)
        results = algo.predict(
            data, model_record, df, forecast_days=7, service=service
        )

        assert len(results) == 7
        for r in results:
            assert r.model_id == 1
            assert r.data_source_id == 1
            assert r.store_code == "S001"
            assert r.matnr == "M001"
            assert r.predicted_value > 0
            assert r.lower_bound is not None
            assert r.upper_bound is not None
            assert r.lower_bound <= r.predicted_value <= r.upper_bound

    def test_predict_weeks_each_dow(self):
        """验证不同 weekday 产出不同预测值（季节性）"""
        df = _make_history(days=90, stores=1, skus=1)
        algo = NaivePredictor()
        model_record = _make_model_record("naive")
        service = MagicMock()
        service._lookup_ware_names.return_value = {}

        data, _ = algo.train(df, model_record, service=service)
        results = algo.predict(
            data, model_record, df, forecast_days=14, service=service
        )

        # 两周 → 14 条
        assert len(results) == 14
        # 相邻周同 weekday 的预测值应该非常接近（Naive 基线性质）
        preds = [r.predicted_value for r in results]
        # 第 0 天和第 7 天是同 weekday
        assert abs(preds[0] - preds[7]) < 1.0, (
            f"相邻周同日预测值应相近: {preds[0]} vs {preds[7]}"
        )
        assert abs(preds[1] - preds[8]) < 1.0

    def test_predict_min_prediction_floor(self):
        """验证极小预测值被 MIN_PREDICTION=0.01 兜底"""
        df = _make_history(days=90, stores=1, skus=1)
        # 把历史值全部置为 0
        df["actual_sale_untaxed_amt"] = 0.0

        algo = NaivePredictor()
        model_record = _make_model_record("naive")
        service = MagicMock()
        service._lookup_ware_names.return_value = {}

        data, _ = algo.train(df, model_record, service=service)
        results = algo.predict(
            data, model_record, df, forecast_days=3, service=service
        )

        for r in results:
            assert r.predicted_value >= MIN_PREDICTION, (
                f"预测值应被兜底: {r.predicted_value} < {MIN_PREDICTION}"
            )

    def test_predict_multiple_stores_skus(self):
        """验证多门店多商品预测返回正确数量"""
        df = _make_history(days=60, stores=3, skus=3)
        algo = NaivePredictor()
        model_record = _make_model_record("naive")
        service = MagicMock()
        service._lookup_ware_names.return_value = {}

        data, _ = algo.train(df, model_record, service=service)
        results = algo.predict(
            data, model_record, df, forecast_days=10, service=service
        )

        # 9 个分组 × 10 天 = 90 条
        assert len(results) == 9 * 10

    def test_save_load_roundtrip(self):
        """验证 save/load 序列化往返"""
        df = _make_history(days=60, stores=1, skus=2)
        algo = NaivePredictor()
        model_record = _make_model_record("naive")

        data, _ = algo.train(df, model_record, service=None)

        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "naive_model.pkl")
            algo.save(data, path)
            assert os.path.exists(path)

            loaded = algo.load(path)
            assert len(loaded) == 2
            for key in data:
                assert key in loaded
                pd.testing.assert_frame_equal(loaded[key], data[key])
        finally:
            shutil.rmtree(tmpdir)

    def test_predict_lookup_ware_names(self):
        """验证 predict 会调用 _lookup_ware_names 补商品名称"""
        df = _make_history(days=60, stores=1, skus=1)
        algo = NaivePredictor()
        model_record = _make_model_record("naive")

        data, _ = algo.train(df, model_record, service=None)

        # Mock service 的 _lookup_ware_names
        service = MagicMock()
        service._lookup_ware_names.return_value = {("S001", "M001"): "测试商品"}

        results = algo.predict(data, model_record, df, forecast_days=3, service=service)

        assert len(results) == 3
        for r in results:
            assert r.ware_name == "测试商品"

        service._lookup_ware_names.assert_called_once()


# =============================================================================
# SARIMAPredictor
# =============================================================================


class TestSARIMAPredictor:
    """SARIMA 预测算法测试

    注意：SARIMA 对短序列<14天会跳过，所以测试数据需要至少 30 天。
    """

    def test_model_type(self):
        assert SARIMAPredictor.MODEL_TYPE == "sarima"

    def test_train_fits_models(self):
        """验证 train 为每个分组拟合 SARIMA"""
        df = _make_history(days=60, stores=1, skus=1)
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")

        models, metrics = algo.train(df, model_record, service=None)

        assert len(models) == 1
        assert ("S001", "M001") in models
        assert "mae" in metrics
        assert "rmse" in metrics
        assert metrics["model_count"] == 1

    def test_train_multiple_groups(self):
        """验证多分组并行训练"""
        df = _make_history(days=60, stores=2, skus=2)
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")

        models, metrics = algo.train(df, model_record, service=None)

        assert len(models) == 4
        assert metrics["model_count"] == 4
        assert metrics["mae"] >= 0

    def test_train_requires_14_days(self):
        """验证历史<14天的分组被跳过"""
        df = _make_history(days=7, stores=1, skus=1)  # 只有 7 天
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")

        with pytest.raises(ValueError, match="无有效分组"):
            algo.train(df, model_record, service=None)

    def test_train_metrics_reasonable(self):
        """验证训练指标在合理范围内"""
        df = _make_history(days=90, stores=1, skus=1)
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")

        models, metrics = algo.train(df, model_record, service=None)

        assert 0 <= metrics["mae"] < 200
        assert 0 <= metrics["rmse"] < 300

    def test_predict_returns_results(self):
        """验证 predict 返回预测结果（含置信区间）"""
        df = _make_history(days=90, stores=1, skus=1)
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")
        service = MagicMock()
        service._lookup_ware_names.return_value = {}

        models, metrics = algo.train(df, model_record, service=service)
        # 保存训练 RMSE 到 model_record 供置信区间降级使用
        model_record.model_metrics = metrics

        results = algo.predict(
            models, model_record, df, forecast_days=7, service=service
        )

        assert len(results) == 7
        for r in results:
            assert r.model_id == 1
            assert r.store_code == "S001"
            assert r.matnr == "M001"
            assert r.predicted_value > 0
            assert r.lower_bound is not None
            assert r.upper_bound is not None
            assert r.lower_bound <= r.predicted_value <= r.upper_bound, (
                f"置信区间顺序异常: lower={r.lower_bound}, "
                f"pred={r.predicted_value}, upper={r.upper_bound}"
            )

    def test_predict_short_series_still_works(self):
        """验证短序列(14-20天)降级为 ARIMA 仍可预测"""
        df = _make_history(days=18, stores=1, skus=1)
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")
        service = MagicMock()
        service._lookup_ware_names.return_value = {}

        models, metrics = algo.train(df, model_record, service=service)
        model_record.model_metrics = metrics
        results = algo.predict(
            models, model_record, df, forecast_days=3, service=service
        )

        assert len(results) == 3
        for r in results:
            assert r.predicted_value > 0

    def test_predict_min_prediction_floor(self):
        """验证极小预测值被 MIN_PREDICTION=0.01 兜底"""
        # 构造极小平稳序列
        np.random.seed(42)
        rows = []
        for d in range(60):
            dt_str = (date(2026, 1, 1) + timedelta(days=d)).strftime("%Y%m%d")
            rows.append([dt_str, "S001", "M001", 0.01])
        df = pd.DataFrame(
            rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"]
        )
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d")

        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")
        service = MagicMock()
        service._lookup_ware_names.return_value = {}

        models, metrics = algo.train(df, model_record, service=service)
        model_record.model_metrics = metrics
        results = algo.predict(
            models, model_record, df, forecast_days=3, service=service
        )

        for r in results:
            assert r.predicted_value >= MIN_PREDICTION, (
                f"预测值应被兜底: {r.predicted_value} < {MIN_PREDICTION}"
            )

    def test_save_load_roundtrip(self):
        """验证 save/load 序列化往返"""
        df = _make_history(days=60, stores=1, skus=1)
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")

        models, _ = algo.train(df, model_record, service=None)

        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "sarima_model.pkl")
            algo.save(models, path)
            assert os.path.exists(path)

            loaded = algo.load(path)
            assert len(loaded) == 1
            assert ("S001", "M001") in loaded
        finally:
            shutil.rmtree(tmpdir)

    def test_predict_multiple_groups(self):
        """验证多分组预测数量正确"""
        df = _make_history(days=60, stores=2, skus=2)
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")
        service = MagicMock()
        service._lookup_ware_names.return_value = {}

        models, metrics = algo.train(df, model_record, service=service)
        model_record.model_metrics = metrics
        results = algo.predict(
            models, model_record, df, forecast_days=5, service=service
        )

        # 4 分组 × 5 天 = 20 条
        assert len(results) == 4 * 5

    def test_predict_lookup_ware_names(self):
        """验证 predict 会调用 _lookup_ware_names"""
        df = _make_history(days=60, stores=1, skus=1)
        algo = SARIMAPredictor()
        model_record = _make_model_record("sarima")

        models, _ = algo.train(df, model_record, service=None)

        service = MagicMock()
        service._lookup_ware_names.return_value = {("S001", "M001"): "测试商品"}

        results = algo.predict(
            models, model_record, df, forecast_days=3, service=service
        )

        for r in results:
            assert r.ware_name == "测试商品"


# =============================================================================
# Cross-Algorithm 一致性
# =============================================================================

TARGET_COL = "actual_sale_untaxed_amt"


class TestAlgorithmConsistency:
    """算法接口一致性测试"""

    def test_all_implement_base(self):
        """验证所有已注册算法继承 BasePredictor"""
        from app.algorithms import BasePredictor
        # 手动导入，避免可选依赖缺失导致测试失败
        assert issubclass(NaivePredictor, BasePredictor)
        assert issubclass(SARIMAPredictor, BasePredictor)
        from app.algorithms.lightgbm_predictor import LightGBMPredictor
        assert issubclass(LightGBMPredictor, BasePredictor)

    def test_all_have_model_type(self):
        """验证所有算法有 MODEL_TYPE 类属性"""
        assert NaivePredictor.MODEL_TYPE == "naive"
        assert SARIMAPredictor.MODEL_TYPE == "sarima"
        from app.algorithms.lightgbm_predictor import LightGBMPredictor
        assert LightGBMPredictor.MODEL_TYPE == "lightgbm"

    def test_import_from_init(self):
        """验证 algorithms 包导出所有非可选依赖的符号"""
        from app.algorithms import (
            BasePredictor, MIN_PREDICTION,
            LightGBMPredictor, NaivePredictor,
        )
        assert BasePredictor is not None
        assert MIN_PREDICTION == 0.01
        assert LightGBMPredictor.MODEL_TYPE == "lightgbm"
        assert NaivePredictor.MODEL_TYPE == "naive"
