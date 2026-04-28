# backend/celery_config.py
# 委托给 app.celery_app，确保 Worker 与任务注册使用同一 Celery 实例
from app.celery_app import celery_app

# 供 `celery -A celery_config worker` 使用
__all__ = ["celery_app"]
