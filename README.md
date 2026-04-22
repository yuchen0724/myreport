# 自定义报表查询系统

基于 Python FastAPI + Vue 3 + Element Plus 的自定义报表查询系统。

## 技术栈

### 后端
- Python 3.12
- FastAPI
- PostgreSQL
- Redis
- Celery
- SQLAlchemy

### 前端
- Vue 3
- Element Plus
- Axios
- Vue Router

## 功能特性

### 第一阶段：基础功能
- ✅ 用户认证
- ✅ 数据源管理
- ✅ SQL 查询编辑器
- ✅ 查询历史记录
- ✅ 基础报表导出

### 第二阶段：高级功能
- ✅ NL2SQL 智能查询
- ✅ 图表可视化
- ✅ 模板管理
- ✅ PDF/Excel 导出
- ✅ 统计分析

### 第三阶段：企业级功能
- ✅ 异步导出
  - 支持大数据量异步导出
  - 实时任务进度跟踪
  - 自动重试机制
- ✅ 模板分享
  - 模板分享给其他用户
  - 查看分享的模板
  - 权限控制
- ✅ 版本控制
  - 模板版本历史
  - 版本对比
  - 版本回滚
- ✅ 性能优化
  - 查询结果缓存
  - SQL 查询优化
  - API 限流

## 快速开始

### 环境要求
- Python 3.12+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+

### 后端启动
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 前端启动
```bash
cd frontend
npm install
npm run dev
```

### 启动 Celery Worker
```bash
cd backend
celery -A celery_config worker --loglevel=info
```

## 文档

- [异步导出使用指南](docs/async-export-guide.md)
- [模板分享使用指南](docs/template-sharing-guide.md)
- [性能优化指南](docs/performance-optimization-guide.md)

## 许可证

MIT License
