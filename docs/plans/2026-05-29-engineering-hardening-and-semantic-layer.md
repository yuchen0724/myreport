# 工程收口与语义指标层实施计划

**日期**: 2026-05-29

**目标**: 先把项目从“功能快速扩张”切换到“可持续迭代”，完成测试、构建、安全和查询链路收口；随后建设语义指标层，让 NL2SQL、AI 分析师、仪表盘、订阅和 RCA 共享统一业务口径。

**当前基线**:
- 前端 `npm run build` 可通过，但 `element-plus` 与 `echarts` chunk 偏大。
- 前端 `npm run lint` 失败，当前有 21 个 error、97 个 warning。
- 后端 `pytest backend/tests -q` 在导入阶段失败，原因是 `REDIS_URL` 为空时 `redis.from_url(None)`。
- AI/RCA 前端存在多处 `v-html` 简易渲染，需要统一安全清理。
- 查询执行链路集中在 `QueryService._execute_query`，承担连接、SQL 改写、分页、COUNT、重试和缓存，复杂度过高。

---

## 阶段 0：工程收口（2 周）

### 0.1 修复测试与 CI 基线

**目标**: 建立最小可执行质量门禁，避免后续开发继续累积不可验证代码。

**涉及文件**:
- `backend/app/core/redis.py`
- `backend/tests/conftest.py`
- `frontend/eslint.config.js`
- 本地验证脚本或 CI 工作流

**实施步骤**:
1. Redis 初始化兼容 `REDIS_URL` 为空：
   - 优先使用 `settings.redis_url`。
   - 为空时拼接 `redis://{redis_host}:{redis_port}/{redis_db}`。
2. 测试环境显式设置 `REDIS_URL=redis://localhost:6379/15`，并对 Redis 不可用场景提供 mock 或降级。
3. 前端 lint 先区分规则类问题和真实 bug：
   - 对路由页面组件名、多词组件名等低风险规则，选择统一重命名或在配置中明确例外。
   - 对 `vue/no-ref-as-operand`、未使用组件、废弃 `.sync` 等真实问题直接修复。
4. 增加一键验证命令：
   - 后端：`backend/.venv/bin/python -m pytest backend/tests -q`
   - 前端：`npm run lint && npm run build`

**验收标准**:
- 后端测试至少能完成收集并跑完现有测试。
- 前端 lint error 为 0；warning 数量记录在 CI 输出中，后续逐步清零。
- 前端 build 无失败；chunk 警告允许暂时存在但必须登记。

### 0.2 安全收口

**目标**: 修复生产默认密钥、HTML 渲染和敏感配置风险。

