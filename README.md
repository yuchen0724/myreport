# 自定义报表查询系统 (myreport)

一个功能强大的自定义报表查询系统，支持 SQL 模板管理、参数化查询、数据导出、可视化展示、NL2SQL 自然语言查询、销售预测、RCA 根因分析和 AI 智能解读。

## 功能特性

### 核心功能
- **SQL 模板管理** — 创建、编辑、删除和管理 SQL 查询模板，支持版本控制与回滚
- **参数化查询** — 支持动态参数和日期范围查询
- **数据导出** — 支持 Excel、PDF 等多种格式，Celery 异步处理长时间任务
- **数据可视化** — 图表展示，支持趋势图、柱状图、饼图等
- **仪表盘** — 可视化组件拖拽编排，多布局管理

### NL2SQL（自然语言转 SQL）
- **LangChain 集成** — 支持 raw / langchain 双适配器模式
- **结构化输出** — Pydantic Schema 驱动，失败自动回退 JSON 解析
- **提示词外部化** — 提示词模板为 `.md` 文件，支持热更新无需重启
- **Schema 语义检索** — 长 schema 自动按关键词筛选相关章节
- **SQL 自动修复** — SQL 执行失败后 LLM 自动修复并重试
- **SQL 分析** — SQL 语句性能分析与优化建议

### 销售预测
- **LightGBM 预测** — 基于历史数据的销售预测，支持训练+预测一键完成
- **商品名称回填** — 预测结果自动关联商品名称
- **异步训练任务** — Celery 后台处理，多任务进度实时显示，支持手动停止
- **模型对比** — 多模型指标对比分析
- **预测结果查询** — 历史预测结果检索与图表展示

### RCA 根因分析
- **异常检测** — 基于指标配置自动检测销售异常
- **根因定位** — AI 驱动的异常贡献度分析与根因解读
- **维度下钻** — 商品、门店等维度逐层下钻分析
- **AI 智能解读** — LLM 对异常数据自动生成分析报告，支持 HTML 下载

### AI 数据分析师
- **自然语言分析** — 用自然语言描述分析需求，AI 自动生成 SQL 并执行
- **流式输出** — SSE 流式传输分析结果，实时展示
- **上下文对话** — 支持多轮对话，基于历史上下文持续分析

### 模板与协作
- **模板分享** — 支持模板分享给其他用户
- **收藏夹** — 收藏常用模板，快速访问
- **查询订阅推送** — 定时执行查询并推送结果
- **定时报表** — 定时生成报表并邮件发送
- **SQL 审核工作流** — SQL 变更审批流程

### 系统管理
- **权限管理** — 基于角色的访问控制（RBAC）
- **审计日志** — 记录所有 API 调用操作
- **菜单管理** — 动态菜单配置
- **代理服务器管理** — 数据库代理连接管理
- **连接池监控** — 数据库连接池实时指标
- **SQL 方言适配** — 多数据库方言自动转换
- **告警通知** — 任务异常告警

### 移动端
- **响应式适配** — 移动端仪表盘、模板管理、查询编辑

## 技术栈

### 前端
- Vue 3 (Composition API) + Element Plus
- Pinia (状态管理) + Vue Router
- Axios + Vite
- vuedraggable (列拖拽排序)

### 后端
- FastAPI + SQLAlchemy + Alembic
- PostgreSQL + Redis
- Celery (异步任务)
- Apache Doris / Hive (数据仓库)
- LangChain + langchain-openai (LLM 集成)
- LightGBM (机器学习预测)

### 基础设施
- Docker Compose (部署)
- Pytest (测试)

## 快速开始

### 前置要求

- Node.js 16+
- Python 3.9+
- Redis 6+
- PostgreSQL 12+

### 安装

```bash
# 克隆项目
git clone https://github.com/yuchen0724/myreport.git
cd myreport

# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install

# 配置数据库
cp ../backend/.env.example ../backend/.env
# 编辑 .env 文件，设置数据库连接等配置
```

### 启动服务

```bash
# 一键启动（推荐）
./start.sh start

# 查看服务状态
./start.sh status

# 查看日志
./start.sh logs backend
./start.sh logs celery
```

或者手动启动：

```bash
# 启动 Redis
redis-server

# 启动 Celery Worker
cd backend
celery -A celery_config worker --loglevel=info -Q export,prediction

# 启动后端服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端服务
cd frontend
npm run dev
```

### 访问系统

- 前端界面: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 项目结构

