"""LightGBM 预测算法 — 封装现有逻辑到 BasePredictor 接口"""

from __future__ import annotations
import os
import logging
import joblib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import lightgbm as lgb

from app.algorithms.base import BasePredictor, MIN_PREDICTION
from app.models.prediction import PredictionResult
from app.utils.feature_engineering import build_features_from_history, get_feature_columns

logger = logging.getLogger(__name__)

TARGET_COL = "actual_sale_untaxed_amt"


class LightGBMPredictor(BasePredictor):
    """LightGBM 预测算法

    封装 PredictionService 中现有的 LightGBM 逻辑到统一接口，
    使 train() / predict() 可以按 model_type 分发。
    """

    MODEL_TYPE = "lightgbm"

    def train(
        self,
        df: pd.DataFrame,
        model_record: Any,
        service: Any,
        **kwargs,
    ) -> Tuple[Any, Dict[str, Any]]:
        """训练 LightGBM 模型

        Args:
            df: 历史销售数据
            model_record: PredictionModel ORM
            service: PredictionService 实例

        Returns:
            (model, metrics) — model 为 LGBMRegressor
        """
        feature_cols = get_feature_columns()

        df_feat = build_features_from_history(df)
        df_feat = df_feat.dropna(subset=feature_cols).reset_index(drop=True)

        X = df_feat[feature_cols].values
        y = df_feat[TARGET_COL].values

        model = lgb.LGBMRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=8,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
            num_threads=2,
        )
        model.fit(X, y)

        y_pred = model.predict(X)
        mae = float(np.mean(np.abs(y - y_pred)))
        rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))

        metrics = {"mae": round(mae, 2), "rmse": round(rmse, 2)}
        logger.info(f"[LightGBM] 训练完成: MAE={mae:.2f}, RMSE={rmse:.2f}")
        return model, metrics

    def predict(
        self,
        model: lgb.LGBMRegressor,
        model_record: Any,
        df: pd.DataFrame,
        forecast_days: int,
        service: Any,
        **kwargs,
    ) -> List[PredictionResult]:
        """用 LightGBM 模型做滚动预测（含置信区间）"""
        from datetime import timedelta

        feature_cols = get_feature_columns()
        df_feat = build_features_from_history(df)
        df_feat = df_feat.dropna(subset=feature_cols)

        # 从模型指标获取 RMSE 用于置信区间
        model_metrics = model_record.model_metrics or {}
        rmse = model_metrics.get("rmse")
        if rmse is not None:
            try:
                rmse = float(rmse)
            except (TypeError, ValueError):
                rmse = None

        # 降级：动态计算 RMSE
        if rmse is None or rmse <= 0:
            rmse = self._compute_rmse(model, df_feat, feature_cols, forecast_days)

        results: List[PredictionResult] = []
        stores = sorted(df_feat["store_code"].unique())
        total_stores = len(stores)
        lookback_window = 60
        progress_callback = kwargs.get("progress_callback")

        for store_idx, store_code in enumerate(stores):
            store_df = df_feat[df_feat["store_code"] == store_code]
            if store_df.empty:
                continue

            latest = (
                store_df.sort_values("dt")
                .groupby(["store_code", "matnr"])
                .last()
                .reset_index()
            )

            for _, sku_row in latest.iterrows():
                matnr_val = sku_row["matnr"]
                sku_history = store_df[
                    (store_df["store_code"] == store_code) &
                    (store_df["matnr"] == matnr_val)
                ].sort_values("dt")

                base_cols = ["dt", "store_code", "matnr", TARGET_COL]
                history_raw = sku_history[base_cols].tail(lookback_window).copy()

                if len(history_raw) < 7:
                    continue

                history_feat = build_features_from_history(history_raw.copy())
                history_feat = history_feat.dropna(subset=feature_cols)
                if history_feat.empty:
                    continue

                last_date = pd.to_datetime(
                    history_raw["dt"].iloc[-1], format="%Y%m%d", errors="coerce"
                )

                for i in range(forecast_days):
                    current_feat = build_features_from_history(history_raw.copy())
                    current_feat = current_feat.dropna(subset=feature_cols)
                    if current_feat.empty:
                        break

                    row_df = current_feat.iloc[-1:][feature_cols]
                    pred = max(float(model.predict(row_df)[0]), MIN_PREDICTION)

                    if rmse is not None and rmse > 0:
                        margin = 1.645 * rmse
                        lower = round(max(pred - margin, 0), 2)
                        upper = round(pred + margin, 2)
                    else:
                        lower = upper = None

                    forecast_date = last_date + timedelta(days=i + 1)
                    forecast_dt_str = forecast_date.strftime("%Y%m%d")

                    results.append(PredictionResult(
                        model_id=model_record.id,
                        data_source_id=model_record.data_source_id,
                        store_code=store_code,
                        matnr=matnr_val,
                        forecast_date=forecast_date.date(),
                        predicted_value=round(pred, 2),
                        lower_bound=lower,
                        upper_bound=upper,
                    ))

                    new_row = pd.DataFrame([{
                        "dt": forecast_dt_str,
                        "store_code": store_code,
                        "matnr": matnr_val,
                        TARGET_COL: pred,
                    }])
                    history_raw = pd.concat([history_raw, new_row], ignore_index=True)
                    if len(history_raw) > lookback_window:
                        history_raw = history_raw.iloc[-lookback_window:].reset_index(drop=True)

            if progress_callback:
                progress_callback(model_record.id, store_idx + 1, total_stores, store_code)

        # 补商品名称
        if results:
            unique_pairs = list({(r.store_code, r.matnr) for r in results})
            ware_name_map = service._lookup_ware_names(
                model_record.data_source_id, unique_pairs
            )
            for r in results:
                r.ware_name = ware_name_map.get((r.store_code, r.matnr), "")

        return results

    def save(self, model: lgb.LGBMRegressor, model_path: str) -> None:
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)
        # 同时保存 Booster 格式
        try:
            model.booster_.save_model(model_path.replace(".pkl", ".txt"))
        except Exception:
            pass

    def load(self, model_path: str) -> lgb.LGBMRegressor:
        return joblib.load(model_path)

    # ── 内部辅助 ───────────────────────────────────────────
    def _compute_rmse(
        self,
        model: lgb.LGBMRegressor,
        df_feat: pd.DataFrame,
        feature_cols: List[str],
        forecast_days: int,
    ) -> Optional[float]:
        """从近期历史数据动态计算 RMSE（兼容旧模型）"""
        try:
            val_days = min(forecast_days * 2, 14)
            last_ref = df_feat["dt"].max()
            val_start = last_ref - pd.Timedelta(days=val_days)
            val_data = df_feat[df_feat["dt"] >= val_start]
            if len(val_data) >= 10:
                y_true = val_data[TARGET_COL].values
                y_pred = model.predict(val_data[feature_cols])
                _rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
                if _rmse > 0:
                    logger.info(f"[LightGBM] 动态 RMSE={_rmse:.2f} ({len(val_data)} 条)")
                    return _rmse
        except Exception as e:
            logger.warning(f"[LightGBM] 动态 RMSE 计算失败: {e}")
        return None
