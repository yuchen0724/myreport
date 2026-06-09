---
name: api-doc-generator
description: API 文档生成 — 根据 FastAPI 路由自动生成或更新 API 文档
user_invocable: true
---

# API 文档生成

根据 `backend/app/api/` 下的路由文件生成 API 文档。

## 后端 API 路由前缀映射

| 路由 | 模块 | 说明 |
|------|------|------|
| `/api/auth` | auth.py | 登录/用户信息 |
| `/api/templates` | templates.py | SQL 模板 CRUD + 分享 + 版本回滚 |
| `/api/query` | query.py | SQL 查询执行 + 历史记录 |
| `/api/datasources` | data_sources.py | 数据源管理 |
| `/api/proxy-servers` | proxy_servers.py | 代理服务器管理 |
| `/api/nl2sql` | nl2sql.py | 自然语言转 SQL |
| `/api/sql` | sql_analysis.py | SQL 分析 |
| `/api/charts` | charts.py | 图表数据 |
| `/api/report` | report.py | 报表生成 (Excel/PDF) |
| `/api/async-export` | async_export.py | 异步导出 |
| `/api/prediction` | prediction.py | 销售预测 |
| `/api/rca` | rca.py | RCA 根因分析 |
| `/api/ai-analyst` | ai_analyst.py | AI 数据分析师 |
| `/api/dashboard` | dashboard.py | 仪表盘 |
| `/api/drilldown` | drilldown.py | 数据下钻 |
| `/api/favorites` | favorites.py | 收藏夹 |
| `/api/subscriptions` | subscriptions.py | 订阅推送 |
| `/api/scheduled-reports` | scheduled_reports.py | 定时报表 |
| `/api/metrics` | pool_metrics.py | 连接池监控 |
| `/api/alerts` | alerts.py | 告警通知 |
| `/api/users` | users.py | 用户管理 |
| `/api/audit-logs` | audit_logs.py | 审计日志 |

## 文档生成格式

为每个 API 端点生成以下信息：
- **路径**: HTTP 方法 + URL
- **描述**: 功能说明
- **请求参数**: Query / Path / Body 参数
- **响应格式**: 成功/错误响应示例
- **权限**: 需要的角色/权限
- **速率限制**: 是否有限流