```
myreport/
├── backend/                          # 后端代码 (FastAPI)
│   ├── app/
│   │   ├── api/                      # API 路由层（30 个模块）
│   │   │   ├── auth.py               # 认证
│   │   │   ├── templates.py          # SQL 模板 CRUD
│   │   │   ├── query.py              # SQL 查询执行
│   │   │   ├── prediction.py         # 销售预测（训练+预测+停止）
│   │   │   ├── nl2sql.py             # 自然语言转 SQL
│   │   │   ├── rca.py                # RCA 根因分析
│   │   │   ├── ai_analyst.py         # AI 数据分析师
│   │   │   ├── dashboard.py          # 仪表盘
│   │   │   ├── drilldown.py          # 数据下钻
│   │   │   ├── favorites.py          # 收藏夹
│   │   │   ├── subscriptions.py      # 查询订阅推送
│   │   │   ├── sql_reviews.py        # SQL 审核
│   │   │   ├── scheduled_reports.py  # 定时报表
│   │   │   ├── model_compare.py      # 模型对比
│   │   │   ├── pool_metrics.py       # 连接池监控
│   │   │   ├── dialects.py           # SQL 方言适配
│   │   │   ├── alerts.py             # 告警通知
│   │   │   ├── menus.py              # 菜单管理
│   │   │   ├── proxy_servers.py      # 代理服务器管理
│   │   │   └── ...
│   │   ├── services/                 # 业务逻辑层
│   │   │   ├── prediction_service.py # 预测核心逻辑
│   │   │   ├── nl2sql_service.py     # NL2SQL 核心逻辑
│   │   │   ├── ai_analyst_service.py # AI 分析师
│   │   │   ├── rca_service.py        # RCA 分析
│   │   │   └── ...
│   │   ├── repositories/             # 数据访问层（Repository 模式）
│   │   ├── models/                   # SQLAlchemy 数据模型（28 个）
│   │   ├── schemas/                  # Pydantic 请求/响应模型
│   │   ├── middleware/               # 中间件（限流/审计/错误处理）
│   │   ├── core/                     # 核心（数据库/认证/安全/Redis）
│   │   ├── tasks/                    # Celery 异步任务
│   │   ├── utils/                    # 工具函数
│   │   └── main.py                   # FastAPI 应用入口
│   ├── prompts/
│   │   ├── nl2sql/                   # NL2SQL 提示词模板
│   │   └── rca_analysis_system.md    # RCA 分析提示词
│   ├── alembic/                      # 数据库迁移
│   ├── tests/                        # 测试代码
│   ├── requirements.txt
│   └── celery_config.py              # Celery 配置
├── frontend/                         # 前端代码 (Vue 3)
│   ├── src/
│   │   ├── api/                      # API 调用封装
│   │   ├── components/               # Vue 组件
│   │   │   ├── EnhancedTable.vue     # 增强表格
│   │   │   ├── TableToolbar.vue      # 表格工具栏（列拖拽排序）
│   │   │   └── ...
│   │   ├── views/                    # 页面视图（30+ 页面）
│   │   │   ├── Dashboard.vue         # 仪表盘
│   │   │   ├── NL2SQLEditor.vue      # NL2SQL 编辑器
│   │   │   ├── SalesForecast.vue     # 销售预测
│   │   │   ├── RcaDashboard.vue      # RCA 根因分析
│   │   │   ├── AIAnalyst.vue         # AI 数据分析师
│   │   │   ├── Favorites.vue         # 收藏夹
│   │   │   ├── SubscriptionList.vue  # 订阅推送
│   │   │   ├── SqlReviewList.vue     # SQL 审核
│   │   │   ├── ModelCompare.vue      # 模型对比
│   │   │   ├── PoolMonitor.vue       # 连接池监控
│   │   │   ├── mobile/               # 移动端页面
│   │   │   └── ...
│   │   ├── store/                    # Pinia 状态管理
│   │   └── router/                   # 路由配置
│   ├── package.json
│   └── vite.config.js
├── docs/                             # 文档
│   ├── plans/                        # 实施计划
│   └── ...
├── semantic/                         # 语义层文档（数据库 Schema 描述）
├── start.sh                          # 一键启动脚本
├── docker-compose.yml                # Docker 部署配置
└── README.md
```

## API 路由总览

