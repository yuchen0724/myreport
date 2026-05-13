"""预测相关 Celery 后台任务"""

import logging
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=600)
def train_prediction_model(self, data_source_id: int, train_days: int = 365):
    """定时训练预测模型"""
    logger.info(f"[Celery] 开始训练预测模型: data_source_id={data_source_id}")
    db = SessionLocal()
    try:
        service = PredictionService(db)
        model_id = service.train(data_source_id, train_days)
        logger.info(f"[Celery] 训练完成: model_id={model_id}")
        return {"model_id": model_id, "status": "success"}
    except Exception as e:
        logger.error(f"[Celery] 训练失败: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()
