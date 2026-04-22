#!/bin/bash
# 启动 Celery Worker

# 设置Python路径
export PYTHONPATH=/home/zhou/myreport/backend:$PYTHONPATH

# 启动Celery worker
cd /home/zhou/myreport/backend
celery -A celery_config worker --loglevel=info --concurrency=4 -Q export
