"""Prophet 预测算法实现

改进：
1. 中文节假日效应（春节/国庆等对零售影响显著）
2. 并行训练（ThreadPool → 多组同时 fit）
3. 自适应 Changepoint（短序列保守、长序列灵活）
4. 减少 uncertainty_samples 提速

（全部改动局限在本文件内，不影响其他算法的数据输入）
"""

from __future__ import annotations
import os
import logging
import joblib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple
from datetime import timedelta

import numpy as np
import pandas as pd
from prophet import Prophet

from app.algorithms.base import BasePredictor, MIN_PREDICTION
from app.models.prediction import PredictionResult

logger = logging.getLogger(__name__)

# 抑制 Prophet 底层 Stan/CmdStanPy 的 Chain 日志刷屏
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

TARGET_COL = "actual_sale_untaxed_amt"

# 并行训练配置
_TRAIN_WORKERS = 4  # 同时训练 4 个 Prophet 模型


class ProphetPredictor(BasePredictor):
    """基于 Prophet 的销售预测

    每个 (store_code, matnr) 独立训练一个 Prophet 模型。
    Prophet 原生输出 yhat_lower / yhat_upper 作为置信区间，
    无需额外的 RMSE 近似。
    """

    MODEL_TYPE = "prophet"

    # Prophet 超参数
    GROWTH = "logistic"  # logistic 增长，配合 floor=0 确保预测值不低于 0
    SEASONALITY_MODE = "additive"  # 加法季节性，趋势下降时仍保持合理预测
    WEEKLY_SEASONALITY = True
    DAILY_SEASONALITY = False
    YEARLY_SEASONALITY = False   # 关闭内置年季节性，用自定义的（fourier_order=3 更简洁）
    UNCERTAINTY_SAMPLES = 300   # 300 已足够稳定，比 1000 快 3x+
    CHANGEPOINT_PRIOR_SCALE = 0.05  # 默认值，会被 _adaptive_changepoint 覆盖
    SEASONALITY_PRIOR_SCALE = 10.0  # 季节性强度
    # 节假日
    HOLIDAY_COUNTRY = "CN"      # 中文节假日（春节、国庆、端午等）

    def __init__(self, forecast_days: int = 30):
        self.forecast_days = forecast_days

    # ── 内部辅助 ──────────────────────────────────────────

    @staticmethod
    def _adaptive_changepoint(n_samples: int) -> float:
        """根据样本量自适应调整 changepoint_prior_scale

        - 短序列 (< 90 天): 0.01（保守，防止过拟合）
        - 中等 (90~365 天): 0.05（默认）
        - 长序列 (> 365 天): 0.10（灵活捕捉趋势变化）
        """
        if n_samples < 90:
            return 0.01
        elif n_samples < 365:
            return 0.05
        else:
            return 0.10

    @staticmethod
    def _train_single_group(
        store: str,
        matnr: str,
        grp: pd.DataFrame,
    ) -> Optional[Tuple[Tuple[str, str], Prophet, float, float]]:
        """训练单个 (store, matnr) 的 Prophet 模型

        设计为静态方法以便 ThreadPoolExecutor 并行调用。

        Returns:
            ((store, matnr), model, mae, rmse) 或 None（数据不足时跳过）
        """
        grp = grp.sort_values("dt").dropna(subset=[TARGET_COL])
        if len(grp) < 14:
            return None

        n_samples = len(grp)
        changepoint = ProphetPredictor._adaptive_changepoint(n_samples)

        # 准备 Prophet 输入
        prophet_df = grp[["dt", TARGET_COL]].rename(columns={
            "dt": "ds",
            TARGET_COL: "y",
        })
        # Logistic 增长需要 cap（上界）和 floor（下界=0）
        y_max = prophet_df["y"].max()
        prophet_df["cap"] = max(y_max * 1.2, 1.0)
        prophet_df["floor"] = 0.0

        # 训练 Prophet
        m = Prophet(
            growth="logistic",
            seasonality_mode="additive",
            weekly_seasonality=True,
            daily_seasonality=False,
            yearly_seasonality=False,
            uncertainty_samples=300,
            changepoint_prior_scale=changepoint,
            seasonality_prior_scale=10.0,
        )
        # 月季节性 + 年季节性
        m.add_seasonality(name="monthly", period=30.5, fourier_order=5)
        m.add_seasonality(name="yearly", period=365.25, fourier_order=3)
        # 中文节假日效应
        m.add_country_holidays(country_name="CN")

        m.fit(prophet_df)

        # 训练集评估
        forecast = m.predict(prophet_df)
        y_true = prophet_df["y"].values
        y_pred = forecast["yhat"].values
        mae = float(np.mean(np.abs(y_true - y_pred)))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

        return ((store, matnr), m, mae, rmse)

    # ── train ──────────────────────────────────────────────
    def train(
        self,
        df: pd.DataFrame,
        model_record: Any,
        service: Any,
        **kwargs,
    ) -> Tuple[Dict, Dict[str, Any]]:
        """为每个 (store_code, matnr) 训练独立的 Prophet 模型

        使用 ThreadPoolExecutor 并行训练，每 4 组同时进行。
        每组使用自适应 changepoint + 中文节假日。

        Args:
            df: 历史销售数据，包含 dt, store_code, matnr, actual_sale_untaxed_amt
            model_record: PredictionModel 对象
            service: PredictionService 实例

        Returns:
            (models_dict, metrics)
            models_dict = {(store_code, matnr): Prophet}
            metrics = {"mae": ..., "rmse": ...}
        """
        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["dt"]):
            df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d", errors="coerce")

        groups = list(df.groupby(["store_code", "matnr"]))
        total = len(groups)
        logger.info(
            f"[Prophet] 训练开始: {total} 个分组, "
            f"workers={_TRAIN_WORKERS}, uncertainty_samples={self.UNCERTAINTY_SAMPLES}"
        )

        models: Dict[Tuple[str, str], Prophet] = {}
        all_mae: list[float] = []
        all_rmse: list[float] = []
        completed = 0

        # 并行训练
        with ThreadPoolExecutor(max_workers=_TRAIN_WORKERS) as executor:
            future_map = {}
            for (store, matnr), grp in groups:
                fut = executor.submit(
                    self._train_single_group, store, matnr, grp
                )
                future_map[fut] = (store, matnr)

            for fut in as_completed(future_map):
                store, matnr = future_map[fut]
                try:
                    result = fut.result()
                except Exception as e:
                    logger.warning(f"[Prophet] {store}/{matnr} 训练异常: {e}")
                    continue

                if result is None:
                    continue

                key, model, mae, rmse = result
                models[key] = model
                all_mae.append(mae)
                all_rmse.append(rmse)

                completed += 1
                if completed % 50 == 0 or completed == 1:
                    logger.info(f"[Prophet] 训练进度 {completed}/{total}")

        if not models:
            raise ValueError("Prophet 训练失败：无有效分组（每组需要至少 14 天数据）")

        avg_mae = float(np.mean(all_mae)) if all_mae else 0.0
        avg_rmse = float(np.mean(all_rmse)) if all_rmse else 0.0
        metrics = {
            "mae": round(avg_mae, 2),
            "rmse": round(avg_rmse, 2),
            "model_count": len(models),
        }
        logger.info(
            f"[Prophet] 训练完成: {len(models)} 个模型, "
            f"MAE={avg_mae:.2f}, RMSE={avg_rmse:.2f}"
        )

        return models, metrics

    # ── predict ────────────────────────────────────────────
    def predict(
        self,
        model: Dict[Tuple[str, str], Prophet],
        model_record: Any,
        df: pd.DataFrame,
        forecast_days: int,
        service: Any,
        **kwargs,
    ) -> List[PredictionResult]:
        """用已训练的 Prophet 模型逐门店-商品预测

        Args:
            model: train() 返回的 {(store, matnr): Prophet} 字典
            model_record: PredictionModel ORM 对象
            df: 最新历史数据（仅用于确定日期范围）
            forecast_days: 预测天数
            service: PredictionService 实例

        Returns:
            List[PredictionResult]
        """
        if not pd.api.types.is_datetime64_any_dtype(df["dt"]):
            df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d", errors="coerce")

        groups = list(model.keys())
        logger.info(f"[Prophet] 预测开始: {len(groups)} 个分组, "
                     f"forecast_days={forecast_days}")

        results: List[PredictionResult] = []
        for idx, (store_code, matnr) in enumerate(groups):
            m = model[(store_code, matnr)]

            # 获取该 SKU 最后日期，用于推算未来日期
            sku_df = df[(df["store_code"] == store_code) & (df["matnr"] == matnr)]
            if sku_df.empty:
                logger.debug(f"[Prophet] 跳过 {store_code}/{matnr}: 无历史数据")
                continue
            last_date = sku_df["dt"].max()

            # 计算 Logistic 增长所需的 cap（与 train() 保持一致）
            sku_y = sku_df[TARGET_COL]
            cap_value = max(float(sku_y.max()) * 1.2, 1.0)

            # Prophet 生成未来日期（Logistic 增长需 cap + floor）
            future = m.make_future_dataframe(
                periods=forecast_days,
                include_history=False,
            )
            future["cap"] = cap_value
            future["floor"] = 0.0
            forecast = m.predict(future)

            for i, (_, row) in enumerate(forecast.iterrows()):
                pred = max(float(row["yhat"]), MIN_PREDICTION)
                lower = max(float(row["yhat_lower"]), 0.0)
                upper = max(float(row["yhat_upper"]), 0.0)

                forecast_date = last_date + timedelta(days=i + 1)

                results.append(PredictionResult(
                    model_id=model_record.id,
                    data_source_id=model_record.data_source_id,
                    store_code=store_code,
                    matnr=matnr,
                    forecast_date=forecast_date.date(),
                    predicted_value=round(pred, 2),
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                ))

            if (idx + 1) % 100 == 0:
                logger.info(f"[Prophet] 预测进度 {idx+1}/{len(groups)}")

        # 批量查询商品名称
        if results:
            unique_pairs = list({(r.store_code, r.matnr) for r in results})
            ware_name_map = service._lookup_ware_names(
                model_record.data_source_id, unique_pairs
            )
            for r in results:
                r.ware_name = ware_name_map.get((r.store_code, r.matnr), "")

        logger.info(f"[Prophet] 预测完成: {len(results)} 条结果")
        return results

    # ── save / load ────────────────────────────────────────
    def save(self, model: Dict[Tuple[str, str], Prophet], model_path: str) -> None:
        """序列化 Prophet 模型字典"""
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)
        logger.info(f"[Prophet] 模型已保存: {model_path}")

    def load(self, model_path: str) -> Dict[Tuple[str, str], Prophet]:
        model = joblib.load(model_path)
        logger.info(f"[Prophet] 模型已加载: {model_path} ({len(model)} 个分组)")
        return model
