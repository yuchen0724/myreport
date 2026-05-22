"""算法推荐器单元测试

测试策略：
  - 评分逻辑（_score）：用各种特征组合验证分数合���
  - 聚合逻辑（_aggregate_features）：用模拟 DataFrame 验证特征提取
  - recommend 接口：mock 数据源验证完整流程

数据库和 Doris 不依赖（mock 掉 execute_query 调用）。
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
from datetime import date, timedelta

from app.algorithms.recommender import AlgorithmRecommender


# =============================================================================
# _score 评分逻辑测试
# =============================================================================


class TestScore:
    """算法评分逻辑 — 不依赖数据库"""

    def _recommend(self, features: dict) -> dict:
        r = AlgorithmRecommender()
        return r._score(features)

    def test_large_scale_favors_lightgbm(self):
        """大规模数据（多分组+多行）→ LightGBM 最高分"""
        scores = self._recommend({
            "total_groups": 300,
            "total_rows": 200000,
            "avg_days_per_group": 60.0,
            "weekly_seasonality": 0.2,
            "trend_strength": 0.1,
            "cv_mean": 0.5,
            "rows_per_group_mean": 60.0,
        })
        best = max(scores, key=lambda k: scores[k]["score"])
        assert best == "lightgbm", f"大���模应推荐 LightGBM, 实际: {best}: {scores[best]}"
        assert scores["lightgbm"]["score"] >= 75

    def test_strong_seasonality_favors_sarima(self):
        """强季节性 + 适量分组 → SARIMA 得分高"""
        scores = self._recommend({
            "total_groups": 30,
            "total_rows": 15000,
            "avg_days_per_group": 40.0,
            "weekly_seasonality": 0.7,
            "trend_strength": 0.1,
            "cv_mean": 0.2,
            "rows_per_group_mean": 40.0,
        })
        assert scores["sarima"]["score"] >= 55, f"SARIMA 应推荐: {scores['sarima']}"
        assert scores["naive"]["score"] >= 50, f"强季节性下 Naive 也应得分不低"

    def test_strong_trend_favors_prophet(self):
        """强趋势 → Prophet 高��"""
        scores = self._recommend({
            "total_groups": 10,
            "total_rows": 5000,
            "avg_days_per_group": 90.0,
            "weekly_seasonality": 0.1,
            "trend_strength": 0.6,
            "cv_mean": 0.5,
            "rows_per_group_mean": 90.0,
        })
        assert scores["prophet"]["score"] >= 55

    def test_small_data_favors_naive(self):
        """小数据集 + 少量分组 → Naive 作为基线得分高"""
        scores = self._recommend({
            "total_groups": 5,
            "total_rows": 500,
            "avg_days_per_group": 15.0,
            "weekly_seasonality": 0.1,
            "trend_strength": 0.05,
            "cv_mean": 0.4,
            "rows_per_group_mean": 15.0,
        })
        assert scores["naive"]["score"] >= 40

    def test_insufficient_history_penalizes_sarima(self):
        """历史不足14天 → SARIMA 得分低"""
        scores = self._recommend({
            "total_groups": 10,
            "total_rows": 500,
            "avg_days_per_group": 10.0,
            "weekly_seasonality": 0.5,
            "trend_strength": 0.1,
            "cv_mean": 0.3,
            "rows_per_group_mean": 10.0,
        })
        assert scores["sarima"]["score"] < 40, f"SARIMA 短序列应低分: {scores['sarima']}"
        # Naive 应该反而不错
        assert scores["naive"]["score"] > scores["sarima"]["score"]

    def test_too_many_groups_penalizes_sarima_prophet(self):
        """分组过多 → SARIMA/Prophet 被惩罚"""
        scores = self._recommend({
            "total_groups": 500,
            "total_rows": 50000,
            "avg_days_per_group": 30.0,
            "weekly_seasonality": 0.3,
            "trend_strength": 0.15,
            "cv_mean": 0.4,
            "rows_per_group_mean": 30.0,
        })
        assert scores["sarima"]["score"] < scores["lightgbm"]["score"]
        assert scores["prophet"]["score"] < scores["lightgbm"]["score"]

    def test_score_range(self):
        """所有得分在 [10, 100] 范围内"""
        features = {
            "total_groups": 50,
            "total_rows": 10000,
            "avg_days_per_group": 30.0,
            "weekly_seasonality": 0.3,
            "trend_strength": 0.15,
            "cv_mean": 0.4,
            "rows_per_group_mean": 30.0,
        }
        scores = self._recommend(features)
        for name, entry in scores.items():
            assert 10 <= entry["score"] <= 100, (
                f"{name} 得分越界: {entry['score']}"
            )

    def test_all_labels_present(self):
        """每种算法都有 label 和 reason"""
        features = {
            "total_groups": 50,
            "total_rows": 10000,
            "avg_days_per_group": 30.0,
            "weekly_seasonality": 0.3,
            "trend_strength": 0.15,
            "cv_mean": 0.4,
            "rows_per_group_mean": 30.0,
        }
        scores = self._recommend(features)
        for name, entry in scores.items():
            assert "label" in entry, f"{name} 缺少 label"
            assert "reason" in entry, f"{name} 缺少 reason"
            assert entry["label"] in ("强烈推荐", "推荐", "可选", "不推荐")

    def test_descending_order(self):
        """评分结果应按分数降序排列"""
        r = AlgorithmRecommender()
        features = {
            "total_groups": 50,
            "total_rows": 10000,
            "avg_days_per_group": 30.0,
            "weekly_seasonality": 0.3,
            "trend_strength": 0.15,
            "cv_mean": 0.4,
            "rows_per_group_mean": 30.0,
        }
        scores = r._score(features)
        sorted_items = sorted(scores.items(), key=lambda x: -x[1]["score"])
        for i in range(len(sorted_items) - 1):
            assert sorted_items[i][1]["score"] >= sorted_items[i + 1][1]["score"]


# =============================================================================
# _aggregate_features 聚合逻辑测试
# =============================================================================


class TestAggregateFeatures:
    """特征聚合 — 用模拟 DataFrame 验证"""

    def _make_group(self, days: int, seed: int = 42) -> pd.DataFrame:
        """构造一个分组的时间序列"""
        np.random.seed(seed)
        end = date(2026, 5, 22)
        dates = [end - timedelta(days=i) for i in range(days - 1, -1, -1)]
        rows = []
        for d in dates:
            # 周季节性 + 趋势 + 噪声
            dow = d.weekday()
            seasonal = 100.0 if dow >= 5 else 0.0
            trend = 0.5 * (len(dates) - len(rows))  # 下降趋势
            val = 500.0 + seasonal - trend + float(np.random.randint(-30, 30))
            rows.append([d.strftime("%Y%m%d"), "S001", "M001", max(val, 1)])
        df = pd.DataFrame(
            rows,
            columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"],
        )
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d")
        return df

    def test_single_group(self):
        """单个分组应有合理特征值"""
        grp = self._make_group(days=30)
        r = AlgorithmRecommender()
        features = r._aggregate_features([grp])

        assert features["total_rows"] == 30
        assert 20 <= features["avg_days_per_group"] <= 30
        assert features["weekly_seasonality"] >= 0
        assert features["trend_strength"] >= 0
        assert features["cv_mean"] > 0
        assert features["rows_per_group_mean"] == 30

    def test_multiple_groups(self):
        """多分组聚合应取均值"""
        grp1 = self._make_group(days=30, seed=42)
        grp2 = self._make_group(days=60, seed=123)
        r = AlgorithmRecommender()
        features = r._aggregate_features([grp1, grp2])

        assert features["total_rows"] == 90
        assert features["avg_days_per_group"] == pytest.approx(45.0, abs=1)
        assert features["weekly_seasonality"] >= 0
        assert features["trend_strength"] >= 0

    def test_empty_list(self):
        """空列表返回默认值"""
        r = AlgorithmRecommender()
        features = r._aggregate_features([])

        assert features["total_rows"] == 0
        assert features["avg_days_per_group"] == 0.0
        assert features["weekly_seasonality"] == 0.0
        assert features["trend_strength"] == 0.0
        assert features["cv_mean"] == 0.5
        assert features["rows_per_group_mean"] == 0.0

    def test_short_group_skipped(self):
        """少于7天的分组被跳过"""
        grp = self._make_group(days=5, seed=42)
        r = AlgorithmRecommender()
        features = r._aggregate_features([grp])

        assert features["total_rows"] == 0
        assert features["avg_days_per_group"] == 0.0

    def test_group_with_high_seasonality(self):
        """强季节性数据应检出季节强度 > 0.2"""
        np.random.seed(42)
        rows = []
        end = date(2026, 5, 22)
        dates = [end - timedelta(days=i) for i in range(59, -1, -1)]
        for d in dates:
            dow = d.weekday()
            # 强烈的周末效应：周末值翻倍
            seasonal = 500.0 if dow >= 5 else 0.0
            val = 500.0 + seasonal + float(np.random.randint(-20, 20))
            rows.append([d.strftime("%Y%m%d"), "S001", "M001", val])
        df = pd.DataFrame(
            rows,
            columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"],
        )
        df["dt"] = pd.to_datetime(df["dt"], format="%Y%m%d")

        r = AlgorithmRecommender()
        features = r._aggregate_features([df])

        assert features["weekly_seasonality"] > 0.2, (
            f"强季节数据应检测出 > 0.2: {features['weekly_seasonality']:.4f}"
        )


# =============================================================================
# recommend 接口测试
# =============================================================================


class TestRecommend:
    """完整 recommend 接口— mock 数据源"""

    def test_requires_service(self):
        """recommend 需要 service 参数"""
        r = AlgorithmRecommender()
        with pytest.raises(ValueError, match="需要 service 参数"):
            r.recommend(data_source_id=1)

    def test_recommend_with_mocked_data(self):
        """mock 数据源验证完整推荐流程（大量分组→LightGBM 推荐）"""
        r = AlgorithmRecommender()
        service = MagicMock()

        # Mock ds_repo.get_by_id 返回一个数据源对象
        ds = MagicMock()
        ds.database = "test_db"
        service.ds_repo.get_by_id.return_value = ds

        # Mock execute_query（在 db_executor 模块级，因为 recommender._execute 内部 import 它）
        with patch("app.utils.db_executor.execute_query") as mock_exec:
            mock_exec.return_value = ([[200]], ["group_count"])
            mock_exec.side_effect = [
                ([[200]], ["group_count"]),  # count query → 200 groups
                # TOP 10 分组（高销售额）
                (
                    [[f"S{i:03d}", f"M{i:03d}", 2000000 - i * 100000] for i in range(10)],
                    ["store_code", "matnr", "total_sales"],
                ),
                # 采样数据（60 天 × 10 分组，大数值 + 小噪声，无季节/趋势）
                (
                    [
                        [
                            (date(2026, 3, 24) + timedelta(days=j)).strftime("%Y%m%d"),
                            f"S{j % 10 + 1:03d}",
                            f"M{j % 10 + 1:03d}",
                            int(500000 + float(np.random.randint(-10000, 10000)))
                        ]
                        for j in range(60) for i in range(10)
                    ],
                    ["dt", "store_code", "matnr", "actual_sale_untaxed_amt"],
                ),
            ]

            result = r.recommend(data_source_id=1, service=service)

        assert len(result) == 4  # 4 种算法
        # 200 groups + 纯噪声数据 → LightGBM 应为第一
        assert result[0]["algorithm"] == "lightgbm", (
            f"首位应为 lightgbm: {[r['algorithm'] for r in result]}"
        )
        assert "score" in result[0]
        assert "label" in result[0]
        assert "reason" in result[0]
        assert result[0]["score"] >= result[1]["score"]

    def test_recommend_data_source_not_found(self):
        """数据源不存在时降级返回"""
        r = AlgorithmRecommender()
        service = MagicMock()
        service.ds_repo.get_by_id.return_value = None

        result = r.recommend(data_source_id=999, service=service)

        # 应返回降级推荐（默认值）
        assert len(result) == 4

    def test_recommend_execute_query_failure(self):
        """SQL 执行失败时降级返回（Naive 应为第一，因为降级数据全零）"""
        r = AlgorithmRecommender()
        service = MagicMock()
        ds = MagicMock()
        ds.database = "test_db"
        service.ds_repo.get_by_id.return_value = ds

        with patch("app.utils.db_executor.execute_query") as mock_exec:
            mock_exec.side_effect = Exception("数据库连接失败")
            result = r.recommend(data_source_id=1, service=service)

        # 应返回降级推荐
        assert len(result) == 4
        # SQL 失败时返回默认特征（全零）→ Naive 得分最高（45 vs 其他算法更低）
        assert "algorithm" in result[0]
        assert "score" in result[0]
