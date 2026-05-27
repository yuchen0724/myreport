"""RCA 异步分析任务"""
from celery import shared_task
from app.core.database import SessionLocal
from app.services.rca_service import RcaService
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


@shared_task(
    bind=True,
    max_retries=settings.rca_task_max_retries,
    soft_time_limit=settings.rca_task_soft_time_limit,
    time_limit=settings.rca_task_time_limit,
)
def run_rca_analysis(self, task_id: str):
    """异步执行 RCA 分析"""
    db = SessionLocal()
    try:
        svc = RcaService(db)
        result = svc.execute_analysis(task_id)
        logger.info(f"RCA analysis completed: {result}")
        return result
    except Exception as e:
        logger.error(f"RCA analysis failed: {e}", exc_info=True)
        raise
    finally:
        db.close()
