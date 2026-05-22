"""Prophet 预测算法实现"""

from __future__ import annotations
import os
import logging
import joblib
from typing import Any, Dict, List, Optional, Tuple
from datetime import timedelta

import numpy as np
import pandas as pd
from prophet import Prophet

from app.algorithms.base import BasePredictor
from app.models.prediction import PredictionResult

logger = logging.getLogger(__name__)

# 抑制 Prophet 底层 Stan/CmdStanPy 的 Chain 日志刷屏
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

TARGET_COL = "actual_sale_untaxed_amt"


class ProphetPredictor(BasePredictor):
    """基于 Prophet 的销售预测

    每个 (store_code, matnr) 独立训练一个 Prophet 模型。
    Prophet 原生输出 yhat_lower / yhat_upper 作为置信区间，
    无需额外的 RMSE 近似。
    """

    MODEL_TYPE = "prophet"

    # Prophet 超参数
    SEASONALITY_MODE = "multiplicative"  # 零售数据季节性幅度随时间增长
    WEEKLY_SEASONALITY = True
    DAILY_SEASONALITY = False
    YEARLY_SEASONALITY = False   # 关闭内置年季节性，用自定义的（fourier_order=3 更简洁）
    UNCERTAINTY_SAMPLES = 1000  # 置信区间采样数（越大越稳定）
    CHANGEPOINT_PRIOR_SCALE = 0.05  # 趋势变化敏感度
    SEASONALITY_PRIOR_SCALE = 10.0  # 季节性强度

    def __init__(self, forecast_days: int = 30):
        self.forecast_days = forecast_days

    # ── train ──────────────────────────────────────────────
    def train(
        self,
        df: pd.DataFrame,
        model_record: Any,
        service: Any,
        **kwargs,
    ) -> Tuple[Dict, Dict[str, Any]]:
        """为每个 (store_code, matnr) 训练独立的 Prophet 模型

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

        groups = df.groupby(["store_code", "matnr"])
        total = len(groups)
        logger.info(f"[Prophet] 训练开始: {total} 个 (门店,商品) 分组")

        models: Dict[Tuple[str, str], Prophet] = {}
        all_mae = []
        all_rmse = []

        for idx, ((store, matnr), grp) in enumerate(groups):
            grp = grp.sort_values("dt").dropna(subset=[TARGET_COL])
            if len(grp) < 14:  # Prophet 最少需要 2 周数据
                logger.debug(f"[Prophet] 跳过 {store}/{matnr}: 仅 {len(grp)} 行")
                continue

            # 准备 Prophet 输入
            prophet_df = grp[["dt", TARGET_COL]].rename(columns={
                "dt": "ds",
                TARGET_COL: "y",
            })

            # 训练 Prophet
            m = Prophet(
                seasonality_mode=self.SEASONALITY_MODE,
                weekly_seasonality=self.WEEKLY_SEASONALITY,
                daily_seasonality=self.DAILY_SEASONALITY,
                yearly_seasonality=self.YEARLY_SEASONALITY,
                uncertainty_samples=self.UNCERTAINTY_SAMPLES,
                changepoint_prior_scale=self.CHANGEPOINT_PRIOR_SCALE,
                seasonality_prior_scale=self.SEASONALITY_PRIOR_SCALE,
            )
            # 添加月季节性和年度季节性
            m.add_seasonality(name="monthly", period=30.5, fourier_order=5)
            m.add_seasonality(name="yearly", period=365.25, fourier_order=3)

            m.fit(prophet_df)

            # 训练集评估
            forecast = m.predict(prophet_df)
            y_true = prophet_df["y"].values
            y_pred = forecast["yhat"].values
            mae = float(np.mean(np.abs(y_true - y_pred)))
            rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
            all_mae.append(mae)
            all_rmse.append(rmse)

            models[(store, matnr)] = m

            if (idx + 1) % 50 == 0 or idx == 0:
                logger.info(f"[Prophet] 训练进度 {idx+1}/{total}")

        if not models:
            raise ValueError("Prophet 训练失败：无有效分组（每组需要至少 14 天数据）")

        avg_mae = float(np.mean(all_mae)) if all_mae else 0.0
        avg_rmse = float(np.mean(all_rmse)) if all_rmse else 0.0
        metrics = {
            "mae": round(avg_mae, 2),
            "rmse": round(avg_rmse, 2),
            "model_count": len(models),
        }
        logger.info(f"[Prophet] 训练完成: {len(models)} 个模型, "
                     f"MAE={avg_mae:.2f}, RMSE={avg_rmse:.2f}")

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

            # Prophet 生成未来日期
            future = m.make_future_dataframe(
                periods=forecast_days,
                include_history=False,
            )
            forecast = m.predict(future)

            for i, (_, row) in enumerate(forecast.iterrows()):
                pred = max(float(row["yhat"]), 0)
                lower = max(float(row["yhat_lower"]), 0)
                upper = max(float(row["yhat_upper"]), 0)

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
        """序列化 Prophet 模型字典

        Prophet 模型使用内置 serialization（JSON），
        但为了统一管理，整体用 joblib 保存。
        """
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)
        logger.info(f"[Prophet] 模型已保存: {model_path}")

    def load(self, model_path: str) -> Dict[Tuple[str, str], Prophet]:
        model = joblib.load(model_path)
        logger.info(f"[Prophet] 模型已加载: {model_path} ({len(model)} 个分组)")
        return model
