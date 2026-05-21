# 自定义报表查询系统 (myreport)

一个功能强大的自定义报表查询系统，支持 SQL 模板管理、参数化查询、数据导出和可视化展示。

**最新更新**: 2026-05-21 - NL2SQL + LangChain 架构升级

## 功能特性

### 核心功能
- ✅ **SQL 模板管理** - 创建、编辑、删除和管理 SQL 查询模板，支持版本控制与回滚
- ✅ **参数化查询** - 支持动态参数和日期范围查询
- ✅ **数据导出** - 支持 Excel、PDF 等多种格式，异步处理长时间任务
- ✅ **数据可视化** - 图表展示，支持趋势图、柱状图、饼图等

### NL2SQL（自然语言转 SQL）
- ✅ **LangChain 集成** - 支持 raw / langchain 双适配器模式
- ✅ **结构化输出** - Pydantic Schema 驱动的结构化输出，失败自动回退 JSON 解析
- ✅ **提示词外部化** - 提示词模板外部化为 `.md` 文件，支持热更新无需重启
- ✅ **Schema 语义检索** - 长 schema 自动按关键词筛选相关章节
- ✅ **SQL 自动修复** - SQL 执行失败后 LLM 自动修复并重试

### 销售预测
- ✅ **LightGBM 预测** - 基于历史数据的销售预测
- ✅ **商品名称回填** - 预测结果自动关联商品名称
- ✅ **异步训练任务** - Celery 后台处理训练与预测任务

### 其他
- ✅ **模板分享** - 支持模板分享给其他用户
- ✅ **权限管理** - 基于角色的访问控制
- ✅ **审计日志** - 记录所有 API 调用操作

## 技术栈

### 前端
- Vue 3 (Composition API)
- Element Plus
- Pinia (状态管理)
- Vue Router
- Axios
- Vite
- vuedraggable (列拖拽排序)

### 后端
- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- Celery (异步任务)
- Apache Doris / Hive (数据仓库)
- LangChain + langchain-openai (LLM 集成)

### 基础设施
- Docker Compose (部署)
- Alembic (数据库迁移)
- Pytest (测试)

## 快速开始

### 前置要求

- Node.js 16+
- Python 3.9+
- Redis 6+
- PostgreSQL 12+

### 安装

1. 克隆项目
```bash
git clone https://github.com/yuchen0724/myreport.git
cd myreport
```

2. 安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

3. 安装前端依赖
```bash
cd frontend
npm install
```

4. 配置数据库
```bash
# 复制配置文件
cp backend/.env.example backend/.env

# 编辑配置文件，设置数据库连接
vim backend/.env
```

### 启动服务

使用一键启动脚本：

```bash
# Linux/Mac
./start.sh start

# Windows (WSL)
./start.sh start
```

或者手动启动各个服务：

