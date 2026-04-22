from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api import auth, data_sources, query, report, nl2sql, charts, templates, stats, async_export, users
from app.middleware.rate_limit import rate_limit_middleware

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流中间件（临时禁用）
# app.add_middleware(rate_limit_middleware)

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


@app.get("/")
async def root():
    return {"message": "Custom Report System API", "version": settings.app_version}


@app.get("/health")
async def health():
    return {"status": "healthy"}
