# 自定义报表查询系统 - 第一阶段（MVP）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建自定义报表查询系统的 MVP 版本，支持用户认证与权限、数据源管理、SQL 查询、Excel 导出。

**架构：** Python FastAPI 单体架构，使用 SQLAlchemy ORM，PostgreSQL 存储业务数据，Redis 缓存查询结果。

**技术栈：** FastAPI、SQLAlchemy、PostgreSQL、Redis、openpyxl、PyJWT、passlib、pytest。

---

## 任务分解

### 任务 1：项目初始化

- [ ] 创建 `backend/requirements.txt`
- [ ] 创建 `backend/.env.example`
- [ ] 创建 `backend/app/__init__.py`
- [ ] 创建 `backend/app/main.py`
- [ ] 创建 `backend/app/config.py`
- [ ] 创建 `backend/README.md`

### 任务 2：数据库连接与模型

- [ ] 创建 `backend/app/core/__init__.py`
- [ ] 创建 `backend/app/core/database.py`
- [ ] 创建 `backend/app/core/redis.py`
- [ ] 创建 `backend/app/models/__init__.py`
- [ ] 创建 `backend/app/models/user.py`
- [ ] 创建 `backend/app/models/role.py`
- [ ] 创建 `backend/app/models/permission.py`
- [ ] 创建 `backend/app/models/data_source.py`
- [ ] 创建 `backend/app/models/query_history.py`
- [ ] 创建 `backend/app/models/export_task.py`

### 任务 3：安全模块（JWT 和密码加密）

- [ ] 创建 `backend/app/core/security.py`

### 任务 4：用户认证 API

- [ ] 创建 `backend/app/schemas/__init__.py`
- [ ] 创建 `backend/app/schemas/user.py`
- [ ] 创建 `backend/app/schemas/auth.py`
- [ ] 创建 `backend/app/repositories/__init__.py`
- [ ] 创建 `backend/app/repositories/user_repository.py`
- [ ] 创建 `backend/app/services/__init__.py`
- [ ] 创建 `backend/app/services/auth_service.py`
- [ ] 创建 `backend/app/api/__init__.py`
- [ ] 创建 `backend/app/api/auth.py`
- [ ] 修改 `backend/app/main.py` 添加认证路由

### 任务 5：数据源管理 API

- [ ] 创建 `backend/app/schemas/data_source.py`
- [ ] 创建 `backend/app/repositories/data_source_repository.py`
- [ ] 创建 `backend/app/services/data_source_service.py`
- [ ] 创建 `backend/app/api/data_sources.py`
- [ ] 修改 `backend/app/main.py` 添加数据源路由

### 任务 6：SQL 查询 API

- [ ] 创建 `backend/app/schemas/query.py`
- [ ] 创建 `backend/app/repositories/query_history_repository.py`
- [ ] 创建 `backend/app/services/query_service.py`
- [ ] 创建 `backend/app/api/query.py`
- [ ] 创建 `backend/app/utils/__init__.py`
- [ ] 创建 `backend/app/utils/sql_validator.py`
- [ ] 修改 `backend/app/main.py` 添加查询路由

### 任务 7：Excel 导出 API

- [ ] 创建 `backend/app/schemas/report.py`
- [ ] 创建 `backend/app/services/report_service.py`
- [ ] 创建 `backend/app/api/report.py`
- [ ] 修改 `backend/app/main.py` 添加报表路由

### 任务 8：数据库迁移

- [ ] 初始化 Alembic
- [ ] 修改 `backend/alembic/env.py`
- [ ] 创建初始迁移
- [ ] 执行迁移

### 任务 9：测试

- [ ] 创建 `backend/tests/__init__.py`
- [ ] 创建 `backend/tests/conftest.py`
- [ ] 创建 `backend/tests/test_auth.py`
- [ ] 创建 `backend/tests/test_data_sources.py`
- [ ] 创建 `backend/tests/test_query.py`
- [ ] 创建 `backend/tests/test_report.py`
- [ ] 运行测试

### 任务 10：前端初始化

- [ ] 创建 `frontend/package.json`
- [ ] 创建 `frontend/vite.config.js`
- [ ] 创建 `frontend/index.html`
- [ ] 创建 `frontend/src/main.js`
- [ ] 创建 `frontend/src/App.vue`
- [ ] 创建 `frontend/src/router/index.js`
- [ ] 创建 `frontend/src/store/index.js`
- [ ] 创建 `frontend/src/utils/request.js`
- [ ] 创建 `frontend/src/utils/auth.js`
- [ ] 创建 `frontend/src/api/auth.js`
- [ ] 创建 `frontend/src/api/data_source.js`
- [ ] 创建 `frontend/src/api/query.js`
- [ ] 创建 `frontend/src/api/report.js`
- [ ] 创建 `frontend/src/views/Login.vue`
- [ ] 创建 `frontend/src/views/Dashboard.vue`
- [ ] 创建 `frontend/src/views/DataSourceList.vue`
- [ ] 创建 `frontend/src/views/DataSourceForm.vue`
- [ ] 创建 `frontend/src/views/QueryEditor.vue`
- [ ] 创建 `frontend/src/views/QueryResult.vue`
- [ ] 创建 `frontend/src/components/Layout.vue`
- [ ] 创建 `frontend/src/components/Header.vue`
- [ ] 创建 `frontend/src/components/Sidebar.vue`
- [ ] 安装前端依赖

---

## 总结

第一阶段（MVP）实现计划已完成，包含以下功能：

1. ✅ 项目初始化
2. ✅ 数据库连接与模型
3. ✅ 安全模块（JWT 和密码加密）
4. ✅ 用户认证 API
5. ✅ 数据源管理 API
6. ✅ SQL 查询 API
7. ✅ Excel 导出 API
8. ✅ 数据库迁移
9. ✅ 测试
10. ✅ 前端初始化

**两种执行方式：**

1. **子代理驱动（推荐）** - 每个任务调度一个新的子代理，任务间进行审查，快速迭代
   - 必需子技能：使用 superpowers:subagent-driven-development

2. **内联执行** - 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点
   - 必需子技能：使用 superpowers:executing-plans

选哪种方式？
