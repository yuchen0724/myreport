"""特征工程模块 - 为销售预测提取时序特征"""

import pandas as pd
import numpy as np
from typing import List


def build_features_from_history(df: pd.DataFrame, target_col: str = "actual_sale_untaxed_amt") -> pd.DataFrame:
    """
    从历史销售数据中提取特征。
    
    输入 df 必须包含列: dt, store_code, matnr, actual_sale_untaxed_amt (或其他指标)
    输出 df 包含原始列 + 特征列。
    """
    features = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(features["dt"]):
        features["dt"] = pd.to_datetime(features["dt"], format="%Y%m%d", errors="coerce")
    
    # 时间特征
    features["day_of_week"] = features["dt"].dt.dayofweek
    features["day_of_month"] = features["dt"].dt.day
    features["month"] = features["dt"].dt.month
    features["quarter"] = features["dt"].dt.quarter
    features["is_weekend"] = features["day_of_week"].isin([5, 6]).astype(int)
    features["is_month_start"] = (features["dt"].dt.day <= 3).astype(int)
    features["is_month_end"] = (features["dt"].dt.day >= 28).astype(int)
    
    # 按门店-商品分组排序
    features = features.sort_values(["store_code", "matnr", "dt"]).reset_index(drop=True)
    
    # 滞后特征（前 N 天）
    for lag in [1, 2, 3, 7, 14, 28]:
        features[f"lag_{lag}"] = (
            features.groupby(["store_code", "matnr"])[target_col]
            .shift(lag)
        )
    
    # 滚动窗口统计
    for window in [3, 7, 14]:
        roll = (
            features.groupby(["store_code", "matnr"])[target_col]
            .transform(lambda x: x.rolling(window, min_periods=1).mean())
        )
        features[f"rolling_mean_{window}"] = roll
        roll_std = (
            features.groupby(["store_code", "matnr"])[target_col]
            .transform(lambda x: x.rolling(window, min_periods=1).std())
        )
        features[f"rolling_std_{window}"] = roll_std.fillna(0)
    
    # 同比/环比特征
    features["diff_1d"] = features[target_col] - features["lag_1"]
    features["diff_7d"] = features[target_col] - features["lag_7"]
    features["pct_change_1d"] = features["diff_1d"] / (features["lag_1"] + 1e-6)
    features["pct_change_7d"] = features["diff_7d"] / (features["lag_7"] + 1e-6)
    
    # 过去7天均值占比（近期趋势）
    features["recent_ratio"] = features["lag_1"] / (features["rolling_mean_7"] + 1e-6)
    
    # 是否上周同日
    features["same_dow_last_week"] = features.groupby(["store_code", "matnr"])[target_col].shift(7)
    
    return features


def get_feature_columns() -> List[str]:
    """返回特征列名列表（排除 ID 列、目标列、日期列）"""
    return [
        "day_of_week", "day_of_month", "month", "quarter",
        "is_weekend", "is_month_start", "is_month_end",
        "lag_1", "lag_2", "lag_3", "lag_7", "lag_14", "lag_28",
        "rolling_mean_3", "rolling_mean_7", "rolling_mean_14",
        "rolling_std_3", "rolling_std_7", "rolling_std_14",
        "diff_1d", "diff_7d", "pct_change_1d", "pct_change_7d",
        "recent_ratio", "same_dow_last_week",
    ]
