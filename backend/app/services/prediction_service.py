"""销售预测服务 - LightGBM 训练与推理"""

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime
from typing import Optional
from sqlalchemy.orm import Session

import lightgbm as lgb
import joblib

from app.config import get_settings

settings = get_settings()
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.prediction_repository import (
    PredictionModelRepository,
    PredictionResultRepository,
)
from app.models.prediction import PredictionResult
from app.utils.feature_engineering import build_features_from_history, get_feature_columns

logger = logging.getLogger(__name__)

TARGET_COL = "actual_sale_untaxed_amt"  # 预测目标字段


class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.model_repo = PredictionModelRepository(db)
        self.result_repo = PredictionResultRepository(db)
        self.model_dir = settings.prediction_model_dir
        os.makedirs(self.model_dir, exist_ok=True)

    def _fetch_history_data(self, ds_id: int, days: int, table_name: str = None,
                           progress_callback: callable = None) -> pd.DataFrame:
        """从 Doris 按天分页拉取历史销售数据，避免单次查询内存/超时问题。
        
        每页拉取 1 天数据，在服务器端排序后插入结果列表。
        最终 pd.concat 合并为完整 DataFrame（特征工程内部会重新排序）。
        
        Args:
            progress_callback: 可选回调 fn(current_page, total_pages, current_rows)
                              用于更新进度到 Redis
        """
        ds = self.ds_repo.get_by_id(ds_id)
        if not ds:
            raise ValueError(f"数据源 {ds_id} 不存在")

        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        table = table_name or f"{ds.database}.ads_cockpit_fd_store_ware_d"
        from app.utils.db_executor import execute_query

        # 先获取总天数作为批次数量
        total_pages = (end_date - start_date).days
        batches = []
        current = start_date
        page_no = 0
        while current < end_date:
            s = current.strftime("%Y%m%d")
            sql = f"""\
                SELECT /*+ SET_VAR(exec_mem_limit=1073741824, query_timeout=600) */
                    dt, store_code, matnr, {TARGET_COL}
                FROM {table}
                WHERE dt = {s}
                  AND exclude_flag != 1
                  AND (service_flag != 1 OR service_flag IS NULL)
                  AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
                ORDER BY store_code, matnr, dt
            """
            rows, columns = execute_query(ds, sql)
            if rows:
                batch_df = pd.DataFrame(rows, columns=columns)
                batches.append(batch_df)

            page_no += 1
            # 日志记录每一页拉取情况
            import logging as _log
            _log.getLogger(__name__).info(f"[拉取] page={page_no}/{total_pages}, rows={len(rows) if rows else 0}")
            if progress_callback:
                progress_callback(page_no, total_pages, len(rows) if rows else 0)

            current += timedelta(days=1)

        if not batches:
            return pd.DataFrame(columns=["dt", "store_code", "matnr", TARGET_COL])

        df = pd.concat(batches, ignore_index=True)
        df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors="coerce").fillna(0)
        # 金额分转元
        df[TARGET_COL] = df[TARGET_COL] / 100.0
        return df

    def train(self, ds_id: int, train_days: int = None, table_name: str = None) -> int:
        """
        训练模型。
        
        返回: 模型记录 ID
        """
        train_days = train_days or settings.prediction_train_default_days
        logger.info(f"[预测] 开始训练，数据源={ds_id}，历史天数={train_days}")

        # 创建模型记录
        model_record = self.model_repo.create(
            data_source_id=ds_id,
            model_type="lightgbm",
            status="training",
        )

        try:
            # 1. 拉取历史数据
            df = self._fetch_history_data(ds_id, train_days, table_name=table_name)
            if len(df) < settings.prediction_min_history_days * 10:
                raise ValueError(
                    f"历史数据不足({len(df)}行)，需要至少 {settings.prediction_min_history_days * 10} 行"
                )

            # 2. 特征工程
            df_feat = build_features_from_history(df)
            df_feat = df_feat.dropna(subset=get_feature_columns()).reset_index(drop=True)

            # 3. 构造训练集
            feature_cols = get_feature_columns()
            X = df_feat[feature_cols].values
            y = df_feat[TARGET_COL].values

            # 4. 训练 LightGBM
            model = lgb.LGBMRegressor(
                n_estimators=500,
                learning_rate=0.05,
                max_depth=8,
                num_leaves=31,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1,
            )
            model.fit(X, y)

            # 5. 评估
            y_pred = model.predict(X)
            mae = float(np.mean(np.abs(y - y_pred)))
            rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))
            logger.info(f"[预测] 训练完成: MAE={mae:.2f}, RMSE={rmse:.2f}")

            # 6. 保存模型
            model_path = os.path.join(self.model_dir, f"lgb_{ds_id}_{model_record.id}.pkl")
            joblib.dump(model, model_path)

            # 7. 更新模型记录
            self.model_repo.update_status(
                model_record.id, "ready",
                model_path=model_path,
                feature_count=len(feature_cols),
                train_start_date=df["dt"].min().date(),
                train_end_date=df["dt"].max().date(),
                train_row_count=len(df_feat),
                model_metrics={"mae": mae, "rmse": rmse},
                trained_at=datetime.utcnow(),
            )

            return model_record.id

        except Exception as e:
            logger.error(f"[预测] 训练失败: {e}")
            self.model_repo.update_status(
                model_record.id, "failed",
                error_message=str(e),
            )
            raise

    def predict(self, ds_id: int, forecast_days: int = None, table_name: str = None) -> int:
        """
        用最新模型预测未来 N 天销售额。
        
        返回: 写入的预测结果条数
        """
        forecast_days = forecast_days or settings.prediction_forecast_days
        model_record = self.model_repo.get_latest_ready(ds_id)
        if not model_record:
            raise ValueError(f"数据源 {ds_id} 没有已训练好的模型")

        model = joblib.load(model_record.model_path)
        feature_cols = get_feature_columns()

        # 拉取最新数据构造特征
        df = self._fetch_history_data(ds_id, days=60, table_name=table_name)
        df_feat = build_features_from_history(df)
        df_feat = df_feat.dropna(subset=feature_cols)

        # 取每个门店-商品的最新一条
        latest = (
            df_feat.sort_values("dt")
            .groupby(["store_code", "matnr"])
            .last()
            .reset_index()
        )

        results = []
        current_features = latest[feature_cols].values

        for i in range(forecast_days):
            preds = model.predict(current_features)
            forecast_date = date.today() + timedelta(days=i + 1)

            for idx, row in latest.iterrows():
                results.append(PredictionResult(
                    model_id=model_record.id,
                    data_source_id=ds_id,
                    store_code=row["store_code"],
                    matnr=row["matnr"],
                    forecast_date=forecast_date,
                    predicted_value=round(float(preds[idx]), 2),
                ))

            # 简易滚动：用预测值更新 lag_1 特征（迭代推理）
            if i < forecast_days - 1:
                current_features[:, feature_cols.index("lag_1")] = preds

        count = self.result_repo.bulk_save(results)
        logger.info(f"[预测] 写入 {count} 条预测结果")
        return count
