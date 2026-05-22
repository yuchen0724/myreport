"""SARIMA 预测算法 — 每 (store, matnr) 独立拟合自回归模型

使用 statsmodels SARIMAX，参数量身定做：
  order=(1,1,1)           — 一阶自回归 + 一阶差分 + 一阶滑动平均
  seasonal_order=(1,1,1,7) — 周季节差分 + 季节AR/MA

注意：statsmodels 是可选依赖，导入失败时跳过注册。
"""

from __future__ import annotations
import os
import logging
import joblib
from typing import Any, Dict, List, Optional, Tuple
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from app.algorithms.base import BasePredictor, MIN_PREDICTION
from app.models.prediction import PredictionResult

logger = logging.getLogger(__name__)

TARGET_COL = "actual_sale_untaxed_amt"
_TRAIN_WORKERS = 4

# SARIMA 默认超参数
SARIMA_ORDER = (1, 1, 1)
SARIMA_SEASONAL_ORDER = (1, 1, 1, 7)


class SARIMAPredictor(BasePredictor):
    """SARIMA 各分组独立预测

    每个 (store_code, matnr) 用 SARIMAX 拟合。
    对短序列降级为普通 ARIMA 或 Naive 均值。
    """

    MODEL_TYPE = "sarima"

    @staticmethod
    def _fit_single(
        store: str,
        matnr: str,
        grp: pd.DataFrame,
    ) -> Optional[Tuple[Tuple[str, str], Any, float, float]]:
        """为单个 (store, matnr) 拟合 SARIMA（静态方法，供并行调用）"""
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        grp = grp.sort_values("dt").dropna(subset=[TARGET_COL])
        if len(grp) < 14:
            return None

        y = grp[TARGET_COL].values

        try:
            # 尝试 SARIMA（带季节项至少需 2×seasonal_period=14 天）
            if len(grp) >= 21:
                model = SARIMAX(
                    y,
                    order=SARIMA_ORDER,
                    seasonal_order=SARIMA_SEASONAL_ORDER,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                    simple_differencing=False,
                )
                fitted = model.fit(disp=False, maxiter=200, low_memory=True)
            else:
                # 短序列降级为普通 ARIMA
                model = SARIMAX(
                    y,
                    order=(1, 0, 0),
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                fitted = model.fit(disp=False, maxiter=100)

            # 训练集评估（样本内预测）
            y_pred = fitted.predict(start=0, end=len(y) - 1, dynamic=False)
            mae = float(np.mean(np.abs(y - y_pred)))
            rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))

            return ((store, matnr), fitted, mae, rmse)

        except Exception as e:
            logger.debug(f"[SARIMA] {store}/{matnr} 拟合失败: {e}")
            return None

    def train(
        self,
        df: pd.DataFrame,
        model_record: Any,
        service: Any,
        **kwargs,
    ) -> Tuple[Dict, Dict[str, Any]]:
        """逐组训练 SARIMA

        Returns:
            (models_dict, metrics)
            models_dict = {(store, matnr): SARIMAXResultsWrapper}
        """
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX
        except ImportError:
            raise ImportError("statsmodels 未安装，SARIMA 不可用。pip install statsmodels")

        df = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["dt"]):
            df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d", errors="coerce")

        groups = list(df.groupby(["store_code", "matnr"]))
        total = len(groups)
        logger.info(f"[SARIMA] 训练开始: {total} 个分组")

        models: Dict[Tuple[str, str], Any] = {}
        all_mae, all_rmse = [], []
        completed = 0

        with ThreadPoolExecutor(max_workers=_TRAIN_WORKERS) as executor:
            future_map = {}
            for (store, matnr), grp in groups:
                fut = executor.submit(self._fit_single, store, matnr, grp)
                future_map[fut] = (store, matnr)

            for fut in as_completed(future_map):
                try:
                    result = fut.result()
                except Exception as e:
                    logger.warning(f"[SARIMA] 训练异常: {e}")
                    continue
                if result is None:
                    continue
                key, fitted, mae, rmse = result
                models[key] = fitted
                all_mae.append(mae)
                all_rmse.append(rmse)
                completed += 1
                if completed % 50 == 0 or completed == 1:
                    logger.info(f"[SARIMA] 进度 {completed}/{total}")

        if not models:
            raise ValueError("SARIMA 训练失败：无有效分组")

        avg_mae = float(np.mean(all_mae)) if all_mae else 0.0
        avg_rmse = float(np.mean(all_rmse)) if all_rmse else 0.0
        metrics = {
            "mae": round(avg_mae, 2),
            "rmse": round(avg_rmse, 2),
            "model_count": len(models),
        }
        logger.info(f"[SARIMA] 完成: {len(models)} 个, MAE={avg_mae:.2f}, RMSE={avg_rmse:.2f}")
        return models, metrics

    def predict(
        self,
        model: Dict[Tuple[str, str], Any],
        model_record: Any,
        df: pd.DataFrame,
        forecast_days: int,
        service: Any,
        **kwargs,
    ) -> List[PredictionResult]:
        """用已训练的 SARIMA 模型预测未来 N 天"""
        if not pd.api.types.is_datetime64_any_dtype(df["dt"]):
            df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d", errors="coerce")

        groups = list(model.keys())
        logger.info(f"[SARIMA] 预测开始: {len(groups)} 个分组, {forecast_days} 天")

        # 从模型 metrics 获取 RMSE 用于置信区间降级
        model_metrics = getattr(model_record, "model_metrics", None) or {}
        fallback_rmse = model_metrics.get("rmse")
        if fallback_rmse is not None:
            fallback_rmse = float(fallback_rmse)

        results: List[PredictionResult] = []
        for idx, (store_code, matnr) in enumerate(groups):
            fitted = model[(store_code, matnr)]

            sku_df = df[(df["store_code"] == store_code) & (df["matnr"] == matnr)]
            if sku_df.empty:
                continue
            last_date = sku_df["dt"].max()

            try:
                # SARIMA 预测 + 置信区间
                # 注意：statsmodels 各版本返回类型不同
                # v0.14.x: numpy.ndarray; v0.12.x: pandas Series/DataFrame
                forecast_result = fitted.get_forecast(steps=forecast_days)
                pred_mean = forecast_result.predicted_mean
                conf_int = forecast_result.conf_int(alpha=0.10)  # 90% CI

                # 统一为 numpy 数组（兼容 pandas 版本）
                if hasattr(pred_mean, "iloc"):
                    pred_mean = pred_mean.values
                if hasattr(conf_int, "iloc"):
                    conf_int = conf_int.values

                for i in range(forecast_days):
                    pv = max(float(pred_mean[i]), MIN_PREDICTION)
                    forecast_date = last_date + timedelta(days=i + 1)

                    # 置信区间：如果 SARIMA 计算结果有效则用，否则降级为 RMSE 基线
                    ci_lower = float(conf_int[i, 0]) if i < conf_int.shape[0] else np.nan
                    ci_upper = float(conf_int[i, 1]) if i < conf_int.shape[0] else np.nan

                    if not np.isnan(ci_lower) and not np.isnan(ci_upper) and ci_lower < ci_upper:
                        lower = round(max(ci_lower, 0), 2)
                        upper = round(max(ci_upper, 0), 2)
                    elif fallback_rmse is not None and fallback_rmse > 0:
                        margin = 1.645 * fallback_rmse
                        lower = round(max(pv - margin, 0), 2)
                        upper = round(pv + margin, 2)
                    else:
                        lower = upper = None

                    results.append(PredictionResult(
                        model_id=model_record.id,
                        data_source_id=model_record.data_source_id,
                        store_code=store_code,
                        matnr=matnr,
                        forecast_date=forecast_date.date(),
                        predicted_value=round(pv, 2),
                        lower_bound=lower,
                        upper_bound=upper,
                    ))
            except Exception as e:
                logger.debug(f"[SARIMA] {store_code}/{matnr} 预测失败: {e}")
                continue

            if (idx + 1) % 100 == 0:
                logger.info(f"[SARIMA] 预测进度 {idx+1}/{len(groups)}")

        if results:
            unique_pairs = list({(r.store_code, r.matnr) for r in results})
            ware_name_map = service._lookup_ware_names(
                model_record.data_source_id, unique_pairs
            )
            for r in results:
                r.ware_name = ware_name_map.get((r.store_code, r.matnr), "")

        logger.info(f"[SARIMA] 预测完成: {len(results)} 条结果")
        return results

    def save(self, model: Dict[Tuple[str, str], Any], model_path: str) -> None:
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)
        logger.info(f"[SARIMA] 已保存: {model_path}")

    def load(self, model_path: str) -> Dict[Tuple[str, str], Any]:
        m = joblib.load(model_path)
        logger.info(f"[SARIMA] 已加载: {model_path} ({len(m)} 个分组)")
        return m