```bash
# 启动 Redis
redis-server

# 启动 Celery Worker
cd backend
celery -A celery_config worker --loglevel=info -Q export,prediction

# 启动后端服务
cd backend
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
├── backend/                      # 后端代码 (FastAPI)
│   ├── app/
│   │   ├── api/                  # API 路由层
│   │   │   ├── auth.py           # 认证
│   │   │   ├── templates.py      # SQL 模板 CRUD
│   │   │   ├── query.py          # SQL 查询执行
│   │   │   ├── prediction.py     # 销售预测
│   │   │   ├── nl2sql.py         # 自然语言转 SQL
│   │   │   ├── config.py         # 前端配置 API
│   │   │   └── ...
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── nl2sql_service.py # NL2SQL 核心逻辑
│   │   │   ├── prediction_service.py
│   │   │   └── ...
│   │   ├── repositories/         # 数据访问层
│   │   ├── models/               # SQLAlchemy 数据模型
│   │   ├── schemas/              # Pydantic 请求/响应模型
│   │   ├── middleware/           # 中间件 (限流/审计)
│   │   ├── core/                 # 核心 (数据库/认证/安全)
│   │   ├── utils/                # 工具函数
│   │   │   ├── llm_client.py     # LLM 客户端 (raw/langchain)
│   │   │   ├── connection_pool_manager.py
│   │   │   └── ...
│   │   ├── tasks/                # Celery 异步任务
│   │   └── main.py               # FastAPI 应用入口
│   ├── prompts/
│   │   └── nl2sql/               # NL2SQL 提示词模板
│   │       ├── system_prompt.md
│   │       └── repair_prompt.md
│   ├── alembic/                  # 数据库迁移
│   ├── tests/                    # 测试代码
│   ├── requirements.txt
│   ├── config.py                 # 配置入口
│   └── celery_config.py          # Celery 配置
├── frontend/                     # 前端代码 (Vue 3)
│   ├── src/
│   │   ├── api/                  # API 调用
│   │   ├── components/           # Vue 组件
│   │   │   ├── EnhancedTable.vue # 增强表格
│   │   │   ├── TableToolbar.vue  # 表格工具栏 (列拖拽排序)
│   │   │   └── ...
│   │   ├── views/                # 页面视图
│   │   │   ├── NL2SQLEditor.vue  # NL2SQL 编辑器
│   │   │   ├── SalesForecast.vue # 销售预测
│   │   │   ├── ForecastResultQuery.vue
│   │   │   └── ...
│   │   ├── store/                # Pinia 状态管理
│   │   └── router/               # 路由配置
│   ├── package.json
│   └── vite.config.js
├── docs/                         # 文档
│   └── plans/                    # 实施计划
│       └── 2026-05-21-langchain-integration-plan.md
├── semantic/                     # 语义层文档 (数据库 Schema 描述)
├── start.sh                      # 一键启动脚本
├── docker-compose.yml            # Docker 部署配置
└── README.md
```

## 使用指南

### 1. 创建 SQL 模板

1. 登录系统
2. 进入"模板管理"页面
3. 点击"新建模板"
4. 填写模板信息：
   - 模板名称
   - 模板描述
   - SQL 语句（支持参数化）
   - 参数定义

### 2. 执行查询

1. 选择已创建的模板
2. 输入查询参数
3. 点击"执行查询"
4. 查看查询结果

### 3. 导出数据

1. 在查询结果页面
2. 点击"导出"按钮
3. 选择导出格式（Excel/PDF）
4. 等待导出完成
5. 下载导出文件

### 4. 模板分享

1. 在模板管理页面
2. 点击"分享"按钮
3. 选择要分享的用户
4. 确认分享

### 5. NL2SQL 自然语言查询

1. 进入"NL2SQL"页面
2. 选择数据源和集团
3. 用自然语言描述查询需求（如"查询上个月销售额 top 10 的商品"）
4. 系统自动生成 SQL 并执行
5. 查看结果，可选择图表展示

### 6. 销售预测

1. 进入"销售预测"页面
2. 选择数据源、门店、物料
3. 设置预测参数（历史天数、预测天数）
4. 点击"训练并预测"
5. 后台异步执行，可在"预测结果查询"查看进��和结果

## 开发指南

### 添加新的 API 端点

1. 在 `backend/app/api/` 中创建新的路由文件
2. 在 `backend/app/main.py` 中注册路由
3. 在 `frontend/src/api/` 中创建对应的 API 调用函数
4. 在前端组件中使用 API

### 添加新的页面

1. 在 `frontend/src/views/` 中创建新的 Vue 组件
2. 在 `frontend/src/router/index.js` 中添加路由
3. 在侧边栏中添加导航菜单

### NL2SQL 开发

提示词模板位置：`backend/prompts/nl2sql/`
- `system_prompt.md`: NL2SQL 系统提示词
- `repair_prompt.md`: SQL 执行失败后的修复提示词

提示词使用 Python `str.format()` 渲染，JSON 示例中的 `{` 必须转义为 `{{`。

修改提示词后无需重启服务，文件修改会自动热加载。

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
NL2SQL_SYSTEM_PROMPT_PATH=prompts/nl2sql/system_prompt.md

