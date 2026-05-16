"""销售预测服务 - LightGBM 训练与推理"""

import os
import warnings
import logging
import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime, timezone
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
from app.utils.db_executor import execute_query

logger = logging.getLogger(__name__)

TARGET_COL = "actual_sale_untaxed_amt"  # 预测目标字段
TZ_UTC8 = timezone(timedelta(hours=8))


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
            logger.info(f"[拉取] page={page_no}/{total_pages}, rows={len(rows) if rows else 0}")
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

    def _fetch_and_train_incremental(self, ds_id: int, days: int, model, feature_cols,
                                      table_name: str = None,
                                      fetch_callback: callable = None,
                                      train_callback: callable = None,
                                      predict_callback: callable = None) -> tuple:
        """按 (group_id, store_code, matnr) 分组分批拉取增量训练

        先查询所有分组的行数，然后将多个完整分组合并为一个批次（≈BATCH_SIZE 行），
        保证同一个 (group_id, store_code, matnr) 的完整时序不被切分到不同批次。

        每个批次拉取数据 → 训练 → 立即回调 predict_callback（不缓存全量数据到内存）。

        Args:
            fetch_callback: 每批数据拉取完成后回调(batch_no, total_batches, rows_count)
            train_callback: 每批训练完成后回调(batch_no, total_batches, rows_count)
            predict_callback: 每批训练完成后回调(chunk_df, batch_no, total_batches) 用于即时预测

        Returns:
            tuple: (model, feature_cols, total_trained_rows, train_start, train_end,
                    mae_val, rmse_val, "", batch_no)
        """
        ds = self.ds_repo.get_by_id(ds_id)
        if not ds:
            raise ValueError(f"数据源 {ds_id} 不存在")

        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        table = table_name or f"{ds.database}.ads_cockpit_fd_store_ware_d"

        # 0. 快速获取最近活跃分组列表：取前一天峰值排前 N 的分组
        #    25.7亿行数据，GROUP BY 全表不可行，改为最近一天优先取高频分组
        latest_day = date.today() - timedelta(days=1)
        group_count_sql = f"""\
            SELECT /*+ SET_VAR(query_timeout=120) */
                group_id, store_code, matnr, COUNT(*) as cnt
            FROM {table}
            WHERE dt >= '{latest_day.strftime('%Y%m%d')}'
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            GROUP BY group_id, store_code, matnr
            ORDER BY cnt DESC
            LIMIT 500
        """
        logger.info(f"[训练] 取前一天 TOP 500 活跃分组...")
        group_rows, _ = execute_query(ds, group_count_sql)
        if not group_rows:
            raise ValueError("无有效训练数据")

        all_groups = []  # [(group_id, store_code, matnr)]
        for row in group_rows:
            all_groups.append((row[0], row[1], row[2]))

        logger.info(f"[训练] 活跃分组数={len(all_groups)}")

        # 每 N 个分组合并为一个批次，减少 DB 写入次数和模型 fit 调用
        BATCH_GROUP_SIZE = 5
        batches = [all_groups[i:i+BATCH_GROUP_SIZE] for i in range(0, len(all_groups), BATCH_GROUP_SIZE)]
        total_batches = len(batches)

        batch_no = 0
        total_trained_rows = 0
        first_fit = True
        train_start = start_date
        train_end = end_date

        for batch_groups in batches:
            batch_no += 1

            # 构造当前批次 SQL：用 IN 匹配所有分组
            # 分批用 OR 条件 (group_id=a AND store_code='b' AND matnr='c') OR ...
            group_conditions = []
            for gid, scode, mnr in batch_groups:
                group_conditions.append(
                    f"(group_id={gid} AND store_code='{scode}' AND matnr='{mnr}')"
                )
            where_groups = " OR ".join(group_conditions)

            sql = f"""\
                SELECT /*+ SET_VAR(exec_mem_limit=1073741824, query_timeout=600) */
                    dt, group_id, store_code, matnr, {TARGET_COL}
                FROM {table}
                WHERE dt >= '{start_date.strftime('%Y%m%d')}' AND dt < '{end_date.strftime('%Y%m%d')}'
                  AND exclude_flag != 1
                  AND (service_flag != 1 OR service_flag IS NULL)
                  AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
                  AND ({where_groups})
                ORDER BY store_code, matnr, dt
            """
            logger.info(f"[训练] 分批批次 batch={batch_no}/{total_batches}, 该批分组数={len(batch_groups)}, SQL: {sql.replace(chr(10), ' ').strip()}")
            rows, cols = execute_query(ds, sql)
            if not rows:
                logger.info(f"[训练] 批次 {batch_no} 无数据，跳过")
                continue

            chunk_df = pd.DataFrame(rows, columns=cols)
            chunk_df[TARGET_COL] = pd.to_numeric(chunk_df[TARGET_COL], errors="coerce").fillna(0)
            chunk_df[TARGET_COL] = chunk_df[TARGET_COL] / 100.0

            if fetch_callback:
                fetch_callback(batch_no, total_batches, len(rows))

            # 特征工程
            feat = build_features_from_history(chunk_df)
            feat = feat.dropna(subset=feature_cols)

            if len(feat) == 0:
                continue

            # 增量训练
            X = feat[feature_cols].values
            y = feat[TARGET_COL].values

            if first_fit:
                model.fit(X, y)
                first_fit = False
            else:
                model.fit(X, y, init_model=model)

            total_trained_rows += len(feat)

            if train_callback:
                train_callback(batch_no, total_batches, len(feat))

            # 每批训练完成后立即回调预测（不缓存全量数据）
            if predict_callback:
                predict_callback(chunk_df, batch_no, total_batches)

        if total_trained_rows == 0:
            raise ValueError("训练数据不足（无有效特征行）")

        # 评估：用最后一批数据
        mae_val, rmse_val = 0.0, 0.0
        last_chunk = locals().get("chunk_df")
        if last_chunk is not None and len(last_chunk) > 0:
            try:
                eval_feat = build_features_from_history(last_chunk.tail(7).copy())
                eval_feat = eval_feat.dropna(subset=feature_cols)
                if len(eval_feat) > 0:
                    y_pred = model.predict(eval_feat[feature_cols])
                    y_true = eval_feat[TARGET_COL].values
                    mae_val = float(np.mean(np.abs(y_true - y_pred)))
                    rmse_val = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
            except Exception:
                pass

        return (model, feature_cols, total_trained_rows, train_start, train_end, mae_val, rmse_val, "", batch_no)

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
                trained_at=datetime.now(TZ_UTC8),
            )

            return model_record.id

        except Exception as e:
            logger.error(f"[预测] 训练失败: {e}")
            self.model_repo.update_status(
                model_record.id, "failed",
                error_message=str(e),
            )
            raise

    def _predict_from_cache(
        self,
        data_df: pd.DataFrame,
        model,
        model_record: 'PredictionModel',
        forecast_days: int,
        progress_callback: callable = None,
    ) -> list:
        """
        利用缓存的历史数据 DataFrame 直接进行滚动预测。
        
        Args:
            data_df: 缓存的历史数据（列: group_id, store_code, matnr, dt, TARGET_COL）
            model: 已训练好的 LightGBM 模型
            model_record: 模型记录（用于关联预测结果）
            forecast_days: 预测天数
            progress_callback: 可选进度回调 fn(model_id, store_idx, total_stores, store_code)
        
        Returns:
            List[PredictionResult]
        """
        
        feature_cols = get_feature_columns()
        
        data_df = data_df.copy()
        data_df[TARGET_COL] = pd.to_numeric(data_df[TARGET_COL], errors="coerce").fillna(0)
        
        # 特征工程
        df_feat = build_features_from_history(data_df)
        df_feat = df_feat.dropna(subset=feature_cols).reset_index(drop=True)
        
        if df_feat.empty:
            raise ValueError("缓存数据经特征工程后无有效数据，无法预测")
        
        # 按 (store_code, matnr) 分组，取每组最后一条
        latest = (
            df_feat.sort_values("dt")
            .groupby(["store_code", "matnr"])
            .last()
            .reset_index()
        )
        
        # 获取所有门店列表（用于进度回调）
        stores = sorted(latest["store_code"].unique())
        total_stores = len(stores)
        
        results = []
        for store_idx, store_code in enumerate(stores):
            store_df = df_feat[df_feat["store_code"] == store_code]
            if store_df.empty:
                continue
            
            # 取每个 SKU 的最新一条
            sku_latest = (
                store_df.sort_values("dt")
                .groupby(["store_code", "matnr"])
                .last()
                .reset_index()
            )
            
            # 用 DataFrame 切片（保留列名），避免 sklearn feature names warning
            current_features = sku_latest[feature_cols]
            
            for i in range(forecast_days):
                preds = model.predict(current_features)
                forecast_date = date.today() + timedelta(days=i + 1)
                
                for idx, row in sku_latest.iterrows():
                    results.append(PredictionResult(
                        model_id=model_record.id,
                        data_source_id=model_record.data_source_id,
                        store_code=row["store_code"],
                        matnr=row["matnr"],
                        forecast_date=forecast_date,
                        predicted_value=round(float(preds[idx]), 2),
                    ))
                
                # 简易滚动：用预测值更新 lag_1 特征
                if i < forecast_days - 1:
                    current_features = current_features.copy()
                    current_features["lag_1"] = preds
            
            if progress_callback:
                progress_callback(model_record.id, store_idx + 1, total_stores, store_code)
        
        return results

    def predict(self, ds_id: int, forecast_days: int = None, table_name: str = None,
                model_id: int = None, progress_callback: callable = None) -> tuple:
        """
        用指定模型预测未来 N 天销售额。
        
        如果 model_id 不传，使用该数据源最新 ready 的模型。

        progress_callback(model_id, store_idx, total_stores, store_code) 用于更新进度
        
        返回: (写入的预测结果条数, 实际使用的模型ID)
        """
        forecast_days = forecast_days or settings.prediction_forecast_days

        if model_id:
            model_record = self.model_repo.get_by_id(model_id)
            if not model_record or model_record.status != "ready":
                raise ValueError(f"模型 {model_id} 不存在或状态不是 ready")
        else:
            model_record = self.model_repo.get_latest_ready(ds_id)
            if not model_record:
                raise ValueError(f"数据源 {ds_id} 没有已训练好的模型")

        model = joblib.load(model_record.model_path)
        feature_cols = get_feature_columns()

        # 拉取最新数据构造特征
        df = self._fetch_history_data(ds_id, days=60, table_name=table_name)
        df_feat = build_features_from_history(df)
        df_feat = df_feat.dropna(subset=feature_cols)

        # 获取所有门店列表
        stores = sorted(df_feat["store_code"].unique())
        total_stores = len(stores)

        results = []
        for store_idx, store_code in enumerate(stores):
            store_df = df_feat[df_feat["store_code"] == store_code]
            if store_df.empty:
                continue

            # 取每个 SKU 的最新一条
            latest = (
                store_df.sort_values("dt")
                .groupby(["store_code", "matnr"])
                .last()
                .reset_index()
            )

            current_features = latest[feature_cols]

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

                # 简易滚动：用预测值更新 lag_1 特征
                if i < forecast_days - 1:
                    current_features = current_features.copy()
                    current_features["lag_1"] = preds

            if progress_callback:
                progress_callback(model_record.id, store_idx + 1, total_stores, store_code)

        count = self.result_repo.bulk_save(results)
        logger.info(f"[预测] 写入 {count} 条预测结果，模型 model_id={model_record.id}")
        return count, model_record.id
