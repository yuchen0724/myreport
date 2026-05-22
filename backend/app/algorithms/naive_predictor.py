"""Naive 季节性基线 — 上周同日作为预测值

零训练开销，用于衡量其他算法是否真的有提升。
预测值 = 同一天上一周的销售额。
置信区间 = 历史同日周值 ± 1.645 × std。
"""

from __future__ import annotations
import os
import logging
import joblib
from typing import Any, Dict, List, Optional, Tuple
from datetime import timedelta

import numpy as np
import pandas as pd

from app.algorithms.base import BasePredictor, MIN_PREDICTION
from app.models.prediction import PredictionResult

logger = logging.getLogger(__name__)

TARGET_COL = "actual_sale_untaxed_amt"
LOOKBACK_WEEKS = 8  # 保留 8 周历史供计算 std


class NaivePredictor(BasePredictor):
    """Naive 季节性基线

    用历史中相同 weekday 的值作为未来预测。
    例如：预测下周三 → 取最近 8 个周三的均值。
    """

    MODEL_TYPE = "naive"

    def train(
        self,
        df: pd.DataFrame,
        model_record: Any,
        service: Any,
        **kwargs,
    ) -> Tuple[Dict, Dict[str, Any]]:
        """"训练" — 实际只是按 (store, matnr) 整理历史数据，不需模型拟合

        Returns:
            (data_dict, metrics)
            data_dict = {(store_code, matnr): DataFrame(历史数据)}
            metrics = {"model_count": N}
        """
        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["dt"]):
            df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d", errors="coerce")
        df["dow"] = df["dt"].dt.dayofweek  # 0=Mon, 6=Sun

        groups = df.groupby(["store_code", "matnr"])
        total = len(groups)
        logger.info(f"[Naive] 整理 {total} 个分组")

        data: Dict[Tuple[str, str], pd.DataFrame] = {}
        for (store, matnr), grp in groups:
            grp = grp.sort_values("dt").dropna(subset=[TARGET_COL])
            if len(grp) < 7:
                continue
            data[(store, matnr)] = grp.tail(LOOKBACK_WEEKS * 7)[
                ["dt", TARGET_COL, "dow"]
            ].copy()

        if not data:
            raise ValueError("Naive 训练失败：无有效分组（每组需要至少 7 天数据）")

        metrics = {"model_count": len(data)}
        logger.info(f"[Naive] 整理完成: {len(data)} 个分组")
        return data, metrics

    def predict(
        self,
        model: Dict[Tuple[str, str], pd.DataFrame],
        model_record: Any,
        df: pd.DataFrame,
        forecast_days: int,
        service: Any,
        **kwargs,
    ) -> List[PredictionResult]:
        """对每个分组用上周同日值预测

        Args:
            model: train() 返回的 {(store,matnr): DataFrame}

        Returns:
            List[PredictionResult]
        """
        if not pd.api.types.is_datetime64_any_dtype(df["dt"]):
            df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d", errors="coerce")
        df["dow"] = df["dt"].dt.dayofweek

        groups = list(model.keys())
        logger.info(f"[Naive] 预测开始: {len(groups)} 个分组, forecast_days={forecast_days}")

        results: List[PredictionResult] = []
        for idx, (store_code, matnr) in enumerate(groups):
            history = model[(store_code, matnr)]

            # 该分组最后日期
            last_date = history["dt"].max()
            if not last_date:
                continue

            for i in range(forecast_days):
                forecast_date = last_date + timedelta(days=i + 1)
                target_dow = forecast_date.weekday()  # 0=Mon

                # 取历史中所有相同 weekday 的值
                same_dow = history[history["dow"] == target_dow][TARGET_COL]
                if same_dow.empty:
                    continue

                pred = max(float(same_dow.mean()), MIN_PREDICTION)
                std = float(same_dow.std()) if len(same_dow) >= 2 else 0.0
                margin = 1.645 * std
                lower = round(max(pred - margin, 0), 2)
                upper = round(pred + margin, 2)

                results.append(PredictionResult(
                    model_id=model_record.id,
                    data_source_id=model_record.data_source_id,
                    store_code=store_code,
                    matnr=matnr,
                    forecast_date=forecast_date.date(),
                    predicted_value=round(pred, 2),
                    lower_bound=lower,
                    upper_bound=upper,
                ))

            if (idx + 1) % 100 == 0:
                logger.info(f"[Naive] 预测进度 {idx+1}/{len(groups)}")

        # 补商品名称
        if results:
            unique_pairs = list({(r.store_code, r.matnr) for r in results})
            ware_name_map = service._lookup_ware_names(
                model_record.data_source_id, unique_pairs
            )
            for r in results:
                r.ware_name = ware_name_map.get((r.store_code, r.matnr), "")

        logger.info(f"[Naive] 预测完成: {len(results)} 条结果")
        return results

    def save(self, model: Dict[Tuple[str, str], pd.DataFrame], model_path: str) -> None:
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)
        logger.info(f"[Naive] 模型已保存: {model_path}")

    def load(self, model_path: str) -> Dict[Tuple[str, str], pd.DataFrame]:
        model = joblib.load(model_path)
        logger.info(f"[Naive] 模型已加载: {model_path} ({len(model)} 个分组)")
        return model
