# Celery Worker 启动指南

## 前置条件

1. 确保Redis服务正在运行：
```bash
redis-server --daemonize yes
```

2. 检查Redis状态：
```bash
redis-cli ping
# 应该返回 PONG
```

## 启动Celery Worker

### 方法1：使用启动脚本（推荐）

```bash
cd /home/zhou/myreport/backend
./start_celery.sh
```

### 方法2：手动启动

```bash
cd /home/zhou/myreport/backend
export PYTHONPATH=/home/zhou/myreport/backend:$PYTHONPATH
celery -A celery_config worker --loglevel=info --concurrency=4 -Q export
```

## 验证Celery Worker

检查已注册的任务：
```bash
cd /home/zhou/myreport/backend
export PYTHONPATH=/home/zhou/myreport/backend:$PYTHONPATH
celery -A celery_config inspect registered
```

应该看到：
```
* app.tasks.export_tasks.export_excel_async
* app.tasks.export_tasks.export_pdf_async
```

检查活跃任务：
```bash
celery -A celery_config inspect active
```

## 常见问题

### 1. ModuleNotFoundError: No module named 'app'

确保设置了PYTHONPATH环境变量：
```bash
export PYTHONPATH=/home/zhou/myreport/backend:$PYTHONPATH
```

### 2. Connection refused (Redis)

确保Redis服务正在运行：
```bash
redis-server --daemonize yes
```

### 3. 任务没有注册

确保celery_config.py中导入了任务模块：
```python
# 导入任务模块以注册任务
try:
    from app.tasks import export_tasks
except ImportError:
    pass
```

## 后台运行

如果需要在后台运行Celery worker：

```bash
cd /home/zhou/myreport/backend
export PYTHONPATH=/home/zhou/myreport/backend:$PYTHONPATH
celery -A celery_config worker --loglevel=info --concurrency=4 -Q export &
```

或者使用nohup：
```bash
cd /home/zhou/myreport/backend
export PYTHONPATH=/home/zhou/myreport/backend:$PYTHONPATH
nohup celery -A celery_config worker --loglevel=info --concurrency=4 -Q export > celery.log 2>&1 &
```

## 停止Celery Worker

```bash
pkill -f "celery.*worker"
```

或者使用Ctrl+C（如果在前台运行）
