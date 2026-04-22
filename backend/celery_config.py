# backend/celery_config.py
from celery import Celery
import os

# Redis 配置
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# 创建 Celery 应用
celery_app = Celery(
    'myreport',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks.export_tasks']
)

# 配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟超时
    task_soft_time_limit=25 * 60,  # 25分钟软超时
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# 任务路由
celery_app.conf.task_routes = {
    'app.tasks.export_tasks.*': {'queue': 'export'},
}

# 自动发现任务
celery_app.autodiscover_tasks(['app.tasks'])
