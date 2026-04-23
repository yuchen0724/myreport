# 自定义报表查询系统 - 快速启动指南

## 一键启动脚本

项目提供了 `start.sh` 一键启动脚本，可以方便地管理所有服务。

### 使用方法

```bash
# 启动所有服务
./start.sh start

# 停止所有服务
./start.sh stop

# 重启所有服务
./start.sh restart

# 查看服务状态
./start.sh status

# 查看日志
./start.sh logs [redis|celery|backend|frontend]
```

### 服务说明

启动脚本会按顺序启动以下服务：

1. **Redis** (端口: 6379) - 缓存和消息队列
2. **Celery Worker** - 异步任务处理
3. **后端服务** (端口: 8000) - FastAPI 服务
4. **前端服务** (端口: 3000) - Vue 3 开发服务器

### 访问地址

- 前端界面: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 日志文件

所有服务的日志都保存在 `logs/` 目录下：

- `logs/redis.log` - Redis 日志
- `logs/celery.log` - Celery Worker 日志
- `logs/backend.log` - 后端服务日志
- `logs/frontend.log` - 前端服务日志

### 故障排查

如果服务启动失败，可以：

1. 查看服务状态：`./start.sh status`
2. 查看对应服务的日志：`./start.sh logs backend`
3. 检查端口是否被占用：`lsof -i :8000`
4. 停止所有服务后重新启动：`./start.sh restart`

### 手动启动（可选）

如果需要单独启动某个服务，可以使用以下命令：

```bash
# Redis
redis-server --daemonize yes --port 6379 --logfile logs/redis.log

# Celery Worker
cd backend
celery -A celery_config worker --loglevel=info --concurrency=4 -Q export

# 后端服务
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端服务
cd frontend
npm run dev
```

## 系统要求

- Node.js 16+
- Python 3.9+
- Redis 6+
- PostgreSQL 12+

## 首次运行

1. 安装后端依赖：
```bash
cd backend
pip install -r requirements.txt
```

2. 安装前端依赖：
```bash
cd frontend
npm install
```

3. 配置数据库连接（修改 `backend/.env` 文件）

4. 启动服务：
```bash
./start.sh start
```

## 开发模式

在开发模式下，后端和前端都会启用热重载，修改代码后会自动重启服务。

## 生产部署

生产环境建议使用：

- 使用 Gunicorn + Uvicorn 部署后端
- 使用 Nginx 反向代理
- 使用 PM2 或 Systemd 管理进程
- 配置 HTTPS 证书
