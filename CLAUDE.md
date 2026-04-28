# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

自定义报表查询系统（Custom Report System）— 支持 SQL 模板管理、参数化查询、数据导出(Excel/PDF)和可视化展示的 Full-Stack 应用。

## 技术栈

- **前端**: Vue 3 (Composition API) + Element Plus + Pinia + Vue Router + Vite + Axios
- **后端**: FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery
- **数据仓库**: Apache Doris / Hive
- **开发工具**: Alembic, Pytest, Uvicorn
- **部署**: Docker Compose (Nginx 反向代理)

## 架构分层

```
frontend/src/          后端 backend/app/
├── views/             ├── api/          # API 路由层
├── components/        ├── services/     # 业务逻辑层
├── store/             ├── repositories/ # 数据访问层(Repository)
├── router/            ├── models/       # SQLAlchemy 数据模型
├── api/               ├── schemas/      # Pydantic 请求/响应模型
└── utils/             ├── middleware/   # 限流/审计/错误处理中间件
                       ├── core/         # 数据库/认证/安全/Redis
                       ├── tasks/        # Celery 异步任务
                       └── utils/        # SQL验证/查询优化/PDF生成
```

### 关键设计决策

- **Repository 模式**: `repositories/` 封装所有数据库查询，`services/` 调用 repositories 完成业务逻辑
- **JWT 认证**: `core/auth_deps.py` 提供 `get_current_user_id` / `get_current_user` 作为 FastAPI Depends
- **服务层模式**: API 路由不直接访问数据库，通过 Service 类中转
- **异步导出**: Celery + Redis Broker 处理长时间运行的导出任务，前端轮询任务状态

## 开发命令

### 后端
```bash
# 安装依赖
pip install -r backend/requirements.txt

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 运行所有测试
cd backend && pytest

# 运行单个测试文件
pytest tests/test_template_api.py

# 运行单个测试用例
pytest tests/test_template_api.py::test_create_template

# 生成覆盖率报告
pytest --cov=app --cov-report=html

# 数据库迁移
alembic upgrade head
alembic revision --autogenerate -m "description"

# 启动 Celery Worker
celery -A celery_config worker --loglevel=info --concurrency=4 -Q export
```

### 前端
```bash
cd frontend
npm install
npm run dev      # 开发服务器 :3000
npm run build    # 生产构建
```

### 一键启动
```bash
./start.sh start     # 启动所有服务 (Redis → Celery → 后端 → 前端)
./start.sh stop      # 停止所有服务
./start.sh status    # 查看服务状态
./start.sh logs backend  # 查看指定服务日志
```

### Docker
```bash
docker-compose up -d          # 启动所有容器
docker-compose logs -f        # 查看日志
```

## 项目结构关键路径

- **配置文件**: `backend/app/config.py`（从 `.env` 读取）
- **API 入口**: `backend/app/main.py`（注册路由、中间件）
- **模型基类**: `backend/app/core/database.py`（`Base` + `get_db`）
- **认证依赖**: `backend/app/core/auth_deps.py`
- **安全工具**: `backend/app/core/security.py`（密码哈希、JWT、Fernet 加密）
- **限流中间件**: `backend/app/middleware/rate_limit.py`（基于内存 IP 限流，可配置开关）
- **审计日志中间件**: `backend/app/middleware/audit_log.py`（自动记录 API 调用）
- **异常定义**: `backend/app/exceptions.py`（分层异常体系）

## API 路由前缀

| 路由 | 模块 | 说明 |
|------|------|------|
| `/api/auth` | `auth.py` | 登录/用户信息 |
| `/api/templates` | `templates.py` | SQL 模板 CRUD + 分享 + 版本回滚 |
| `/api/query` | `query.py` | SQL 查询执行 + 历史记录 |
| `/api/data-sources` | `data_sources.py` | 数据源管理 |
| `/api/nl2sql` | `nl2sql.py` | 自然语言转 SQL |
| `/api/charts` | `charts.py` | 图表数据 |
| `/api/reports` | `report.py` | 报表生成(Excel/PDF) |
| `/api/async-export` | `async_export.py` | 异步导出任务 |
| `/api/users` | `users.py` | 用户管理 |
| `/api/cache` | `cache.py` | 缓存管理 |
| `/api/audit-logs` | `audit_logs.py` | 审计日志查看 |
| `/api/stats` | `stats.py` | 统计信息 |

## 关键数据模型

- **User** (`users`): JWT 认证, RBAC 通过 role_id 关联 Role
- **Template** (`templates`): SQL 模板, JSON config, 版本号, 分享机制
- **TemplateVersion** (`template_versions`): 版本历史, 支持回滚
- **TemplateShare** (`template_shares`): 模板分享记录
- **DataSource** (`data_sources`): 数据库连接配置, 密码用 Fernet 加密存储
- **ExportTask** (`export_tasks`): Celery 异步导出任务状态跟踪
- **QueryHistory** (`query_histories`): 用户查询历史

## 测试约定

- 测试使用 SQLite 内存数据库（`conftest.py` 中配置）
- 每个测试函数独立的 `db_session` fixture（自动创建/销毁表）
- `client` fixture 提供 `TestClient`，`auth_headers` fixture 提供 JWT token
- 测试文件: `test_auth_api.py`, `test_template_api.py`, `test_query_api.py`, `test_api_integration.py` 等
