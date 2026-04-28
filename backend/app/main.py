from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api import auth, data_sources, query, report, nl2sql, charts, templates, stats, async_export, users, cache, audit_logs, dashboard
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.error_handler import register_exception_handlers

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug
)

# 注册异常处理器
register_exception_handlers(app)

# CORS 配置（从环境变量读取，生产环境请限制具体域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流中间件（可通过 rate_limit_enabled 控制开关）
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# 注册路由
app.include_router(auth.router)
app.include_router(data_sources.router)
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


@app.get("/")
async def root():
    return {"message": "Custom Report System API", "version": settings.app_version}


@app.get("/health")
async def health():
    return {"status": "healthy"}
