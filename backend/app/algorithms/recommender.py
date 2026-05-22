"""自动算法推荐器

通过对历史数据进行轻量采样分析，提取数据特征（数据量、周季节性强度、趋势），
为每个算法计算推荐得分，返回排序后的推荐结果。

工作流程：
  1. 从 Doris 采样 TOP-N 活跃分组的最近 N 天数据
  2. 对每个采样分组计算特征（季节强度、趋势强度、变异系数等）
  3. 聚合特征后按规则为每种算法打分
  4. 返回排序的推荐列表 + 推荐理由

用法：
  recommender = AlgorithmRecommender()
  result = recommender.recommend(data_source_id=1, table_name="...")
  # result = [{ "algorithm": "lightgbm", "score": 85, "reason": "...", "label": "推荐" }, ...]
"""

from __future__ import annotations
import logging
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# 采样参数
_SAMPLE_GROUPS = 10       # 采样分组数
_SAMPLE_DAYS = 60          # 采样天数

# 评分权重
SCORE_MAX = 100
SCORE_MIN = 10


class AlgorithmRecommender:
    """自动算法推荐器

    每次调用 recommend() 执行：
      1. 查询采样数据
      2. 提取特征
      3. 评分
      4. 返回排序结果
    """

    def __init__(self):
        self._label_cache: Dict[str, str] = {}

    def recommend(
        self,
        data_source_id: int,
        table_name: Optional[str] = None,
        ds_repo=None,
        service: Any = None,
    ) -> List[Dict[str, Any]]:
        """对指定数据源执行算法推荐

        Args:
            data_source_id: 数据源 ID
            table_name: 表名或子查询
            ds_repo: DataSourceRepository（用于获取数据源连接信息）
            service: PredictionService 实例（用于 SQL 执行）

        Returns:
            推荐列表，按分数降序：
            [
                {
                    "algorithm": "lightgbm",
                    "score": 85,
                    "label": "推荐",
                    "reason": "...",
                    "details": {...}
                },
                ...
            ]
        """
        if service is None:
            raise ValueError("AlgorithmRecommender.recommend 需要 service 参数")

        # 1. 查询采样数据特征
        features = self._analyze_data(data_source_id, table_name, service)

        # 2. 评分
        scores = self._score(features)

        # 3. 格式化输出
        result = []
        for algo_name, entry in sorted(scores.items(), key=lambda x: -x[1]["score"]):
            result.append({
                "algorithm": algo_name,
                "score": entry["score"],
                "label": entry["label"],
                "reason": entry["reason"],
            })

        return result

    # ── 1. 数据分析 ──────────────────────────────────

    def _analyze_data(
        self,
        data_source_id: int,
        table_name: Optional[str],
        service: Any,
    ) -> Dict[str, Any]:
        """从 Doris 采样分析数据特征

        Returns:
            {
                "total_groups": int,       # 分组总数
                "total_rows": int,          # 采样数据行数
                "avg_days_per_group": float, # 每组平均数据天数
                "weekly_seasonality": float, # 周季节性强度 0~1
                "trend_strength": float,     # 趋势强度 0~1
                "cv_mean": float,            # 平均变异系数
                "rows_per_group_mean": float, # 每组平均行数
            }
        """
        # 默认值（当数据查询失败时使用保守推荐）
        defaults = {
            "total_groups": 0,
            "total_rows": 0,
            "avg_days_per_group": 0.0,
            "weekly_seasonality": 0.0,
            "trend_strength": 0.0,
            "cv_mean": 0.5,
            "rows_per_group_mean": 0.0,
        }

        try:
            # 获取数据源并执行采样查询
            ds = service.ds_repo.get_by_id(data_source_id)
            if not ds:
                logger.warning(f"[推荐] 数据源 {data_source_id} 不存在")
                return defaults

            table = self._resolve_table(ds, table_name)
            end_date = date.today()
            start_date = end_date - timedelta(days=_SAMPLE_DAYS)
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")

            # 0. 获取总分组数（快速 COUNT）
            count_sql = f"""\
                SELECT COUNT(*) AS group_count
                FROM (
                    SELECT store_code, matnr
                    FROM {table}
                    WHERE dt >= {start_str} AND dt < {end_str}
                      AND exclude_flag != 1
                      AND (service_flag != 1 OR service_flag IS NULL)
                      AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
                    GROUP BY store_code, matnr
                ) AS _g
            """
            count_rows, _ = self._execute(service, ds, count_sql)
            total_groups = int(count_rows[0][0]) if count_rows else 0

            # 1. 采样 TOP-N 活跃分组的数据
            raw_features = self._sample_group_data(
                service, ds, table, start_date, end_date, _SAMPLE_GROUPS
            )

            if not raw_features:
                logger.info("[推荐] 无采样数据，使用默认特征")
                defaults["total_groups"] = total_groups
                return defaults

            # 2. 聚合特征
            features = self._aggregate_features(raw_features)
            features["total_groups"] = total_groups

            logger.info(
                f"[推荐] 分析完成: "
                f"groups={total_groups}, "
                f"seasonality={features['weekly_seasonality']:.2f}, "
                f"trend={features['trend_strength']:.2f}, "
                f"cv={features['cv_mean']:.2f}, "
                f"avg_days={features['avg_days_per_group']:.0f}"
            )
            return features

        except Exception as e:
            logger.warning(f"[推荐] 数据分析失败: {e}", exc_info=True)
            return defaults

    def _sample_group_data(
        self,
        service: Any,
        ds: Any,
        table: str,
        start_date: date,
        end_date: date,
        limit: int,
    ) -> List[pd.DataFrame]:
        """采样 TOP-N 分组的时序数据"""
        import pandas as pd

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        # 先查 TOP 分组
        top_sql = f"""\
            SELECT store_code, matnr, SUM(actual_sale_untaxed_amt) AS total_sales
            FROM {table}
            WHERE dt >= {start_str} AND dt < {end_str}
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            GROUP BY store_code, matnr
            ORDER BY total_sales DESC
            LIMIT {limit}
        """
        top_rows, cols = self._execute(service, ds, top_sql)
        if not top_rows:
            return []

        groups = [(r[0], r[1]) for r in top_rows]

        # 查每个分组的时序数据
        # 用 OR 拼接（少量分组时 OR 比 JOIN 子查询更简单）
        conditions = " OR ".join(
            f"(store_code = '{sc}' AND matnr = '{mn}')"
            for sc, mn in groups
        )
        data_sql = f"""\
            SELECT dt, store_code, matnr, actual_sale_untaxed_amt
            FROM {table}
            WHERE ({conditions})
              AND dt >= {start_str} AND dt < {end_str}
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            ORDER BY store_code, matnr, dt
        """
        rows, cols = self._execute(service, ds, data_sql)
        if not rows:
            return []

        df = pd.DataFrame(rows, columns=cols)
        if df.empty:
            return []

        df["actual_sale_untaxed_amt"] = (
            pd.to_numeric(df["actual_sale_untaxed_amt"], errors="coerce")
            .fillna(0) / 100.0
        )
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d", errors="coerce")

        # 按分组拆分为独立 DataFrame
        result = []
        for (sc, mn), grp in df.groupby(["store_code", "matnr"]):
            grp = grp.sort_values("dt").reset_index(drop=True)
            if len(grp) >= 7:  # 至少 7 天才有分析意义
                result.append(grp)

        return result

    def _aggregate_features(
        self, raw_features: List[pd.DataFrame]
    ) -> Dict[str, float]:
        """从采样分组数据聚合特征

        Args:
            raw_features: 每个分组的 DataFrame 列表

        Returns:
            dict with avg_days_per_group, weekly_seasonality, trend_strength, cv_mean
        """
        import pandas as pd
        import numpy as np

        n_groups = len(raw_features)
        if n_groups == 0:
            return {
                "total_rows": 0,
                "avg_days_per_group": 0.0,
                "weekly_seasonality": 0.0,
                "trend_strength": 0.0,
                "cv_mean": 0.5,
                "rows_per_group_mean": 0.0,
            }

        all_rows = 0
        day_counts = []
        seasonal_scores = []
        trend_scores = []
        cvs = []

        for grp in raw_features:
            grp = grp.dropna(subset=["actual_sale_untaxed_amt"])
            if len(grp) < 7:
                continue

            all_rows += len(grp)
            day_counts.append(len(grp))
            vals = grp["actual_sale_untaxed_amt"].values

            # 变异系数 CV = std / mean
            mean_val = float(np.mean(vals))
            std_val = float(np.std(vals))
            cv = std_val / mean_val if mean_val > 0 else 0.0
            cvs.append(cv)

            # 周季节性强度
            # 方法：计算各 weekday 组间方差占总方差的比例
            grp["dow"] = grp["dt"].dt.dayofweek
            dow_means = grp.groupby("dow")["actual_sale_untaxed_amt"].mean()
            if len(dow_means) >= 2:
                between_var = float(np.var(dow_means.values))
                total_var = float(np.var(vals))
                if total_var > 0:
                    seasonality = min(between_var / total_var, 1.0)
                    seasonal_scores.append(seasonality)

            # 趋势强度
            # 方法：线性回归 R² 作为趋势强度
            if len(grp) >= 14:
                x = np.arange(len(grp))
                y = vals
                slope, intercept = np.polyfit(x, y, 1)
                y_pred = slope * x + intercept
                ss_res = float(np.sum((y - y_pred) ** 2))
                ss_tot = float(np.sum((y - np.mean(y)) ** 2))
                if ss_tot > 0:
                    r_squared = max(0, 1 - ss_res / ss_tot)
                    trend_scores.append(r_squared)

        return {
            "total_rows": all_rows,
            "avg_days_per_group": float(np.mean(day_counts)) if day_counts else 0.0,
            "weekly_seasonality": float(np.mean(seasonal_scores)) if seasonal_scores else 0.0,
            "trend_strength": float(np.mean(trend_scores)) if trend_scores else 0.0,
            "cv_mean": float(np.mean(cvs)) if cvs else 0.5,
            "rows_per_group_mean": float(np.mean(day_counts)) if day_counts else 0.0,
        }

    # ── 2. 评分逻辑 ──────────────────────────────────

    def _score(self, features: Dict[str, Any]) -> Dict[str, Dict]:
        """根据数据特征为每种算法评分

        评分规则：
          lightgbm: 大分组/大数据量优先
          naive:    强季节性/低变异优先
          sarima:   强季节性/中数据量优先
          prophet:  强趋势/强季节性优先

        Returns:
            {algorithm: {"score": int, "label": str, "reason": str}}
        """
        g = features["total_groups"]
        sea = features["weekly_seasonality"]
        trend = features["trend_strength"]
        cv = features["cv_mean"]
        avg_days = features["avg_days_per_group"]
        rows = features["total_rows"]
        rows_per_group = features["rows_per_group_mean"]

        scores: Dict[str, Dict] = {}

        # ── LightGBM ──
        lgb_score = 50
        lgb_reasons = []
        if rows > 50000:
            lgb_score += 20
            lgb_reasons.append("大规模数据 √")
        elif rows > 10000:
            lgb_score += 10
            lgb_reasons.append("数据量充足")
        if g > 100:
            lgb_score += 15
            lgb_reasons.append("分组数多，增量训练优势")
        elif g > 20:
            lgb_score += 5
        if trend > 0.3:
            lgb_score += 10
            lgb_reasons.append("能学习趋势模式")
        if cv > 0.8:
            lgb_score += 5  # 高波动数据也能处理
        if g <= 5:
            lgb_score -= 10  # 分组太少，用 LightGBM 杀鸡用牛刀
        lgb_reasons.append("通用场景首选")
        scores["lightgbm"] = self._make_entry(
            lgb_score, "lightgbm", lgb_reasons
        )

        # ── Naive 基线 ──
        naive_score = 30
        naive_reasons = []
        if sea > 0.3:
            naive_score += 20
            naive_reasons.append("周季节性明显，基线可信")
        elif sea > 0.15:
            naive_score += 10
            naive_reasons.append("存在一定季节性")
        if cv < 0.3:
            naive_score += 15
            naive_reasons.append("数据波动小，基线精度高")
        if rows < 5000:
            naive_score += 15
            naive_reasons.append("数据量小，其他算法无优势")
        if g > 200:
            naive_score += 10
            naive_reasons.append("分组极多，零训练开销优势显著")
        if avg_days < 14:
            naive_score += 20
            naive_reasons.append("历史不足，仅 Naive 可用")
        if g >= 1:
            naive_reasons.append("零训练成本，建议作为对比基线")
        scores["naive"] = self._make_entry(
            naive_score, "naive", naive_reasons
        )

        # ── SARIMA ──
        sarima_score = 40
        sarima_reasons = []
        if sea > 0.4:
            sarima_score += 20
            sarima_reasons.append("强周季节性，SARIMA 优势明显")
        elif sea > 0.2:
            sarima_score += 10
            sarima_reasons.append("有一定季节性")
        if avg_days >= 30 and rows_per_group >= 30:
            sarima_score += 15
            sarima_reasons.append("时序长度充足")
        elif avg_days < 14:
            sarima_score -= 30
            sarima_reasons.append("历史不足 14 天，无法拟合")
        if g > 50:
            sarima_score -= 15
            sarima_reasons.append("分组数过多，训练耗时")
        if cv < 0.3:
            sarima_score += 10
            sarima_reasons.append("低波动序列，SARIMA 拟合稳定")
        scores["sarima"] = self._make_entry(
            sarima_score, "sarima", sarima_reasons
        )

        # ── Prophet ──
        prophet_score = 35
        prophet_reasons = []
        if trend > 0.3:
            prophet_score += 20
            prophet_reasons.append("强趋势模式，Prophet 擅长")
        elif trend > 0.15:
            prophet_score += 10
        if sea > 0.3:
            prophet_score += 10
            prophet_reasons.append("周季节性可建模")
        if avg_days >= 60:
            prophet_score += 15
            prophet_reasons.append("历史充足，Prophet 拟合效果好")
        elif avg_days < 30:
            prophet_score -= 15
            prophet_reasons.append("历史偏短，Prophet 效果受限")
        if g > 50:
            prophet_score -= 10
            prophet_reasons.append("分组较多，Prophet 训练慢")
        if cv > 0.6:
            prophet_score += 5
        prophet_reasons.append("需安装 prophet 包")
        scores["prophet"] = self._make_entry(
            prophet_score, "prophet", prophet_reasons
        )

        # 兜底：score 范围 [SCORE_MIN, SCORE_MAX]
        for name in scores:
            scores[name]["score"] = max(SCORE_MIN, min(SCORE_MAX, scores[name]["score"]))

        return scores

    def _make_entry(
        self, score: int, algorithm: str, reasons: List[str]
    ) -> Dict:
        """构建单条评分结果"""
        # 计算标签
        if score >= 75:
            label = "强烈推荐"
        elif score >= 55:
            label = "推荐"
        elif score >= 35:
            label = "可选"
        else:
            label = "不推荐"

        # 取最重要的 2 个理由
        important_reasons = reasons[:3]

        return {
            "score": score,
            "label": label,
            "reason": "；".join(important_reasons) if important_reasons else "",
        }

    # ── 工具方法 ─────────────────────────────────────

    def _resolve_table(self, ds: Any, table_name: Optional[str]) -> str:
        """解析表名"""
        if table_name:
            t = table_name.strip()
            if t.upper().startswith(("SELECT", "(SELECT")):
                return f"({t}) AS _sub"
            return t
        return f"{ds.database}.ads_cockpit_fd_store_ware_d"

    def _execute(self, service: Any, ds: Any, sql: str):
        """执行 SQL 查询"""
        from app.utils.db_executor import execute_query
        return execute_query(ds, sql)
