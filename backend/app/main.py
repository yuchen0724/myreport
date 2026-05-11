from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.config import get_settings
from app.api import auth, data_sources, query, report, nl2sql, charts, templates, stats, async_export, users, cache, audit_logs, dashboard, menus, proxy_servers, config
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_logging import RequestLoggingMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description="""
## 自定义报表查询系统

支持 SQL 模板管理、参数化查询、数据导出和可视化展示的完整解决方案。

### 核心功能

- **SQL 模板管理** — 模板创建、分享、版本管理
- **参数化查询** — 动态参数、数据源管理
- **数据导出** — Excel/PDF 异步导出
- **NL2SQL** — 自然语言转 SQL 查询
- **可视化图表** — 折线图、柱状图、饼图等

### 认证方式

使用 JWT Token 认证，在请求头中添加：
```
Authorization: Bearer <your_token>
```

### 限流说明

- 查询接口: 30次/分钟
- NL2SQL: 20次/分钟
- 导出接口: 10次/分钟
- 只读接口: 100次/分钟
""",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# 注册异常处理器
register_exception_handlers(app)

# CORS 配置（从环境变量读取，生产环境请限制具体域名）
# 如果设置了 cors_origins_prod 则使用生产环境配置
if settings.cors_origins_prod:
    cors_origins = [o.strip() for o in settings.cors_origins_prod.split(",") if o.strip()]
else:
    cors_origins = settings.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip 压缩中间件（对大响应进行压缩）
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 请求日志和性能监控中间件
app.add_middleware(RequestLoggingMiddleware)

# 限流中间件（可通过 rate_limit_enabled 控制开关）
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# 审计日志中间件
app.add_middleware(AuditLogMiddleware)

# 注册路由
app.include_router(auth.router)
app.include_router(data_sources.router)
app.include_router(proxy_servers.router)
app.include_router(query.router)
app.include_router(report.router)
app.include_router(nl2sql.router)
app.include_router(charts.router)
app.include_router(templates.router)
app.include_router(stats.router)
app.include_router(async_export.router)
app.include_router(users.router)
app.include_router(cache.router)
app.include_router(audit_logs.router)
app.include_router(dashboard.router)
app.include_router(menus.router)
app.include_router(config.router)


@app.get("/")
async def root():
    return {"message": "Custom Report System API", "version": settings.app_version}


@app.get("/health")
async def health():
    return {"status": "healthy"}
