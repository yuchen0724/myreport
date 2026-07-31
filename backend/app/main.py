import warnings
import logging
import sys
from fastapi import FastAPI

# 配置根日志级别，确保所有模块的 INFO 日志可见
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
    force=True,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text
from app.config import get_settings
from app.core.database import engine
from app.api import auth, data_sources, query, report, nl2sql, charts, templates, stats, async_export, users, cache, audit_logs, dashboard, menus, proxy_servers, config, alerts, drilldown, favorites, semantic_metrics
from app.api import sql_analysis as sql_analysis_api
from app.api import scheduled_reports as scheduled_reports_api
from app.api import model_compare as model_compare_api
from app.api import prediction as prediction_api
from app.api import subscriptions as subscriptions_api
from app.api import pool_metrics as pool_metrics_api
from app.api import sql_reviews as sql_reviews_api
from app.api import dialects as dialects_api
from app.api import ai_analyst as ai_analyst_api
from app.api import rca as rca_api
from app.api import inventory_copilot as inventory_copilot_api
from app.api import ai_design as ai_design_api
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_logging import RequestLoggingMiddleware

settings = get_settings()
logger = logging.getLogger(__name__)
PLACEHOLDER_SECRETS = {
    "changeme",
    "your-secret-key",
    "your-encryption-key",
    "change-me-in-production-please",
    "change-this-secret-key-in-production",
    "change-this-encryption-key-in-production",
}

# --- 启动安全检查 ---
if not settings.debug:
    # 生产环境强制检查
    if settings.secret_key in PLACEHOLDER_SECRETS:
        raise RuntimeError(
            "FATAL: SECRET_KEY is still a default placeholder. "
            "Set SECRET_KEY via environment variable or .env file. "
            "Generate a secure key: openssl rand -hex 32"
        )
    if not settings.password_encryption_key or settings.password_encryption_key in PLACEHOLDER_SECRETS:
        raise RuntimeError(
            "FATAL: PASSWORD_ENCRYPTION_KEY is empty or still a default placeholder. "
            "Set PASSWORD_ENCRYPTION_KEY via environment variable or .env file. "
            "Generate a Fernet key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if not settings.llm_api_key:
        raise RuntimeError(
            "FATAL: LLM_API_KEY is empty. NL2SQL 功能需要配置 LLM_API_KEY。"
            "Set LLM_API_KEY via environment variable or .env file."
        )
else:
    # 开发环境仅警告
    if settings.secret_key in PLACEHOLDER_SECRETS:
        warnings.warn("⚠️  SECRET_KEY 仍使用默认值！生产部署前务必修改。")
    if not settings.password_encryption_key or settings.password_encryption_key in PLACEHOLDER_SECRETS:
        warnings.warn("⚠️  PASSWORD_ENCRYPTION_KEY 为空！生产部署前务必设置。")
    if not settings.llm_api_key:
        warnings.warn("⚠️  LLM_API_KEY 为空！NL2SQL 功能将不可用。")
    if settings.cors_origins == ["http://localhost:5173"]:
        warnings.warn("⚠️  CORS origins 为默认本地配置，请根据实际部署地址修改。")

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
app.add_middleware(GZipMiddleware, minimum_size=4096)

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
app.include_router(drilldown.router)
app.include_router(menus.router)
app.include_router(config.router)
app.include_router(alerts.router)
app.include_router(sql_analysis_api.router)
app.include_router(scheduled_reports_api.router)
app.include_router(model_compare_api.router)
app.include_router(subscriptions_api.router)
app.include_router(favorites.router)
app.include_router(semantic_metrics.router)
app.include_router(sql_reviews_api.router)
app.include_router(pool_metrics_api.router)
app.include_router(dialects_api.router)
app.include_router(ai_analyst_api.router)
app.include_router(rca_api.router)
app.include_router(inventory_copilot_api.router)
app.include_router(ai_design_api.router)
# 预测路由受 prediction_enabled 控制
if settings.prediction_enabled:
    app.include_router(prediction_api.router)
else:
    logger.info("预测功能已禁用（prediction_enabled=False），预测 API 未注册")


# 启动时预加载集团缓存已移除（需手工调用 POST /api/nl2sql/groups/refresh）


@app.get("/")
async def root():
    return {"message": "Custom Report System API", "version": settings.app_version}


@app.get("/health")
async def health():
    return {"status": "healthy", "checks": {"app": "ok"}}


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    checks = {}
    healthy = True

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        healthy = False
        checks["database"] = f"error: {type(exc).__name__}"

    try:
        from app.core.redis import redis_client
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        healthy = False
        checks["redis"] = f"error: {type(exc).__name__}"

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if healthy else "not_ready", "checks": checks},
    )
