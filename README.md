# 自定义报表查询系统

一个功能强大的自定义报表查询系统，支持 SQL 模板管理、参数化查询、数据导出和可视化展示。

## 功能特性

- ✅ **SQL 模板管理** - 创建、编辑、删除和管理 SQL 查询模板
- ✅ **参数化查询** - 支持动态参数和日期范围查询
- ✅ **数据导出** - 支持 Excel、PDF 等多种格式导出
- ✅ **异步处理** - 使用 Celery 处理长时间运行的导出任务
- ✅ **版本控制** - 模板版本管理和回滚功能
- ✅ **模板分享** - 支持模板分享给其他用户
- ✅ **数据可视化** - 图表展示和数据透视
- ✅ **权限管理** - 基于角色的访问控制

## 技术栈

### 前端
- Vue 3 (Composition API)
- Element Plus
- Pinia
- Vue Router
- Axios
- Vite

### 后端
- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- Celery
- Apache Doris / Hive

## 快速开始

### 前置要求

- Node.js 16+
- Python 3.9+
- Redis 6+
- PostgreSQL 12+

### 安装

1. 克隆项目
```bash
git clone <repository-url>
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

# Windows
start.bat start
```

或者手动启动各个服务：

```bash
# 启动 Redis
redis-server

# 启动 Celery Worker
cd backend
celery -A celery_config worker --loglevel=info

# 启动后端服务
cd backend
uvicorn app.main:app --reload

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
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/             # API 路由
│   │   ├── models/          # 数据模型
│   │   ├── schemas/         # Pydantic 模式
│   │   ├── services/        # 业务逻辑
│   │   └── main.py          # FastAPI 应用
│   ├── tests/               # 测试代码
│   ├── requirements.txt     # Python 依赖
│   └── celery_config.py     # Celery 配置
├── frontend/                # 前端代码
│   ├── src/
│   │   ├── api/             # API 调用
│   │   ├── components/      # Vue 组件
│   │   ├── views/           # 页面视图
│   │   ├── store/           # Pinia 状态管理
│   │   └── router/          # 路由配置
│   ├── package.json         # Node 依赖
│   └── vite.config.js       # Vite 配置
├── docs/                    # 文档
│   └── superpowers/         # Superpowers 规格文档
├── logs/                    # 日志文件
├── start.sh                 # Linux/Mac 启动脚本
├── start.bat                # Windows 启动脚本
└── README.md                # 项目说明
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

### 运行测试

```bash
# 后端测试
cd backend
pytest

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

## 文档

- [快速启动指南](START_GUIDE.md) - 一键启动脚本使用说明
- [系统架构](ARCHITECTURE.md) - 系统架构和技术栈说明
- [API 文档](http://localhost:8000/docs) - FastAPI 自动生成的 API 文档
- [开发文档](docs/) - 详细的开发文档

## 常见问题

### Q: 启动服务时端口被占用怎么办？

A: 可以修改配置文件中的端口号，或者停止占用端口的进程：

```bash
# 查看端口占用
lsof -i :8000

# 停止进程
kill -9 <PID>
```

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

- 项目主页: [GitHub Repository]
- 问题反馈: [GitHub Issues]
- 邮箱: [your-email@example.com]

## 更新日志

### v1.0.0 (2025-04-21)
- ✨ 初始版本发布
- ✅ 实现基本的模板管理功能
- ✅ 实现查询执行功能
- ✅ 实现数据导出功能
- ✅ 实现用户认证和权限管理

### v1.1.0 (2025-04-22)
- ✨ 添加模板版本控制
- ✨ 添加模板分享功能
- ✨ 添加异步导出功能
- 🐛 修复模板管理按钮无反应问题
- 📝 添加一键启动脚本
- 📝 完善文档

---

**注意**: 本项目正在积极开发中，可能会有 breaking changes。建议在生产环境使用前进行充分测试。
