# 自定义报表查询系统 (myreport)

一个功能强大的自定义报表查询系统，支持 SQL 模板管理、参数化查询、数据导出、NL2SQL 自然语言查询、销售预测、RCA 根因分析和 AI 智能解读。

---

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **前端** | Vue 3 (Composition API) + Element Plus + Pinia + Vue Router + Vite + Axios | Vue 3.3+ |
| **后端** | FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery | FastAPI 0.136 |
| **数据仓库** | Apache Doris / StarRocks (MySQL 协议兼容) | — |
| **ML** | LightGBM + Prophet + SARIMA | — |
| **LLM** | LangChain + langchain-openai | LangChain 1.3 |
| **部署** | Docker Compose (Nginx 反向代理) | — |

## 项目结构

```
myreport/
├── backend/
│   ├── app/
│   │   ├── api/            # 31 个 API 路由模块
│   │   ├── services/       # 业务逻辑层 (含 nl2sql/ 子包)
│   │   ├── repositories/   # 数据访问层 (Repository 模式)
│   │   ├── models/         # SQLAlchemy 数据模型 (28 个)
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── core/           # 数据库/认证/安全/Redis
│   │   ├── middleware/     # 限流/审计/错误处理
│   │   ├── tasks/          # Celery 异步任务
│   │   └── utils/          # SQL 验证/查询优化/PDF 生成/LLM
│   ├── prompts/            # LLM 提示词 (外部化 .md 文件)
│   └── tests/              # 50+ 测试文件
├── frontend/
│   ├── src/
│   │   ├── api/            # 27 个 API 模块 (全 TypeScript)
│   │   ├── views/          # 34 个视图页面
│   │   ├── components/     # 20+ 公共组件
│   │   ├── store/          # Pinia 状态管理 (TypeScript)
│   │   ├── router/         # Vue Router (TypeScript)
│   │   ├── types/          # 共享类型定义
│   │   └── utils/          # 工具函数
│   └── package.json
├── semantic/               # 语义层文档 (数据目录描述)
├── docker-compose.yml
└── start.sh
```

## 功能特性

### NL2SQL（自然语言转 SQL）

- **LangChain / Raw 双适配器** — 支持 OpenAI、Azure OpenAI、Ollama、Anthropic
- **提示词外部化** — `.md` 文件热加载，无需重启
- **Schema 语义检索** — 自动按问题关键词筛选相关表结构
- **SQL 自动修复** — 执行失败后 LLM 自动修复并重试
- **语义层文档** — `semantic/` 目录存放数据字典，给 LLM 提供业务上下文
- **重试机制** — 最多 3 次重试 + 正则回退 JSON 解析

### AI 数据分析师

- **自研 Agent 循环** — 手动编排工具调用（非 LangChain Agent），最多 30 轮
- **6 个内置工具** — `execute_sql`、`get_schema`、`generate_chart`、`analyze_data`、`list_metrics`、`query_metric`
- **SSE 流式输出** — 逐 token 推送，实时展示分析过程
- **LLM 驱动工具提取** — 当 LLM 输出非标准格式时，二次 LLM 调用自动提取工具参数，替代脆弱的正则匹配
- **智能回退** — JSON 格式、markdown 代码块、纯 SELECT 文本自动识别
- **SQL 自动 Schema 注入** — 连续 SQL 失败时自动查询表结构并注入上下文
- **语义层优先** — 先读语义层文档，不足时再查数据库
- **对话历史** — Redis 持久化 + 滑动窗口摘要（超 20 条自动压缩）

### 销售预测

- LightGBM / Prophet / SARIMA 多算法支持
- 训练+预测一键完成，Celery 异步后台处理
- 模型对比分析与预测结果查询

### RCA 根因分析

- 自动异常检测 + LLM 智能解读
- 维度下钻（商品/门店）
- 支持 HTML 报告下载

### 系统管理

- RBAC 权限控制（admin / editor / user）
- 审计日志、限流、动态菜单配置
- 数据源管理（支持 SOCKS5 代理）
- SQL 审核工作流

## 架构设计

### 分层架构

```
API 路由层 → Service 业务逻辑层 → Repository 数据访问层 → Database
     ↓              ↓                    ↓
  Pydantic Schema  PromptManager      SQLAlchemy ORM
```

### 关键设计决策

| 决策 | 说明 |
|------|------|
| **Repository 模式** | 所有数据库查询封装在 `repositories/`，Service 通过 Repository 访问数据，Repository 只 `flush()` 不 `commit()` |
| **JWT 认证** | `core/auth_deps.py` 提供 `get_current_user_id` / `get_current_user` 作为 FastAPI Depends |
| **异步导出** | Celery + Redis Broker 处理长时间任务，前端轮询状态 |
| **提示词外部化** | `.md` 文件热加载，`PromptManager` 基于 mtime 缓存 |
| **Engine 级别代理** | SOCKS5 代理通过 `create_engine(creator=...)` 实现，无全局 socket 污染 |
| **结构化输出优先** | LangChain 场景下 `chat_structured` 优先，失败回退文本解析 |

### LLM 调用链路

```
用户输入 → SSE /chat/stream → AIAnalystService.chat_stream()
  → Agent 循环 (最多 30 轮):
    1. LLMClient.chat_stream()  ← 真流式逐 token
    2. _parse_action() → JSON / LLM reformat / 智能回退
    3. _execute_tool() → 6 种工具分发
    4. 结果反馈 → 继续下一轮
  → yield SSE 事件 (token / tool_call / tool_result / chart / done)
```