| 路由前缀 | 模块 | 说明 |
|----------|------|------|
| `/api/auth` | auth.py | 登录/用户信息 |
| `/api/templates` | templates.py | SQL 模板 CRUD + 分享 + 版本回滚 |
| `/api/query` | query.py | SQL 查询执行 + 历史记录 |
| `/api/datasources` | data_sources.py | 数据源管理 |
| `/api/proxy-servers` | proxy_servers.py | 代理服务器管理 |
| `/api/nl2sql` | nl2sql.py | 自然语言转 SQL |
| `/api/sql` | sql_analysis.py | SQL 分析 |
| `/api/charts` | charts.py | 图表数据 |
| `/api/report` | report.py | 报表生成 (Excel/PDF) |
| `/api/async-export` | async_export.py | 异步导出任务 |
| `/api/prediction` | prediction.py | 销售预测（训练+预测+停止） |
| `/api/rca` | rca.py | RCA 根因分析 |
| `/api/ai-analyst` | ai_analyst.py | AI 数据分析师 |
| `/api/dashboard` | dashboard.py | 仪表盘 |
| `/api/drilldown` | drilldown.py | 数据下钻 |
| `/api/favorites` | favorites.py | 收藏夹管理 |
| `/api/subscriptions` | subscriptions.py | 查询订阅推送 |
| `/api/reviews` | sql_reviews.py | SQL 审核 |
| `/api/scheduled-reports` | scheduled_reports.py | 定时报表 |
| `/api/model-compare` | model_compare.py | 模型对比 |
| `/api/metrics` | pool_metrics.py | 连接池监控 |
| `/api/dialects` | dialects.py | SQL 方言适配 |
| `/api/alerts` | alerts.py | 告警通知 |
| `/api/menus` | menus.py | 菜单管理 |
| `/api/users` | users.py | 用户管理 |
| `/api/cache` | cache.py | 缓存管理 |
| `/api/audit-logs` | audit_logs.py | 审计日志 |
| `/api/stats` | stats.py | 统计信息 |
| `/api/config` | config.py | 前端配置 |

## 使用指南

### 1. 创建 SQL 模板

1. 登录系统
2. 进入「模板管理」页面
3. 点击「新建模板」
4. 填写模板名称、描述、SQL 语句（支持参数化）和参数定义

### 2. 执行查询

1. 选择已创建的模板
2. 输入查询参数
3. 点击「执行查询」
4. 查看查询结果，支持图表展示

### 3. 导出数据

1. 在查询结果页面点击「导出」
2. 选择导出格式（Excel/PDF）
3. 系统异步处理，可在「异步导出」页面查看进度和下载

### 4. NL2SQL 自然语言查询

1. 进入「NL2SQL」页面
2. 选择数据源
3. 用自然语言描述查询需求（如「查询上个月销售额 top 10 的商品」）
4. 系统自动生成 SQL 并执行，支持图表展示

### 5. 销售预测

1. 进入「销售预测」页面
2. 选择数据源，设置训练参数
3. 点击「训练并预测」，后台异步执行
4. 支持多任务进度实时显示和手动停止
5. 在「预测结果查询」页面查看结果

### 6. RCA 根因分析

1. 进入「RCA」页面
2. 配置指标和分析参数
3. 启动分析任务
4. 查看异常检测结果和 AI 智能解读报告

### 7. AI 数据分析师

1. 进入「AI 分析师」页面
2. 用自然语言描述分析需求
3. AI 自动生成 SQL、执行查询并返回分析结果
4. 支持多轮对话深入分析

## 开发指南

### 添加新的 API 端点

1. 在 `backend/app/api/` 中创建路由文件，定义 `router = APIRouter(prefix="/api/xxx", tags=[...])`
2. 在 `backend/app/main.py` 中 `app.include_router(xxx.router)` 注册路由
3. 在 `frontend/src/api/` 中创建对应的 API 调用函数
4. 在前端组件中使用 API

### 添加新的页面

1. 在 `frontend/src/views/` 中创建 Vue 组件
2. 在 `frontend/src/router/index.js` 中添加路由
3. 在 `frontend/src/components/Sidebar.vue` 中添加导航菜单

### NL2SQL 开发

提示词模板位置：`backend/prompts/nl2sql/`
- `system_prompt.md`: NL2SQL 系统提示词
- `repair_prompt.md`: SQL 执行失败后的修复提示词

提示词使用 Python `str.format()` 渲染，JSON 示例中的 `{` 必须转义为 `{{`。修改后无需重启，文件自动热加载。

### 配置项说明