# Prediction
PREDICTION_ENABLED=false
PREDICTION_TRAIN_DEFAULT_DAYS=365
PREDICTION_FORECAST_DAYS=30
```

### 运行测试

```bash
# 后端测试
cd backend
pytest

# 运行单个测试文件
pytest tests/test_nl2sql.py

# 生成覆盖率报告
pytest --cov=app --cov-report=html

# 前端测试
cd frontend
npm test
```

## 部署

### Docker 部署（推荐）

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 手动部署

1. 配置生产环境变量
2. 使用 Gunicorn + Uvicorn 部署后端
3. 使用 Nginx 反向代理
4. 配置 HTTPS 证书
5. 设置进程管理（PM2/Systemd）

详细部署指南请参考 [DEPLOYMENT.md](DEPLOYMENT.md)

## 常见问题

### Q: 启动服务时端口被占用怎么办？

A: 可以修改配置文件中的端口号，或者停止占用端口的进程：

```bash
# 查看端口占用
lsof -i :8000

# 停止进程
kill -9 <PID>
```

### Q: NL2SQL 生成 SQL 失败怎么办？

A: 
1. 检查数据源的 schema 语义层文档是否完整
2. 调整 `backend/prompts/nl2sql/system_prompt.md` 中的提示词
3. 查看后端日志确认错误原因

### Q: 预测任务执行失败怎么办？

A: 
1. 确保 Celery Worker 已启动：`./start.sh start` 或手动启动
2. 检查数据源配置是否正确
3. 查看 Celery Worker 日志：`./start.sh logs celery`

### Q: 如何重置数据库？

A: 删除数据库文件并重新创建：

```bash
cd backend
python scripts/reset_database.py
```

### Q: 导出任务失败怎么办？

A: 检查 Celery Worker 日志：

```bash
./start.sh logs celery
```

## 文档

- [快速启动指南](START_GUIDE.md) - 一键启动脚本使用说明
- [系统架构](ARCHITECTURE.md) - 系统架构和技术栈说明
- [API 文档](http://localhost:8000/docs) - FastAPI 自动生成的 API 文档
- [开发文档](docs/) - 详细的开发文档
- [NL2SQL + LangChain 集成计划](docs/plans/2026-05-21-langchain-integration-plan.md)

## 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- 项目主页: https://github.com/yuchen0724/myreport
- 问题反馈: https://github.com/yuchen0724/myreport/issues

## 更新日志

### v1.2.0 (2026-05-21)
- ✨ **NL2SQL + LangChain 架构升级**
  - 新增 LangChain 适配器 (raw / langchain 双模式)
  - 结构化输出支持，Pydantic Schema 驱动
  - 提示词模板外部化 `.md` 文件，支持热更新
  - Schema 语义检索（长 schema 自动筛选）
  - SQL 执行失败后自动修复重试
- ✨ **销售预测增强**
  - 新增 ware_name（商品名称）字段
  - Doris 兼容性修复（元组 IN 改 OR）
- ✨ **前端改进**
  - TableToolbar 列拖拽排序 + 持久化
  - 集团选择器显示 ID 和名称
  - EnhancedTable 递归更新修复
- 🛠 连接池管理器（复用 SQLAlchemy engine）
- 🛠 SQL 参数化防注入

### v1.1.0 (2025-04-22)
- ✨ 添加模板版本控制
- ✨ 添加模板分享功能
- ✨ 添加异步导出功能
- 🐛 修复模板管理按钮无反应问题
- 📝 添加一键启动脚本
- 📝 完善文档

### v1.0.0 (2025-04-21)
- ✨ 初始版本发布
- ✅ 实现基本的模板管理功能
- ✅ 实现查询执行功能
- ✅ 实现数据导出功能
- ✅ 实现用户认证和权限管理

---

**注意**: 本项目正在积极开发中，可能会有 breaking changes。建议在生产环境使用前进行充分测试。