### Prompt 体系

| 文件 | 用途 |
|------|------|
| `prompts/ai_analyst/system_prompt.md` | AI Analyst 角色定义 + 输出格式 + SQL 规则 |
| `prompts/ai_analyst/tools.md` | 工具参数参考格式 |
| `prompts/nl2sql/system_prompt.md` | NL2SQL 系统提示词 |
| `prompts/nl2sql/repair_prompt.md` | SQL 修复提示词 |
| `prompts/rca_analysis_system.md` | RCA 根因分析 |
| `prompts/sql_optimizer.md` | SQL 优化提示词 |

### 安全

- JWT Token + 黑名单检查
- SQL 只读校验（禁止 INSERT/UPDATE/DELETE/DROP）
- 禁止直接查询 `information_schema`（强制走 `get_schema` 工具）
- SSL 验证可选（`ssl_verify_enabled` 配置）
- 限流中间件（内存模式 / Redis 模式）

## 开发命令

### 后端

```bash
# 启动开发服务器
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 运行测试
cd backend && pytest
pytest tests/test_template_api.py::test_create_template

# 数据库迁移
alembic upgrade head
alembic revision --autogenerate -m "description"

# Celery Worker
celery -A celery_config worker --loglevel=info --concurrency=4 -Q export,prediction
```

### 前端

```bash
cd frontend
npm install          # 安装依赖
npm run dev          # 开发服务器 :3000
npm run build        # 生产构建
npm run lint         # ESLint 检查
```

### 一键启动

```bash
./start.sh start     # 启动所有服务
./start.sh stop      # 停止所有服务
./start.sh status    # 查看服务状态
./start.sh logs backend  # 查看指定服务日志
```

## API 路由

31 个路由模块，前缀包括：

| 路由前缀 | 功能 |
|----------|------|
| `/api/auth` | 登录/用户信息 |
| `/api/templates` | SQL 模板 CRUD + 版本管理 |
| `/api/query` | SQL 查询执行 + 历史 |
| `/api/nl2sql` | 自然语言→SQL |
| `/api/ai-analyst` | AI 数据分析师 (SSE 流式) |
| `/api/rca` | 根因分析 |
| `/api/prediction` | 销售预测 |
| `/api/charts` | 图表生成 |
| `/api/report` | 报表导出 |
| `/api/dashboard` | 仪表盘 |
| `/api/datasources` | 数据源管理 |
| `/api/subscriptions` | 订阅推送 |
| `/api/scheduled-reports` | 定时报表 |
| `/api/sql-reviews` | SQL 审核 |
| `/api/audit-logs` | 审计日志 |
| `/api/menus` | 动态菜单 |
| `/api/users` | 用户管理 |
| ... | 共 31 个模块 |

## 数据模型

28 个 SQLAlchemy 模型，关键模型：

| 模型 | 用途 |
|------|------|
| `User` / `Role` / `Permission` | 用户认证 + RBAC |
| `Template` / `TemplateVersion` | SQL 模板 + 版本历史 |
| `DataSource` | 数据源连接配置 (Fernet 加密) |
| `QueryHistory` | 查询历史 |
| `PredictionModel` / `PredictionResult` | 预测模型 + 结果 |
| `RcaMetricConfig` / `RcaAnomaly` | RCA 配置 + 异常记录 |
| `DashboardLayout` / `WidgetConfig` | 仪表盘布局 |
| `AuditLog` | 审计日志 |
| `ScheduledReport` / `Subscription` | 定时报表 + 订阅 |

## 测试

- 50+ 测试文件，使用 SQLite `:memory:` 保证隔离
- 全局 `autouse` LLM mock fixture，防止真实 API 调用
- 覆盖 API / Service / Repository 三层

## 部署

```bash
# Docker Compose
docker-compose up -d

# 手动部署
./start.sh start
```

Nginx 反向代理配置参考 `nginx.conf`。

---

## 近期优化 (v2.0)

| 优化项 | 详情 |
|--------|------|
| 🔒 SSL 验证配置化 | `llm_client.py` `verify=False` → `ssl_verify_enabled` 配置项 |
| 🔒 全局 socket 补丁消除 | db_executor.py 改用 engine-level proxy creator |
| 📝 日志系统 | ~50 处 `print()` → `logger`，新增 LLM 调用详细日志 |
| 🏗 Repository 事务边界 | 全部 10 个 Repository `commit()` → `flush()`，Service 层控制事务 |
| 🔧 公共依赖 | `core/deps.py` `get_data_source_or_404` 消除路由重复代码 |
| 📦 nl2sql 子包化 | prompt_utils / schema 独立模块，主文件 1808→1548 行 |
| 🔌 Element Plus 按需加载 | unplugin-auto-import + components，减少构建体积 |
| 📘 TypeScript 全量迁移 | 27 个 API 模块 + Store + Router 全 TypeScript |
| 🧪 测试增强 | autouse LLM mock fixture，防止测试中真实 LLM 调用 |
| 🤖 AI Analyst 优化 | Prompt 外部化 + 结构化输出 + 真流式 + SSE 客户端 + 智能回退 |
| 🗃 语义层不截断 | `max_chars=0` 完整加载语义层文档 |
| ⚡ Agent 效率优化 | get_schema 最多 1 次 + CTE 子查询减少轮次 |
