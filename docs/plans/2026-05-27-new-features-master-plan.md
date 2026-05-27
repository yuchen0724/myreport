# 自定义报表查询系统 - 新功能实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development 或 executing-plans 逐任务实现此计划。

**目标：** 为自定义报表查询系统添加8个新功能，提升业务价值和技术架构

**架构：** 基于现有 FastAPI + Vue3 + PostgreSQL + Redis + Celery 架构，按优先级分3个阶段实现

**技术栈：** Python 3.12, FastAPI, SQLAlchemy, Vue 3, Element Plus, Celery, Redis, LangChain

---

## 功能概览

| 阶段 | 功能 | 复杂度 | 预计工时 |
|------|------|--------|----------|
| P0 | 1. 查询结果订阅推送 | 中 | 2天 |
| P0 | 2. 仪表盘钻取 | 中 | 2天 |
| P0 | 3. 查询收藏夹 | 低 | 1天 |
| P1 | 4. SQL 审核工作流 | 高 | 3天 |
| P1 | 5. 数据源连接池监控 | 中 | 2天 |
| P1 | 6. 多语言 SQL 方言适配 | 中 | 2天 |
| P2 | 7. AI 数据分析师 | 高 | 4天 |
| P2 | 8. 移动端适配 | 中 | 2天 |

---

## 阶段 P0：核心业务增强（5天）

### 功能 1：查询结果订阅推送

**文件结构：**
- 创建：`backend/app/models/subscription.py`
- 创建：`backend/app/schemas/subscription.py`
- 创建：`backend/app/repositories/subscription_repository.py`
- 创建：`backend/app/services/subscription_service.py`
- 创建：`backend/app/tasks/subscription_tasks.py`
- 创建：`backend/app/api/subscriptions.py`
- 创建：`frontend/src/views/SubscriptionList.vue`
- 修改：`backend/app/main.py`（注册路由）
- 修改：`frontend/src/router/index.js`（添加路由）

### 功能 2：仪表盘钻取

**文件结构：**
- 创建：`backend/app/schemas/drilldown.py`
- 创建：`backend/app/services/drilldown_service.py`
- 创建：`backend/app/api/drilldown.py`
- 创建：`frontend/src/components/DrilldownPanel.vue`
- 修改：`frontend/src/components/DashboardWidget.vue`（添加点击事件）
- 修改：`backend/app/main.py`（注册路由）

### 功能 3：查询收藏夹

**文件结构：**
- 创建：`backend/app/models/user_favorite.py`
- 创建：`backend/app/schemas/favorite.py`
- 创建：`backend/app/repositories/favorite_repository.py`
- 创建：`backend/app/services/favorite_service.py`
- 创建：`backend/app/api/favorites.py`
- 创建：`frontend/src/views/FavoriteList.vue`
- 修改：`backend/app/main.py`（注册路由）
- 修改：`frontend/src/router/index.js`（添加路由）

---

## 阶段 P1：架构演进（7天）

### 功能 4：SQL 审核工作流

**文件结构：**
- 创建：`backend/app/models/sql_review.py`
- 创建：`backend/app/schemas/review.py`
- 创建：`backend/app/repositories/review_repository.py`
- 创建：`backend/app/services/review_service.py`
- 创建：`backend/app/tasks/review_tasks.py`
- 创建：`backend/app/api/reviews.py`
- 创建：`frontend/src/views/ReviewList.vue`
- 创建：`frontend/src/components/ReviewDetail.vue`
- 修改：`backend/app/main.py`（注册路由）

### 功能 5：数据源连接池监控

**文件结构：**
- 创建：`backend/app/utils/pool_monitor.py`
- 创建：`backend/app/schemas/metrics.py`
- 创建：`backend/app/api/metrics.py`
- 创建：`frontend/src/views/PoolMonitor.vue`
- 修改：`backend/app/main.py`（注册路由）

### 功能 6：多语言 SQL 方言适配

**文件结构：**
- 创建：`backend/app/utils/sql_dialect.py`
- 创建：`backend/app/schemas/dialect.py`
- 创建：`backend/app/api/dialects.py`
- 创建：`frontend/src/components/SqlDialectSelector.vue`
- 修改：`backend/app/main.py`（注册路由）

---

## 阶段 P2：智能化与移动端（8天）

### 功能 7：AI 数据分析师

**文件结构：**
- 创建：`backend/app/services/ai_analyst_service.py`
- 创建：`backend/app/api/ai_analyst.py`
- 创建：`backend/app/tools/`（Agent 工具集）
- 创建：`frontend/src/views/AiAnalyst.vue`
- 修改：`backend/app/main.py`（注册路由）

### 功能 8：移动端适配

**文件结构：**
- 创建：`frontend/src/views/mobile/`（移动视图）
- 创建：`frontend/src/composables/useMobile.js`
- 修改：`frontend/src/App.vue`（响应式布局）
- 修改：`frontend/src/router/index.js`（移动端路由）

---

## 执行策略

**推荐方式：** 子代理驱动开发

每个功能作为独立任务，使用 delegate_task 并行执行：
1. 功能 1-3 可并行（无依赖）
2. 功能 4-6 可并行（无依赖）
3. 功能 7-8 可并行（无依赖）

**验证方式：**
- 后端：pytest 单元测试 + API 集成测试
- 前端：npm run build 构建验证 + 手动测试
- 整体：./start.sh status 服务状态检查
