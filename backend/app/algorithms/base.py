"""预测算法基类 — 所有算法实现此接口"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from app.models.prediction import PredictionResult


class BasePredictor:
    """预测算法抽象接口

    每个算法实现 train / predict / save / load 四个方法。
    """

    MODEL_TYPE: str = ""  # 子类覆盖：如 "lightgbm", "prophet"

    def train(
        self,
        df: pd.DataFrame,
        model_record: Any,
        service: Any,
        **kwargs,
    ) -> Tuple[Any, Dict[str, Any]]:
        """训练模型

        Args:
            df: 历史销售数据 (列: dt, store_code, matnr, actual_sale_untaxed_amt)
            model_record: PredictionModel ORM 对象
            service: PredictionService 实例（可访问 db, repos, model_dir 等）
            **kwargs: 算法特有参数

        Returns:
            (model, metrics) — model 是任意可序列化对象，metrics 是 dict
                           metrics 必须包含 "mae", "rmse" 用于 model_metrics
        """
        raise NotImplementedError

    def predict(
        self,
        model: Any,
        model_record: Any,
        df: pd.DataFrame,
        forecast_days: int,
        service: Any,
        **kwargs,
    ) -> List[PredictionResult]:
        """用已训练模型预测未来 N 天

        Args:
            model: train() 返回的模型对象
            model_record: PredictionModel ORM 对象
            df: 最新历史数据用于特征构造
            forecast_days: 预测天数
            service: PredictionService 实例
            **kwargs: 算法特有参数

        Returns:
            List[PredictionResult] — 每个元素包含 predicted_value, lower_bound, upper_bound
        """
        raise NotImplementedError

    def save(self, model: Any, model_path: str) -> None:
        """将模型序列化到磁盘"""
        raise NotImplementedError

    def load(self, model_path: str) -> Any:
        """从磁盘加载模型"""
        raise NotImplementedError