**涉及文件**:
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/.env.example`
- `docker-compose.yml`
- `frontend/src/views/AIAnalyst.vue`
- `frontend/src/views/AiAnalyst.vue`
- `frontend/src/views/RcaAnomalies.vue`

**实施步骤**:
1. 统一默认密钥占位符检查：
   - `change-me-in-production-please`
   - `change-this-secret-key-in-production`
   - `change-this-encryption-key-in-production`
2. Docker Compose 中生产敏感值不再提供可上线的默认值，启动失败优于带弱密钥运行。
3. 修正 `PASSWORD_ENCRYPTION_KEY` 文档，明确需要 Fernet 兼容 key。
4. 引入 DOMPurify 或等价 sanitizer，所有 `v-html` 输出统一走 `sanitizeHtml()`。
5. AI/RCA 下载 HTML 报告也复用相同 sanitizer，避免浏览器执行危险脚本。

**验收标准**:
- `DEBUG=false` 且密钥为默认值时后端拒绝启动。
- 所有 `v-html` 调用点可追踪到统一 sanitizer。
- 安全文档说明密钥生成、轮换和配置方式。

### 0.3 查询执行链路重构

**目标**: 降低查询模块复杂度，为权限、缓存、异步查询和不同 SQL 方言打基础。

**涉及文件**:
- `backend/app/services/query_service.py`
- `backend/app/utils/db_executor.py`
- `backend/app/utils/connection_pool_manager.py`
- `backend/app/utils/sql_validator.py`
- `backend/app/utils/query_optimizer.py`
- 新增：`backend/app/services/query_runner.py`
- 新增：`backend/app/services/sql_paginator.py`
- 新增：`backend/app/services/datasource_engine_factory.py`

**实施步骤**:
1. 拆分职责：
   - `DataSourceEngineFactory`: 根据数据源创建或复用 engine。
   - `SqlPaginator`: 生成分页 SQL、游标分页 SQL、COUNT SQL。
   - `QueryRunner`: 执行 SQL、处理超时、重试和结果转换。
   - `QueryService`: 只负责业务编排、权限、历史、缓存和响应模型。
2. SQL 改写逐步从正则迁移到解析器方案，优先评估 `sqlglot`。
3. COUNT 策略可配置：
   - `exact`: 精确 COUNT。
   - `deferred`: 首屏先返回数据，后台补总数。
   - `none`: 只返回 `has_more`。
4. 查询超时、最大 page size、最大导出行数进入配置项。
5. 增加覆盖用例：
   - 普通分页。
   - 深分页。
   - 游标分页。
   - 带参数模板。
   - COUNT 失败降级。

**验收标准**:
- `QueryService._execute_query` 不再超过 120 行。
- 查询结果、历史记录、缓存行为与重构前兼容。
- 新增查询链路单测覆盖主要分页和异常场景。

### 0.4 任务调度与健康检查

**目标**: 避免后台任务硬编码，提升部署可观测性。

**涉及文件**:
- `backend/app/celery_app.py`
- `backend/app/tasks/*`
- `backend/app/api/stats.py` 或新增 `backend/app/api/health.py`
- `docker-compose.yml`

**实施步骤**:
1. 移除 Celery beat 中硬编码预测任务 `args=(1,)`。
2. 定时任务来源改为数据库配置或环境配置，至少支持启用/禁用。
3. `/health` 拆分为：
   - `live`: 进程存活。
   - `ready`: DB、Redis、核心配置可用。
4. 增加 Celery worker/beat 运行状态检查。

**验收标准**:
- 默认启动不会自动对固定数据源执行训练任务。
- 健康检查可区分进程存活和依赖不可用。
- Docker healthcheck 使用 ready 检查。

### 0.5 前端性能与体验基线

**目标**: 降低首屏和重页面加载成本。

**涉及文件**:
- `frontend/vite.config.js`
- `frontend/src/utils/echarts.js`
- `frontend/src/main.js`
- `frontend/src/router/index.js`

**实施步骤**:
1. Element Plus 评估按需导入。
2. ECharts 只注册项目使用到的图表类型和组件。
3. AI、NL2SQL、Dashboard、Forecast 继续保持路由级懒加载，并按组件拆大文件。
4. 移除生产前遗留 `console.log`，必要日志走统一 debug 开关。

**验收标准**:
- `element-plus` 与 `echarts` chunk 明显下降，目标单 chunk 小于 700KB minified。
- 首屏路由不加载预测、RCA、AI 分析师的重依赖。

---

## 阶段 1：语义指标层 MVP（3 周）

### 1.1 数据模型

**目标**: 把业务指标、维度、口径、权限和版本沉淀为一等资源。

**建议模型**:
- `metric_definitions`: 指标主表，记录名称、展示名、描述、聚合方式、负责人、状态。
- `metric_expressions`: 指标表达式，按数据源和 SQL 方言存储 SQL 片段。
- `metric_dimensions`: 可分析维度，记录字段、展示名、类型、层级关系。
- `metric_versions`: 指标版本，记录口径变更和回滚点。
- `metric_permissions`: 指标级权限，后续可扩展到行级/列级。

**涉及文件**:
- 新增：`backend/app/models/metric.py`
- 新增：`backend/app/schemas/metric.py`
- 新增：`backend/app/repositories/metric_repository.py`
- 新增：`backend/app/services/metric_service.py`
- 新增：`backend/app/api/metrics.py`
- 新增：Alembic migration

**验收标准**:
- 可创建、编辑、禁用、版本化指标。
- 指标可绑定数据源、事实表、时间字段和可用维度。

### 1.2 指标查询 API

**目标**: 提供稳定的指标查询入口，减少用户直接拼 SQL。

**API 建议**:
- `GET /api/metrics`: 指标列表。
- `POST /api/metrics`: 创建指标。
- `GET /api/metrics/{id}`: 指标详情。
- `POST /api/metrics/{id}/query`: 按时间、维度、过滤条件查询指标。
- `GET /api/metrics/{id}/versions`: 指标版本。
- `POST /api/metrics/{id}/rollback`: 回滚指标版本。

**验收标准**:
- 指标查询返回标准结构：`columns`、`rows`、`total`、`sql_preview`、`execution_time_ms`。
- 所有指标查询仍走现有权限、审计、缓存和慢查询记录。

**当前落地说明（2026-05-29）**:
- 已实现 `/api/semantic-metrics` 的指标 CRUD、SQL 预览和执行入口。
- 已实现 `GET /api/semantic-metrics/{metric_id}/versions` 和 `POST /api/semantic-metrics/{metric_id}/rollback`，指标创建、更新、回滚都会保留快照版本。
- 当前指标可见性采用 owner/admin + 用户级共享模型：普通用户可访问自己创建的指标，以及被授予 `viewer` 或 `editor` 的指标；`role.name == "admin"` 的管理员可访问全部指标。
- 已实现 `GET /api/semantic-metrics/{metric_id}/permissions`、`POST /api/semantic-metrics/{metric_id}/permissions`、`DELETE /api/semantic-metrics/{metric_id}/permissions/{user_id}`，仅 owner/admin 可管理共享。
- `viewer` 可查看、预览和执行指标查询；`editor` 可在 viewer 权限基础上编辑指标和回滚版本；删除指标和管理共享仍仅限 owner/admin。
- 指标查询仍复用 `QueryService.execute_sql()`，继续保留查询历史、分页、缓存与慢查询相关链路。
- `metric_key` 暂保持全局唯一，后续引入团队空间或共享权限时再评估是否改为租户/空间内唯一。
- 当前共享范围为用户级；团队/角色共享、行级/列级权限、脱敏策略归入阶段 2 权限增强。

### 1.3 前端管理页面

**目标**: 让业务和数据管理员能维护指标口径。

**涉及文件**:
- 新增：`frontend/src/api/metric.js`
- 新增：`frontend/src/views/MetricList.vue`
- 新增：`frontend/src/views/MetricForm.vue`
- 新增：`frontend/src/views/MetricDetail.vue`
- 修改：`frontend/src/router/index.js`
- 修改：菜单配置或初始化数据

**验收标准**:
- 管理员可维护指标、维度、表达式和版本。
- 编辑页支持 SQL 预览与测试查询。
- 指标详情页展示使用位置：仪表盘、订阅、RCA、模板。

### 1.4 与现有智能模块集成

**目标**: 让 AI 和 NL2SQL 优先引用指标层，而不是自由生成不稳定口径。

**开发约束**: 开发、调试或调用任何 LLM 能力前，必须先阅读 `semantic/` 下相关语义层文档，确认数据逻辑、指标口径、维度、关联关系、过滤条件和业务含义，再调整 prompt、工具调用或 SQL 生成逻辑。

**涉及模块**:
- `backend/app/services/nl2sql_service.py`
- `backend/app/services/ai_analyst_service.py`
- `backend/app/services/rca_service.py`
- `backend/app/services/dashboard_service.py`

**实施步骤**:
1. NL2SQL prompt 注入可用指标列表、同义词和维度说明。
2. AI 分析师工具新增 `list_metrics`、`query_metric`。
3. RCA 指标配置优先从 `metric_definitions` 选择。
4. 仪表盘组件支持绑定指标而不是直接绑定 SQL。

**验收标准**:
- 用户问“本月销售额”时，NL2SQL 能使用统一销售额指标口径。
- AI 分析师返回中标注使用的指标名称和版本。
- RCA 配置可直接选择指标。

**当前落地说明（2026-05-29）**:
- NL2SQL system prompt 已注入当前用户在当前数据源下可见的启用语义指标。
- 注入内容包含 `metric_key`、名称、描述、`metric_expression`、`time_column`、可用维度和压缩后的 `base_sql`。
- NL2SQL 生成缓存指纹已纳入语义指标上下文，避免不同用户或不同指标口径复用旧 SQL。
- 当前仅做 prompt 级引导，尚未强制把命中指标转换为 `/api/semantic-metrics/query/execute` 调用；该能力留给 AI 分析师工具化接入或后续 NL2SQL 结构化路由。
- AI 分析师已新增 `list_metrics` 与 `query_metric` 工具，工具执行时继承当前用户上下文，只能读取 owner/admin 可见指标。
- `query_metric` 会先验证指标可见性和数据源归属，再复用语义指标查询服务执行，结果返回 `columns`、`rows`、`total`、分页信息和执行耗时。
- RCA 指标配置已支持 `semantic_metric_key` 绑定。创建或更新配置时会校验当前用户是否可访问该语义指标，以及指标是否属于当前数据源。
- 绑定语义指标的 RCA 分析不再拼接旧的 `metric_field + source_table` SQL，而是复用语义指标查询服务分别查询当前期、基线期和下钻维度，然后在应用层计算变化率、贡献度和异常项。
- 当前 RCA 语义指标路径使用配置中的 `drill_dimensions` 作为语义指标维度，要求这些维度存在于指标定义中；更复杂的多层下钻和父级过滤仍留给后续迭代。
- 查询订阅已支持 `semantic_metric_key + semantic_query` 直接绑定语义指标，旧的模板 SQL 订阅保持兼容。
- 语义指标订阅创建时校验当前用户可见性；执行时复用语义指标查询服务，`semantic_query` 支持 `dimensions`、`filters`、`start_time`、`end_time` 和 `page_size`。
- 订阅模型的 `template_id` 已改为可空：模板订阅和语义指标订阅至少选择一种。
- 订阅管理页已支持选择“模板查询 / 语义指标”两类订阅；语义指标订阅可配置指标、维度、时间范围、过滤条件和最大行数，并继续复用启停、立即执行和执行历史能力。
- 已新增 `scripts/verify-local.sh` 本地门禁脚本，统一执行前端 `lint/typecheck/build` 与后端语义指标、订阅、查询链路核心回归。
- 前端生产构建已切换为 Terser 压缩，使 `drop_console/drop_debugger` 配置真实生效，并消除 Vite 构建 warning。
- 后端 schema 已迁移到 Pydantic v2 `ConfigDict(from_attributes=True)`，订阅和定时报表调度服务已移除 `datetime.utcnow()` 用法；核心回归 warning 从 16 个降到 4 个。

---

## 阶段 2：数据质量、权限与分析闭环（后续 4-6 周）

### 2.1 数据质量与报表 SLA

**功能方向**:
- 数据延迟检测。
- 空值率/行数/分布突变检测。
- 报表生成 SLA 监控。
- 异常自动触发通知或 RCA。

### 2.2 权限与脱敏增强

**功能方向**:
- 行级权限。
- 列级权限。
- 导出水印。
- 敏感字段脱敏策略。
- 下载审计与追踪。

### 2.3 分析工作台

**功能方向**:
- 查询结果、图表、AI 解读保存为分析快照。
- 支持评论、分享、版本和引用到仪表盘。
- 定时报表可引用分析快照模板。

### 2.4 预测 + RCA 联动

**功能方向**:
- 预测偏离阈值自动触发 RCA。
- RCA 输出沉淀为规则和历史案例。
- 相似异常复用历史根因和处理建议。

---

## 推荐执行顺序

1. 修复 Redis 初始化和测试导入。
2. 修复前端 lint error，建立 CI 基线。
3. 修复密钥占位符、`v-html` sanitizer 和 Fernet key 文档。
4. 拆分查询执行链路，补分页和 COUNT 测试。
5. 处理 Celery 硬编码任务和健康检查。
6. 优化前端重依赖 chunk。
7. 开始语义指标层模型和 API。
8. 接入 NL2SQL、AI 分析师、RCA 和仪表盘。

---

## 质量门禁

每个阶段完成时必须满足：
- 后端测试可运行，新增模块必须有单测或 API 集成测试。
- 前端 lint error 为 0，build 成功。
- 关键安全变更有回归测试或手工验证记录。
- 新增 API 更新 README 或对应功能文档。
- 涉及数据库结构变更必须有 Alembic migration。