主要配置项在 `backend/app/config.py`：

```bash
# LLM / NL2SQL
LLM_ADAPTER=langchain        # raw 或 langchain
LLM_PROVIDER=azure           # openai, azure, ollama
LLM_MODEL=gpt-5.4-nano
LLM_API_MODE=responses       # chat 或 responses

# NL2SQL 行为
NL2SQL_TEMPERATURE=0.0
NL2SQL_MAX_RETRIES=2
NL2SQL_SCHEMA_RETRIEVAL_ENABLED=true

# 预测
PREDICTION_ENABLED=true
PREDICTION_TRAIN_DEFAULT_DAYS=365
PREDICTION_FORECAST_DAYS=30
```

### 运行测试

```bash
# 后端测试
cd backend
pytest

# 运行单个测试文件
pytest tests/test_prediction_api.py

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

## 部署

### Docker 部署（推荐）

```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
```

### 手动部署

1. 配置生产环境变量
2. 使用 Gunicorn + Uvicorn 部署后端
3. 使用 Nginx 反向代理
4. 配置 HTTPS 证书
5. 设置进程管理（PM2/Systemd）

## 常见问题

### Q: 启动服务时端口被占用怎么办？

```bash
lsof -i :8000
kill -9 <PID>
```

### Q: NL2SQL 生成 SQL 失败怎么办？

1. 检查数据源的 schema 语义层文档是否完整
2. 调整 `backend/prompts/nl2sql/system_prompt.md` 中的提示词
3. 查看后端日志确认错误原因

### Q: 预测任务执行失败怎么办？

1. 确保 Celery Worker 已启动：`./start.sh start`
2. 检查数据源配置是否正确
3. 查看日志：`./start.sh logs celery`

### Q: 如何重置数据库？

```bash
cd backend
python scripts/reset_database.py
```

## 文档

- [快速启动指南](START_GUIDE.md)
- [系统架构](ARCHITECTURE.md)
- [API 文档](http://localhost:8000/docs)（FastAPI 自动生成）
- [开发文档](docs/)

## 更新日志

### v1.3.0 (2026-05-28)
- ✨ **RCA 根因分析** — 异常检测 + AI 根因解读 + 维度下钻 + HTML 报告下载
- ✨ **AI 数据分析师** — 自然语言分析 + SSE 流式输出 + 多轮对话
- ✨ **训练+预测合并** — 一键三阶段流水线（拉取+训练→预测→完成）
- ✨ **多任务进度显示** — 同时展示多个训练任务进度，支持手动停止
- ✨ **收藏夹** — 收藏常用模板快速访问
- ✨ **查询订阅推送** — 定时执行查询并推送结果
- ✨ **SQL 审核工作流** — SQL 变更审批流程
- ✨ **模型对比** — 多模型指标对比分析
- ✨ **定时报表** — 定时生成报表并发送
- ✨ **连接池监控** — 数据库连接池实时指标
- ✨ **SQL 方言适配** — 多数据库方言自动转换
- ✨ **代理服务器管理** — 数据库代理连接管理
- ✨ **菜单管理** — 动态菜单配置
- ✨ **告警通知** — 任务异常告警
- ✨ **移动端适配** — 仪表盘、模板管理、查询编辑响应式布局
- ✨ **仪表盘组件编辑器** — 可视化组件拖拽编排
- 🛠 数据下钻（商品维度反向下钻到门店）

### v1.2.0 (2026-05-21)
- ✨ NL2SQL + LangChain 架构升级（双适配器、结构化输出、提示词热更新）
- ✨ 销售预测增强（商品名称回填、Doris 兼容性修复）
- ✨ 前端改进（列拖拽排序、集团选择器、递归更新修复）
- 🛠 连接池管理器、SQL 参数化防注入

### v1.1.0 (2025-04-22)
- ✨ 模板版本控制 + 分享功能
- ✨ 异步导出功能
- 🐛 修复模板管理按钮无反应问题

### v1.0.0 (2025-04-21)
- ✨ 初始版本发布（模板管理、查询执行、数据导出、用户认证）

---

**注意**: 本项目正在积极开发中，可能会有 breaking changes。建议在生产环境使用前进行充分测试。

## 许可证

本项目采用 MIT 许可证 — 详见 [LICENSE](LICENSE) 文件

## 联系方式

- 项目主页: https://github.com/yuchen0724/myreport
- 问题反馈: https://github.com/yuchen0724/myreport/issues
