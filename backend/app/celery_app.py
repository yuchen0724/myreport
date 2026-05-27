# backend/app/celery_app.py
from celery import Celery
from celery.schedules import crontab
import os

def create_celery_app():
    """创建 Celery 应用实例"""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    celery = Celery(
        'myreport',
        broker=redis_url,
        backend=redis_url,
    )

    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Shanghai',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,
        task_soft_time_limit=25 * 60,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        beat_schedule={
            "weekly-retrain-prediction": {
                "task": "app.tasks.prediction_tasks.train_prediction_model",
                "schedule": crontab(hour=2, minute=0),
                "args": (1,),
                "kwargs": {"train_days": 365},
            },
        },
    )

    return celery

celery_app = create_celery_app()

# 导入任务模块以向该 celery_app 注册任务
from app.tasks import export_tasks  # noqa: E402, F401
from app.tasks import prediction_tasks  # noqa: E402, F401
from app.tasks import subscription_tasks  # noqa: E402, F401
