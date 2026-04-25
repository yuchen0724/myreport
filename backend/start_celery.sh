#!/bin/bash
# 启动 Celery Worker（统一使用 app.celery_app）

# 设置Python路径
export PYTHONPATH=/home/zhou/myreport/backend:$PYTHONPATH

# 加载 .env 环境变量（若未加载）
set -a
source .env 2>/dev/null || true
set +a

# 启动Celery worker
cd /home/zhou/myreport/backend
celery -A app.celery_app worker --loglevel=info --concurrency=4
