# backend/app/celery_app.py
from celery import Celery
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
    )

    return celery

celery_app = create_celery_app()
