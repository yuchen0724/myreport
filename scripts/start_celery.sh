#!/bin/bash
# scripts/start_celery.sh

cd /home/zhou/myreport/backend

# 设置 PYTHONPATH
export PYTHONPATH=/home/zhou/myreport/backend:$PYTHONPATH

# 启动 Celery Worker
celery -A celery_config worker --loglevel=info --concurrency=4
