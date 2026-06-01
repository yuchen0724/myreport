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

---

## 阶段 2：语义层文档升级（立即开始，和模型一起推进）

### 2.1 文档目标

把 `semantic/` 从“表结构说明”升级为“LLM 可执行的语义规范”。目标不是写得更长，而是写得更可推理、可校验、可复用。

### 2.2 建议的统一文档结构

每个数据源文档都按同一模板组织：

1. 业务总览
   - 数据域
   - 适用场景
   - 不适用场景
   - 口径总原则

2. 概念词典
   - 业务术语 -> 标准定义 -> 对应字段 -> 易混淆项

3. 指标词典
   - 指标中文名
   - metric_key
   - 公式
   - 单位
   - 含税/未税
   - 是否可加总
   - 默认口径
   - 适用表
   - 禁用场景

4. 维度词典
   - 维度名
   - 粒度
   - 层级关系
   - 可取值范围
   - 显示名/编码规则
   - 是否需要 join 维表

5. 表与关系
   - 事实表 / 维表 / 跨库表
   - 主键
   - 粒度
   - join key
   - 一对多风险
   - 去重规则

6. 默认过滤规则
   - 默认排除项
   - 业务口径过滤
   - 日期范围规则
   - 分表规则

7. 查询路由规则
   - 先选哪类表
   - 明细 / 聚合 / 预警如何选表
   - 快查优先表
   - 下钻优先路径

8. 示例库
   - 标准问法
   - 标准 SQL
   - 反例
   - 边界案例

### 2.3 语义层必须补齐的内容

1. 指标口径卡片
   - “销售额”“销量”“毛利”“库存”“动销率”“门店数”“商品数”“供应商数”“异常数”必须有统一口径。

2. 维度层级规则
   - 类目层级、组织层级、时间层级、预警层级要明确上卷/下钻方式。

3. join 规则
   - 哪些表需要跨库 join，哪些表不能直接 join，哪些 join 需要去重。

4. 默认过滤规则
   - `exclude_flag`、`service_flag`、`shopping_bag_flag` 等必须写成默认规则，不要只放在字段说明里。

5. 反例和禁用写法
   - 例如不能把含税和未税混用，不能对比率先平均后汇总，不能把订单数和商品数混为一谈。

### 2.4 建议的机器可读同步

在 markdown 之外，再生成一份机器可读语义层，例如：
- `semantic/*.yaml` 或 `semantic/*.json`

内容至少包含：
- tables
- columns
- metrics
- dimensions
- joins
- defaults
- aliases
- forbidden_patterns

这样 NL2SQL prompt、校验器、缓存指纹、指标选择器都能复用同一份结构化语义，而不是只靠长 prompt。

### 2.5 语义层优先级规则

LLM 生成 SQL 时的优先级建议固定为：
1. 语义层文档
2. 结构化指标定义
3. 实时 schema
4. 通用模型常识

一旦冲突，前者覆盖后者。

### 2.6 语义层维护规范

**新增或修改表字段时**，必须同步更新：
- 文档中的字段定义
- 指标词典
- 维度词典
- 查询路由规则
- 示例 SQL

**新增或修改指标时**，必须同步更新：
- 指标表达式
- 默认口径
- 适用表
- 前端/后端可见性
- NL2SQL prompt 注入

**新增或修改 JOIN 时**，必须同步更新：
- 连接键
- 去重规则
- 是否一对多
- 是否跨库

### 2.7 当前文档的明确优化方向

结合现在已有内容，建议优先补这几块：
- 统一所有数据源的“业务总览 + 口径原则”开头。
- 给核心指标补“指标卡片”，避免散落在表字段中。
- 把 `ads_cockpit_fd_store_ware_d` 的预警字段单独整理成“异常/预警维度”。
- 把跨库依赖写成独立的“连接规则章节”。
- 把“默认过滤”从字段说明中抽出来，形成统一规则表。
- 给每个主题补 3~5 条标准问句和对应 SQL 模板。

---

## 阶段 3：执行顺序建议

1. 先把 `semantic/` 文档结构统一。
2. 同步生成一份结构化 YAML/JSON。
3. 让 NL2SQL prompt 只注入“摘要 + 结构化指标 + 查询路由规则”。
4. 再做语义层校验器，检查字段、指标、join 和过滤是否齐全。
5. 最后把 AI 分析师、RCA、订阅、仪表盘都切到同一语义层来源。

---

## 验收标准

- 用户问“销售额”“销量”“库存”“毛利”时，系统能稳定选定唯一口径。
- 生成 SQL 不再频繁发明字段或 join。
- 跨库维表、默认过滤、分表规则都能在语义层中追溯。
- NL2SQL、AI 分析师、RCA、订阅、仪表盘共享同一套指标定义。
- 文档既能给人读，也能被程序消费。
