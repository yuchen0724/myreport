"""销售预测服务 - LightGBM 训练与推理"""

import os
import re
import signal
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

# 算法注册（惰性导入，避免 prophet/lightgbm 未安装时崩溃）
from app.algorithms.base import BasePredictor

logger = logging.getLogger(__name__)

TARGET_COL = "actual_sale_untaxed_amt"  # 预测目标字段
TZ_UTC8 = timezone(timedelta(hours=8))

# Doris 分批查询中实际需要的列（避免 SELECT * 读全部列放大 I/O）
_REQUIRED_COLS = [
    "dt", "group_id", "store_code", "matnr",
    TARGET_COL,
    "exclude_flag", "service_flag", "shopping_bag_flag",
]
_REQUIRED_COLS_SQL = ", ".join(_REQUIRED_COLS)


class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.model_repo = PredictionModelRepository(db)
        self.result_repo = PredictionResultRepository(db)
        self.model_dir = settings.prediction_model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        # 算法注册表：model_type → BasePredictor 实例（惰性初始化）
        self._algorithms: dict[str, BasePredictor] | None = None

    def _get_algorithms(self) -> dict[str, BasePredictor]:
        """懒加载算法注册表，避免未安装的算法模块导致导入失败"""
        if self._algorithms is not None:
            return self._algorithms
        self._algorithms = {}
        # LightGBM（强依赖，始终可用）
        from app.algorithms.lightgbm_predictor import LightGBMPredictor
        self._algorithms["lightgbm"] = LightGBMPredictor()
        # Prophet（可选依赖）
        try:
            from app.algorithms.prophet_predictor import ProphetPredictor
            self._algorithms["prophet"] = ProphetPredictor()
        except ImportError:
            logger.warning("[算法] Prophet 未安装，仅 lightgbm 可用")
        return self._algorithms

    def _get_algorithm(self, model_type: str = "lightgbm") -> BasePredictor:
        """按 model_type 查找算法实例"""
        algos = self._get_algorithms()
        algo = algos.get(model_type)
        if not algo:
            raise ValueError(
                f"不支持的模型类型: '{model_type}'，"
                f"支持: {list(algos.keys())}"
            )
        return algo

    def _lookup_ware_names(self, ds_id: int, pairs: list) -> dict:
        """从 Doris 维度表批量查 ware_name，返回 (store_code, matnr) -> ware_name 字典

        Args:
            ds_id: 数据源 ID
            pairs: [(store_code, matnr), ...]
        Returns:
            {(store_code, matnr): ware_name, ...}
        """
        if not pairs:
            return {}
        try:
            ds = self.ds_repo.get_by_id(ds_id)
            if not ds:
                return {}
            # Doris 不支持 (col1, col2) IN (...) 元组语法，用 OR 拼接
            ors = " OR ".join(
                [f"(store_code = '{sc}' AND matnr = '{mn}')" for sc, mn in pairs]
            )
            sql = f"SELECT store_code, matnr, ware_name FROM ads_fd_dim_store_ware WHERE {ors}"
            rows, cols = execute_query(ds, sql)
            name_map = {}
            for row in rows:
                name_map[(row[0], row[1])] = row[2] if len(row) > 2 and row[2] else ""
            return name_map
        except Exception as e:
            logger.warning(f"[预测] 查询商品名称失败: {e}")
            return {}

    def _fetch_history_data(self, ds_id: int, days: int, table_name: str = None,
                           progress_callback: callable = None) -> pd.DataFrame:
        """从 Doris 按范围拉取历史销售数据，一次查询获取全部数据。
        
        优化点：将原来的按天分页查询改为单次范围查询，
        减少网络往返次数，充分利用 Doris 列存引擎的聚合能力。
        
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
        
        # 检测 table_name 是否为完整 SELECT 语句（大小写不敏感）
        is_subquery = table_name and table_name.strip().upper().startswith(("SELECT", "(SELECT"))
        if is_subquery:
            # 子查询需要加括号和别名才能在 FROM 中使用
            table = self._fix_select_star(table)
            table_ref = f"({table}) AS _sub"
        else:
            table_ref = table
        
        # 格式化日期范围
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        # 一次性查询整个日期范围（优化：减少 365 次查询为 1 次）
        sql = f"""\
            SELECT /*+ SET_VAR(exec_mem_limit=1073741824, query_timeout=600) */
                dt, store_code, matnr, {TARGET_COL}
            FROM {table_ref}
            WHERE dt >= {start_str}
              AND dt < {end_str}
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            ORDER BY store_code, matnr, dt
        """
        
        if progress_callback:
            progress_callback(0, 1, 0)  # 开始拉取
        
        logger.info(f"[拉取] 范围查询: {start_str} -> {end_str}, rows=...")
        rows, columns = execute_query(ds, sql)
        
        if progress_callback:
            progress_callback(1, 1, len(rows) if rows else 0)  # 拉取完成
        
        if not rows:
            return pd.DataFrame(columns=["dt", "store_code", "matnr", TARGET_COL])

        df = pd.DataFrame(rows, columns=columns)
        df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors="coerce").fillna(0)
        # 金额分转元
        df[TARGET_COL] = df[TARGET_COL] / 100.0
        return df

    def _fetch_and_train_incremental(
            self, ds_id: int, days: int, model, feature_cols,
            table_name: str = None,
            batch_size: int = 200,
            batch_unit: int = 10,
            test_days: int = 30,  # 测试集天数（参数化）
            valid_days: int = 30,  # 验证集天数（参数化）
            fetch_callback: callable = None,
            train_callback: callable = None,
            predict_callback: callable = None,
            start_batch: int = 0) -> tuple:
        """按 (group_id, store_code, matnr) 分组分批拉取增量训练

        先查询所有分组的行数，然后将多个完整分组合并为一个批次（≈BATCH_SIZE 行），
        保证同一个 (group_id, store_code, matnr) 的完整时序不被切分到不同批次。

        每个批次拉取数据 → 训练 → 立即回调 predict_callback（不缓存全量数据到内存）。

        Args:
            fetch_callback: 每批数据拉取完成后回调(batch_no, total_batches, rows_count)
            train_callback: 每批训练完成后回调(batch_no, total_batches, rows_count)
            predict_callback: 每批训练完成后回调(chunk_df, batch_no, total_batches) 用于即时预测
            start_batch: 从第几批开始（跳过之前已完成的批次），用于超时重试断点续训

        Returns:
            tuple: (model, feature_cols, total_trained_rows, train_start, train_end,
                    mae_val, rmse_val, "", batch_no)
        """
        ds = self.ds_repo.get_by_id(ds_id)
        if not ds:
            raise ValueError(f"数据源 {ds_id} 不存在")

        end_date = date.today()
        # 训练集实际需要的天数 = 用户指定的 train_days + 验证集天数 + 测试集天数
        # 因为验证集和测试集是从训练集末尾"切走"的
        total_days_needed = days + valid_days + test_days
        start_date = end_date - timedelta(days=total_days_needed)
        
        # 数据划分：训练集 ← 验证集 ← 测试集（时间递增）
        # 测试集：最后 test_days 天（用于最终评估）
        # 验证集：test_split_date 往前 valid_days 天（用于早停调参）
        # 训练集：valid_split_date 往前的所有历史数据
        test_split_date = end_date - timedelta(days=test_days)  # 2026-04-19
        valid_split_date = test_split_date - timedelta(days=valid_days)  # 2026-03-20
        train_end_date = valid_split_date  # 训练集结束于验证集开始之前
        logger.info(f"[数据划分] 总拉取天数={total_days_needed}, 训练集={days}天, 验证集={valid_days}天, 测试集={test_days}天")
        table = table_name or f"{ds.database}.ads_cockpit_fd_store_ware_d"
        # 检测 table_name 是否为完整 SELECT 语句（大小写不敏感）
        is_subquery = table_name and table_name.strip().upper().startswith(("SELECT", "(SELECT"))
        if is_subquery:
            table = self._fix_select_star(table)
        
        if is_subquery:
            # 子查询：用 CTE 替代内联嵌套，避免 Doris 重复扫描
            cte_prefix = f"WITH data_src AS ({table}) "
            table_ref = "data_src"
            top_groups_table = "data_src"
            table_alias = "data_src"
        else:
            # 普通表名或默认表名
            cte_prefix = f"WITH data_src AS ({table}) " if table_name else ""
            table_ref = "data_src" if table_name else table
            top_groups_table = "data_src" if table_name else table
            table_alias = "data_src" if table_name else "src"

        # 0. 快速获取最近活跃分组列表：取前一天峰值排前 N 的分组
        #    25.7亿行数据，GROUP BY 全表不可行，改为最近一天优先取高频分组
        #    活跃分组子查询会被训练 SQL 和测试 SQL 共用（JOIN 方式），避免拼 IN/OR 长条件
        latest_day = date.today() - timedelta(days=1)
        top_groups_dt = latest_day.strftime('%Y%m%d')
        top_groups_subquery = f"""(
            SELECT group_id, store_code, matnr
            FROM {top_groups_table}
            WHERE dt >= '{top_groups_dt}'
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            GROUP BY group_id, store_code, matnr
            ORDER BY SUM(actual_sale_untaxed_amt) DESC
            LIMIT {batch_size}
        ) top_g"""

        group_count_sql = f"""{cte_prefix}\
            SELECT /*+ SET_VAR(query_timeout=120) */
                group_id, store_code, matnr, SUM(actual_sale_untaxed_amt) as total_sales
            FROM {table_ref}
            WHERE dt >= '{top_groups_dt}'
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            GROUP BY group_id, store_code, matnr
            ORDER BY total_sales DESC
            LIMIT {batch_size}
        """
        logger.info(f"[训练] 取前一天 TOP {batch_size} 活跃分组...")
        group_rows, _ = execute_query(ds, group_count_sql)
        if not group_rows:
            raise ValueError("无有效训练数据")

        all_groups = []  # [(group_id, store_code, matnr)]
        for row in group_rows:
            all_groups.append((row[0], row[1], row[2]))

        logger.info(f"[训练] 活跃分组数={len(all_groups)}")

        # 每 N 个分组合并为一个批次，减少 DB 写入次数和模型 fit 调用
        BATCH_GROUP_SIZE = min(batch_unit, 200)  # 上限 200，防止单批过大导致 Doris 超时
        logger.info(f"[训练] batch_unit={batch_unit}, BATCH_GROUP_SIZE={BATCH_GROUP_SIZE}")
        batches = [all_groups[i:i+BATCH_GROUP_SIZE] for i in range(0, len(all_groups), BATCH_GROUP_SIZE)]
        total_batches = len(batches)

        batch_no = 0
        total_trained_rows = 0
        first_fit = True
        train_start = start_date
        train_end = end_date

        for batch_groups in batches:
            batch_no += 1
            # 超时重试时跳过已完成的批次
            if start_batch > 0 and batch_no <= start_batch:
                if train_callback:
                    train_callback(batch_no, total_batches, 0)
                continue

            # 每个分批通过独立的子查询 JOIN 确认分组匹配，不用 OR 或 IN
            batch_values = " UNION ALL ".join(
                f"SELECT {gid} AS group_id, '{scode}' AS store_code, '{mnr}' AS matnr"
                for gid, scode, mnr in batch_groups
            )
            batch_subquery = f"""(
                {batch_values}
            ) batch_g"""

            sql = f"""{cte_prefix}\
                SELECT /*+ SET_VAR(exec_mem_limit=1073741824, query_timeout=600) */
                    {table_alias}.dt, {table_alias}.group_id, {table_alias}.store_code, {table_alias}.matnr, {table_alias}.{TARGET_COL}
                FROM {table_ref}
                JOIN {batch_subquery}
                  ON {table_alias}.group_id = batch_g.group_id
                 AND {table_alias}.store_code = batch_g.store_code
                 AND {table_alias}.matnr = batch_g.matnr
                WHERE {table_alias}.dt >= '{start_date.strftime('%Y%m%d')}' AND {table_alias}.dt < '{end_date.strftime('%Y%m%d')}'
                  AND {table_alias}.exclude_flag != 1
                  AND ({table_alias}.service_flag != 1 OR {table_alias}.service_flag IS NULL)
                  AND ({table_alias}.shopping_bag_flag != 1 OR {table_alias}.shopping_bag_flag IS NULL)
                ORDER BY {table_alias}.store_code, {table_alias}.matnr, {table_alias}.dt
            """
            logger.info(f"[训练] 分批批次 batch={batch_no}/{total_batches}, 该批分组数={len(batch_groups)}, SQL: {sql.replace(chr(10), ' ').strip()}")

            # 单批超时保护：超时则跳过该批，不打断整个任务
            batch_timeout = get_settings().prediction_task_batch_timeout
            _batch_ok = True
            def _timeout_handler(signum, frame):
                raise TimeoutError(f"批次 {batch_no} 超时 ({batch_timeout}s)")

            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(batch_timeout)
            _skip_batch = False
            try:
                rows, cols = execute_query(ds, sql)
                if not rows:
                    logger.info(f"[训练] 批次 {batch_no} 无数据，跳过")
                    _skip_batch = True

                if not _skip_batch:
                    chunk_df = pd.DataFrame(rows, columns=cols)
                    chunk_df[TARGET_COL] = pd.to_numeric(chunk_df[TARGET_COL], errors="coerce").fillna(0)
                    chunk_df[TARGET_COL] = chunk_df[TARGET_COL] / 100.0

                    if fetch_callback:
                        fetch_callback(batch_no, total_batches, len(rows))

                    # 特征工程（处理全部数据，包含训练+验证+测试）
                    feat = build_features_from_history(chunk_df)
                    feat = feat.dropna(subset=feature_cols)

                    if len(feat) > 0:
                        # ========== 1. 训练阶段 ==========
                        # 训练集：验证期之前的数据
                        train_feat = feat[feat["dt"] < pd.Timestamp(valid_split_date)]
                        if len(train_feat) > 0:
                            X = train_feat[feature_cols].values
                            y = train_feat[TARGET_COL].values

                            if first_fit:
                                model.fit(X, y)
                                first_fit = False
                            else:
                                model.fit(X, y, init_model=model)

                            total_trained_rows += len(train_feat)
                            logger.info(f"[批次 {batch_no}] 训练集样本数: {len(train_feat)}")

                        if train_callback:
                            train_callback(batch_no, total_batches, len(train_feat))

                        # ========== 2. 验证阶段 ==========
                        # 验证集：验证期的数据
                        valid_feat = feat[
                            (feat["dt"] >= pd.Timestamp(valid_split_date)) &
                            (feat["dt"] < pd.Timestamp(test_split_date))
                        ]
                        if len(valid_feat) > 0:
                            y_pred_valid = model.predict(valid_feat[feature_cols])
                            y_true_valid = valid_feat[TARGET_COL].values
                            mae_valid = float(np.mean(np.abs(y_true_valid - y_pred_valid)))
                            rmse_valid = float(np.sqrt(np.mean((y_true_valid - y_pred_valid) ** 2)))
                            logger.info(f"[批次 {batch_no}] 验证集 MAE={mae_valid:.4f}, RMSE={rmse_valid:.4f}, 样本数={len(valid_feat)}")

                        # ========== 3. 测试阶段 ==========
                        # 测试集：测试期的数据
                        test_feat = feat[
                            (feat["dt"] >= pd.Timestamp(test_split_date)) &
                            (feat["dt"] < pd.Timestamp(end_date))
                        ]
                        if len(test_feat) > 0:
                            y_pred_test = model.predict(test_feat[feature_cols])
                            y_true_test = test_feat[TARGET_COL].values
                            mae_test = float(np.mean(np.abs(y_true_test - y_pred_test)))
                            rmse_test = float(np.sqrt(np.mean((y_true_test - y_pred_test) ** 2)))
                            logger.info(f"[批次 {batch_no}] 测试集 MAE={mae_test:.4f}, RMSE={rmse_test:.4f}, 样本数={len(test_feat)}")

                        # ========== 4. 预测阶段 ==========
                        # 每批训练完成后立即回调预测（不缓存全量数据）
                        if predict_callback:
                            predict_callback(chunk_df, batch_no, total_batches)
            except TimeoutError as e:
                logger.warning(f"[训练] 批次 {batch_no}/{total_batches} 超时({batch_timeout}s)，跳过该批")
                _skip_batch = True
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            if _skip_batch:
                continue

        if total_trained_rows == 0:
            raise ValueError("训练数据不足（无有效特征行）")

        # 评估：用所有分组的测试集数据（最后 7 天）
        # 注意：测试 SQL 需要从 start_date 起查，确保 build_features_from_history
        # 能生成 lag_28 等特征，然后只过滤 dt >= test_split_date 的样本来评估
        mae_val, rmse_val = 0.0, 0.0
        test_sample_count = 0
        try:
            # 查询所有活跃分组的历史数据（含训练范围，供特征工程生成 lag 特征）
            # 用 JOIN 子查询替代 OR 拼接，避免超长 SQL
            test_sql = f"""{cte_prefix}\
                SELECT /*+ SET_VAR(exec_mem_limit=1073741824, query_timeout=600) */
                    {table_alias}.dt, {table_alias}.group_id, {table_alias}.store_code, {table_alias}.matnr, {table_alias}.{TARGET_COL}
                FROM {table_ref}
                JOIN {top_groups_subquery}
                  ON {table_alias}.group_id = top_g.group_id
                 AND {table_alias}.store_code = top_g.store_code
                 AND {table_alias}.matnr = top_g.matnr
                WHERE {table_alias}.dt >= '{start_date.strftime('%Y%m%d')}' AND {table_alias}.dt < '{end_date.strftime('%Y%m%d')}'
                  AND {table_alias}.exclude_flag != 1
                  AND ({table_alias}.service_flag != 1 OR {table_alias}.service_flag IS NULL)
                  AND ({table_alias}.shopping_bag_flag != 1 OR {table_alias}.shopping_bag_flag IS NULL)
                ORDER BY {table_alias}.store_code, {table_alias}.matnr, {table_alias}.dt
            """
            logger.info("[评估] 查询测试集数据（含历史范围供特征工程）...")
            test_rows, test_cols = execute_query(ds, test_sql)
            if test_rows:
                test_df = pd.DataFrame(test_rows, columns=test_cols)
                test_df[TARGET_COL] = pd.to_numeric(test_df[TARGET_COL], errors="coerce").fillna(0)
                test_df[TARGET_COL] = test_df[TARGET_COL] / 100.0
                test_all_feat = build_features_from_history(test_df)
                test_feat = test_all_feat.dropna(subset=feature_cols)
                # 只过滤测试时间段的行进行评估
                # build_features_from_history 把 dt 转成了 datetime64[ns]，需用 pd.Timestamp 比较
                ts_split = pd.Timestamp(test_split_date)
                ts_end = pd.Timestamp(end_date)
                test_feat = test_feat[
                    (test_feat["dt"] >= ts_split) & (test_feat["dt"] < ts_end)
                ]
                test_sample_count = len(test_feat)
                if test_sample_count > 0:
                    y_pred = model.predict(test_feat[feature_cols])
                    y_true = test_feat[TARGET_COL].values
                    mae_val = float(np.mean(np.abs(y_true - y_pred)))
                    rmse_val = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
                    logger.info(f"[评估] 测试集 MAE={mae_val:.4f}, RMSE={rmse_val:.4f}, 样本数={test_sample_count}")

            # ========== 验证集评估 ==========
            if valid_days and valid_days > 0:
                logger.info("[评估] 查询验证集数据...")
                valid_sql = f"""{cte_prefix}\
                    SELECT {table_alias}.dt, {table_alias}.store_code, {table_alias}.matnr, {table_alias}.group_id, {table_alias}.actual_sale_untaxed_amt
                    FROM {table_ref}
                    JOIN {top_groups_subquery}
                      ON {table_alias}.group_id = top_g.group_id
                     AND {table_alias}.store_code = top_g.store_code
                     AND {table_alias}.matnr = top_g.matnr
                    WHERE {table_alias}.dt >= '{valid_split_date.strftime('%Y%m%d')}' AND {table_alias}.dt < '{test_split_date.strftime('%Y%m%d')}'
                      AND {table_alias}.exclude_flag != 1
                      AND ({table_alias}.service_flag != 1 OR {table_alias}.service_flag IS NULL)
                      AND ({table_alias}.shopping_bag_flag != 1 OR {table_alias}.shopping_bag_flag IS NULL)
                    ORDER BY {table_alias}.store_code, {table_alias}.matnr, {table_alias}.dt
                """
                valid_rows, valid_cols = execute_query(ds, valid_sql)
                if valid_rows:
                    valid_df = pd.DataFrame(valid_rows, columns=valid_cols)
                    valid_df[TARGET_COL] = pd.to_numeric(valid_df[TARGET_COL], errors="coerce").fillna(0)
                    valid_df[TARGET_COL] = valid_df[TARGET_COL] / 100.0
                    valid_all_feat = build_features_from_history(valid_df)
                    valid_feat = valid_all_feat.dropna(subset=feature_cols)
                    # 只过滤验证集时间段
                    ts_valid_start = pd.Timestamp(valid_split_date)
                    ts_valid_end = pd.Timestamp(test_split_date)
                    valid_feat = valid_feat[
                        (valid_feat["dt"] >= ts_valid_start) & (valid_feat["dt"] < ts_valid_end)
                    ]
                    valid_sample_count = len(valid_feat)
                    if valid_sample_count > 0:
                        y_pred_valid = model.predict(valid_feat[feature_cols])
                        y_true_valid = valid_feat[TARGET_COL].values
                        mae_valid = float(np.mean(np.abs(y_true_valid - y_pred_valid)))
                        rmse_valid = float(np.sqrt(np.mean((y_true_valid - y_pred_valid) ** 2)))
                        logger.info(f"[评估] 验证集 MAE={mae_valid:.4f}, RMSE={rmse_valid:.4f}, 样本数={valid_sample_count}")
        except Exception as e:
            logger.warning(f"[评估] 测试集/验证集评估失败: {e}")

        return (model, feature_cols, total_trained_rows, train_start, train_end, mae_val, rmse_val, "", batch_no)

    def train(self, ds_id: int, train_days: int = None, test_days: int = None, 
              valid_days: int = None, table_name: str = None,
              model_type: str = "lightgbm") -> int:
        """
        训练模型（通过算法注册表分发）。

        Args:
            ds_id: 数据源ID
            train_days: 训练集天数（默认配置）
            test_days: 测试集天数（默认30天）
            valid_days: 验证集天数（默认30天）
            table_name: 自定义表名
            model_type: 模型类型（"lightgbm" / "prophet"），默认 lightgbm

        Returns: 模型记录 ID
        """
        train_days = train_days or settings.prediction_train_default_days
        test_days = test_days if test_days is not None else settings.prediction_test_days
        valid_days = valid_days if valid_days is not None else settings.prediction_valid_days
        
        # 获取算法
        algo = self._get_algorithm(model_type)
        
        logger.info(f"[预测] 开始训练，数据源={ds_id}，类型={model_type}，"
                     f"训练={train_days}天，测试={test_days}天，验证={valid_days}天")

        # 创建模型记录
        model_record = self.model_repo.create(
            data_source_id=ds_id,
            model_type=model_type,
            status="training",
        )

        try:
            # 1. 拉取历史数据
            df = self._fetch_history_data(ds_id, train_days, table_name=table_name)
            if len(df) < settings.prediction_min_history_days * 10:
                raise ValueError(
                    f"历史数据不足({len(df)}行)，需要至少 {settings.prediction_min_history_days * 10} 行"
                )

            # 2. 算法训练（内部包含特征工程+模型训练+评估）
            model, metrics = algo.train(df, model_record, self)

            # 3. 保存模型
            model_filename = f"{model_type}_{ds_id}_{model_record.id}.pkl"
            model_path = os.path.join(self.model_dir, model_filename)
            algo.save(model, model_path)

            # 4. 更新模型记录
            feature_cols = get_feature_columns()
            df_dates = df["dt"] if hasattr(df, "dt") else pd.Series()
            self.model_repo.update_status(
                model_record.id, "ready",
                model_path=model_path,
                feature_count=len(feature_cols),
                train_start_date=df_dates.min().date() if not df_dates.empty else date.today(),
                train_end_date=df_dates.max().date() if not df_dates.empty else date.today(),
                train_row_count=len(df),
                model_metrics=metrics,
                trained_at=datetime.now(TZ_UTC8),
            )

            logger.info(f"[预测] 训练完成: model_id={model_record.id}, "
                         f"MAE={metrics.get('mae', 'N/A')}, RMSE={metrics.get('rmse', 'N/A')}")
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
        
        # 旧模型降级：从缓存数据动态计算 RMSE（兼容旧模型无 model_metrics）
        model_metrics = model_record.model_metrics or {}
        _rmse_from_metrics = model_metrics.get("rmse")
        if _rmse_from_metrics is not None:
            try:
                _rmse_from_metrics = float(_rmse_from_metrics)
            except (TypeError, ValueError):
                _rmse_from_metrics = None
        if _rmse_from_metrics is None or _rmse_from_metrics <= 0:
            try:
                _val_days = min(forecast_days * 2, 14)
                _last_ref_date = df_feat["dt"].max()
                _val_start = _last_ref_date - pd.Timedelta(days=_val_days)
                _val_data = df_feat[df_feat["dt"] >= _val_start]
                if len(_val_data) >= 10:
                    _y_true = _val_data[TARGET_COL].values
                    _y_pred = model.predict(_val_data[feature_cols])
                    _computed = float(np.sqrt(np.mean((_y_true - _y_pred) ** 2)))
                    if _computed > 0:
                        _rmse_from_metrics = _computed
                        logger.info(f"[预测-缓存] 从历史数据动态计算 RMSE={_rmse_from_metrics:.2f} ({len(_val_data)} 条样本)")
            except Exception as _e:
                logger.warning(f"[预测-缓存] 动态 RMSE 计算失败: {_e}")
        
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
            
            # 按每个 SKU 递归滚动预测
            # 原理：维护历史+预测值的 DataFrame，每次追加预测行后重新计算特征
            lookback_window = 60
            for sku_idx, (sku_row_idx, sku_row) in enumerate(sku_latest.iterrows()):
                store_code = sku_row["store_code"]
                matnr_val = sku_row["matnr"]

                sku_history = store_df[
                    (store_df["store_code"] == store_code) &
                    (store_df["matnr"] == matnr_val)
                ].sort_values("dt")

                # 取历史最后 lookback_window 天的原始数据（未构造特征）
                base_cols = ["dt", "store_code", "matnr", TARGET_COL]
                history_raw = sku_history[base_cols].tail(lookback_window).copy()

                if len(history_raw) < 7:
                    continue

                # 先构造一次特征，确认能产出有效���
                history_feat = build_features_from_history(history_raw.copy())
                history_feat = history_feat.dropna(subset=feature_cols)

                if history_feat.empty:
                    continue

                # 获取最后一天的日期，用于推算未来日期
                last_date = pd.to_datetime(history_raw["dt"].iloc[-1], format="%Y%m%d", errors="coerce")

                for i in range(forecast_days):
                    # 构造当前历史的完整特征
                    current_feat = build_features_from_history(history_raw.copy())
                    current_feat = current_feat.dropna(subset=feature_cols)

                    if current_feat.empty:
                        break

                    # 取最后一天的特征行用于预测（保持 DataFrame 格式，保留特征名）
                    row_df = current_feat.iloc[-1:][feature_cols]

                    # 计算点预测
                    pred = max(float(model.predict(row_df)[0]), 0)

                    # 使用模型 RMSE 计算 90% 置信区间（pred ± 1.645×RMSE）
                    if _rmse_from_metrics is not None and _rmse_from_metrics > 0:
                        margin = 1.645 * _rmse_from_metrics
                        lower = round(max(pred - margin, 0), 2)
                        upper = round(pred + margin, 2)
                    else:
                        lower = upper = None

                    # 计算预测日期
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

                    # 将预测值追加到历史 DataFrame，下次循环重新计算所有特征
                    new_row = pd.DataFrame([{
                        "dt": forecast_dt_str,
                        "store_code": store_code,
                        "matnr": matnr_val,
                        TARGET_COL: pred,
                    }])
                    history_raw = pd.concat([history_raw, new_row], ignore_index=True)
                    # 保持窗口大小
                    if len(history_raw) > lookback_window:
                        history_raw = history_raw.iloc[-lookback_window:].reset_index(drop=True)

            if progress_callback:
                progress_callback(model_record.id, store_idx + 1, total_stores, store_code)

        # 批量查询商品名称
        if results:
            unique_pairs = list({(r.store_code, r.matnr) for r in results})
            ware_name_map = self._lookup_ware_names(model_record.data_source_id, unique_pairs)
            for r in results:
                r.ware_name = ware_name_map.get((r.store_code, r.matnr), "")

        return results

    @staticmethod
    def _fix_select_star(sql: str) -> str:
        """将子查询中的 SELECT * 替换为实际需要的列，减少 Doris I/O

        只替换最外层的 SELECT *，不影响嵌套子查询。
        若不是 SELECT * 则原样返回。
        """
        if not re.match(r'^\s*SELECT\s+\*\s+FROM', sql, re.IGNORECASE | re.DOTALL):
            return sql
        # 替换 'SELECT *' → 'SELECT col1, col2, ...'（保持原有大小写风格）
        return re.sub(
            r'(?i)^(\s*SELECT)\s+\*\s+(FROM)',
            lambda m: f"{m.group(1)} {_REQUIRED_COLS_SQL} {m.group(2)}",
            sql,
            count=1,
        )

    def _resolve_table_context(self, ds, table_name: str = None) -> dict:
        """解析表名/子查询，返回 SQL 上下文

        优化：
        1. 自动将 SELECT * 替换为需要的列，减少 Doris I/O（最高可减少 60%+）
        2. 统一使用 CTE（WITH data_src AS (...)），避免子查询被多层内联

        Returns:
            dict with keys: cte_prefix, table_ref, top_groups_table, table_alias, is_subquery
        """
        table = table_name or f"{ds.database}.ads_cockpit_fd_store_ware_d"
        is_subquery = table_name and table_name.strip().upper().startswith(("SELECT", "(SELECT"))

        # 优化1：将 SELECT * 替换为实际需要的列
        if is_subquery:
            table = self._fix_select_star(table)

        # 统一 CTE 名称，简化逻辑
        if is_subquery or table_name:
            cte_name = "data_src"
            cte_prefix = f"WITH {cte_name} AS ({table}) "
            return {
                "cte_prefix": cte_prefix,
                "table_ref": cte_name,
                "top_groups_table": cte_name,
                "table_alias": cte_name,
                "is_subquery": is_subquery,
            }
        else:
            # 默认无自定义表名：直接使用全量表名，不改动 LightGBM 原生路径
            return {
                "cte_prefix": "",
                "table_ref": table,
                "top_groups_table": table,
                "table_alias": "src",
                "is_subquery": False,
            }

    def _query_top_groups(self, ds, table_name: str, batch_size: int) -> list:
        """查前一天 TOP-N 活跃分组"""
        ctx = self._resolve_table_context(ds, table_name)
        latest_day = date.today() - timedelta(days=1)
        top_groups_dt = latest_day.strftime('%Y%m%d')

        sql = f"""{ctx['cte_prefix']}\
            SELECT /*+ SET_VAR(query_timeout=120) */
                group_id, store_code, matnr, SUM(actual_sale_untaxed_amt) as total_sales
            FROM {ctx['table_ref']}
            WHERE dt >= '{top_groups_dt}'
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            GROUP BY group_id, store_code, matnr
            ORDER BY total_sales DESC
            LIMIT {batch_size}
        """
        rows, _ = execute_query(ds, sql)
        return [(row[0], row[1], row[2]) for row in rows]

    def _build_batch_fetch_sql(self, ctx: dict, batch_groups: list,
                                start_date: date, end_date: date) -> str:
        """为一批分组生成数据拉取 SQL

        batch_g 已精确指定当前批次的 SKU 列表，不再需要 top_g JOIN
        （减少了 1 次 GROUP BY + ORDER BY + 扫描）。
        """
        table_alias = ctx["table_alias"]

        batch_values = " UNION ALL ".join(
            f"SELECT {gid} AS group_id, '{scode}' AS store_code, '{mnr}' AS matnr"
            for gid, scode, mnr in batch_groups
        )

        sql = f"""{ctx['cte_prefix']}\
            SELECT /*+ SET_VAR(exec_mem_limit=1073741824, query_timeout=600) */
                {table_alias}.dt, {table_alias}.group_id, {table_alias}.store_code,
                {table_alias}.matnr, {table_alias}.{TARGET_COL}
            FROM {ctx['table_ref']}
            JOIN ({batch_values}) batch_g
              ON {table_alias}.group_id = batch_g.group_id
             AND {table_alias}.store_code = batch_g.store_code
             AND {table_alias}.matnr = batch_g.matnr
            WHERE {table_alias}.dt >= '{start_date.strftime('%Y%m%d')}'
              AND {table_alias}.dt < '{end_date.strftime('%Y%m%d')}'
              AND {table_alias}.exclude_flag != 1
              AND ({table_alias}.service_flag != 1 OR {table_alias}.service_flag IS NULL)
              AND ({table_alias}.shopping_bag_flag != 1 OR {table_alias}.shopping_bag_flag IS NULL)
            ORDER BY {table_alias}.store_code, {table_alias}.matnr, {table_alias}.dt
        """
        return sql

    def _build_top_groups_subquery(self, top_groups_table: str) -> str:
        """构建活跃分组子查询（用于 JOIN）"""
        latest_day = date.today() - timedelta(days=1)
        top_groups_dt = latest_day.strftime('%Y%m%d')
        return f"""(
            SELECT group_id, store_code, matnr
            FROM {top_groups_table}
            WHERE dt >= '{top_groups_dt}'
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            GROUP BY group_id, store_code, matnr
            ORDER BY SUM(actual_sale_untaxed_amt) DESC
        ) top_g"""

    def _batch_train_predict(
        self,
        algo: BasePredictor,
        ds,
        model_record,
        train_days: int,
        forecast_days: int,
        table_name: str = None,
        test_days: int = 30,
        valid_days: int = 30,
        batch_size: int = 200,
        batch_unit: int = 10,
        start_batch: int = 0,
        progress_callback: callable = None,
    ) -> tuple:
        """通用分批训练+预测（适用于 LightGBM 外的算法）

        按前一天 TOP-N 活跃分组分批处理。每批：拉取 → 训练 → 预测 → 保存结果。

        Returns:
            (batch_model, metrics, total_predictions)
        """
        end_date = date.today()
        total_days_needed = train_days + valid_days + test_days
        start_date = end_date - timedelta(days=total_days_needed)

        ctx = self._resolve_table_context(ds, table_name)

        # 1. 查活跃分组
        all_groups = self._query_top_groups(ds, table_name, batch_size)
        if not all_groups:
            raise ValueError("无有效训练数据")

        batch_group_size = min(batch_unit, 200)
        batches = [all_groups[i:i+batch_group_size]
                   for i in range(0, len(all_groups), batch_group_size)]

        logger.info(f"[分批训练] {len(all_groups)} 个分组, {len(batches)} 批")

        # 断点续训保护：如果 start_batch >= total_batches，说明所有批次之前已完成，
        # 但无 checkpoint 可加载（Prophet 路径），从头开始
        if start_batch > 0 and start_batch >= len(batches):
            logger.info(f"[分批训练] start_batch={start_batch} >= 总批数={len(batches)}，重置为从头开始")
            start_batch = 0

        batch_model = None
        total_preds = 0
        all_mae, all_rmse = [], []

        for batch_no, batch_groups in enumerate(batches, 1):
            if start_batch > 0 and batch_no <= start_batch:
                continue

            # 2. 拉取本批数据（在 SQL 查询前先更新进度，避免长时间无反馈）
            if progress_callback:
                progress_callback(batch_no, len(batches), None)
            sql = self._build_batch_fetch_sql(ctx, batch_groups, start_date, end_date)
            logger.info(f"[分批训练] 批次 {batch_no}/{len(batches)} SQL: {sql.replace(chr(10), ' ').strip()}")
            rows, cols = execute_query(ds, sql)
            if not rows:
                logger.info(f"[分批训练] 批次 {batch_no}/{len(batches)} 无数据")
                continue
            logger.info(f"[分批训练] 批次 {batch_no}/{len(batches)} 拉取 {len(rows)} 行")

            chunk = pd.DataFrame(rows, columns=cols)
            chunk[TARGET_COL] = pd.to_numeric(chunk[TARGET_COL], errors="coerce").fillna(0)
            chunk[TARGET_COL] = chunk[TARGET_COL] / 100.0

            # 3. 训练
            batch_model, batch_metrics = algo.train(chunk, model_record, self)
            if batch_metrics.get("mae") is not None:
                all_mae.append(batch_metrics["mae"])
            if batch_metrics.get("rmse") is not None:
                all_rmse.append(batch_metrics["rmse"])

            # 4. 预测
            batch_results = algo.predict(
                batch_model, model_record, chunk, forecast_days, self
            )
            if batch_results:
                self.result_repo.bulk_save(batch_results)
                total_preds += len(batch_results)

            # 5. 进度回调
            if progress_callback:
                progress_callback(batch_no, len(batches), len(batch_results))

        if batch_model is None:
            raise ValueError("训练数据不足（所有批次无有效数据）")

        avg_mae = float(np.mean(all_mae)) if all_mae else 0.0
        avg_rmse = float(np.mean(all_rmse)) if all_rmse else 0.0
        metrics = {"mae": round(avg_mae, 2), "rmse": round(avg_rmse, 2)}

        return batch_model, metrics, total_preds

    def predict(self, ds_id: int, forecast_days: int = None, table_name: str = None,
                model_id: int = None, progress_callback: callable = None) -> tuple:
        """
        用指定模型预测未来 N 天销售额（通过算法注册表分发）。

        如果 model_id 不传，使用该数据源最新 ready 的模型。

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

        # 按算法类型分发
        algo = self._get_algorithm(model_record.model_type)
        model = algo.load(model_record.model_path)

        # 拉取最新数据
        df = self._fetch_history_data(ds_id, days=60, table_name=table_name)

        # 算法预测（内部包含特征工程+滚动预测+置信区间+商品名称查询）
        # 将 progress_callback 通过 kwargs 传递，算法可选用
        results = algo.predict(
            model, model_record, df, forecast_days, self,
            progress_callback=progress_callback,
        )

        count = self.result_repo.bulk_save(results)
        logger.info(f"[预测] 写入 {count} 条预测结果，模型 model_id={model_record.id}, "
                     f"类型={model_record.model_type}")
        return count, model_record.id
