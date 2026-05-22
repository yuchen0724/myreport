"""预测算法注册 — 所有预测器在此导出

注意：Prophet/SARIMA 是可选依赖，导入失败时不阻塞整体加载。
"""

from app.algorithms.base import BasePredictor, MIN_PREDICTION
from app.algorithms.lightgbm_predictor import LightGBMPredictor
from app.algorithms.naive_predictor import NaivePredictor

import logging as _logging
_logger = _logging.getLogger(__name__)

# Prophet（可选依赖）
try:
    from app.algorithms.prophet_predictor import ProphetPredictor
except ImportError:
    ProphetPredictor = None  # type: ignore
    _logger.warning("[算法] ProphetPredictor 不可用（prophet 未安装）")

# SARIMA（可选依赖 statsmodels）
try:
    from app.algorithms.sarima_predictor import SARIMAPredictor
except ImportError:
    SARIMAPredictor = None  # type: ignore
    _logger.warning("[算法] SARIMAPredictor 不可用（statsmodels 未安装）")

__all__ = [
    "BasePredictor",
    "MIN_PREDICTION",
    "LightGBMPredictor",
    "NaivePredictor",
    "ProphetPredictor",
    "SARIMAPredictor",
]

