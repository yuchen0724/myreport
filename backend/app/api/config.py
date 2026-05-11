"""
前端配置 API - 返回前端需要的配置项
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth_deps import get_current_user_id

from app.config import get_settings

router = APIRouter(prefix="/api/config", tags=["config"])


class FrontendConfigResponse(BaseModel):
    """前端配置响应"""
    nl2sql_timeout: int  # NL2SQL 超时时间（秒）
    nl2sql_timeout_ms: int  # NL2SQL 超时时间（毫秒，前端直接用）


# 缓存配置，避免每次都读取
_cached_config = None


@router.get("", response_model=FrontendConfigResponse)
async def get_frontend_config(current_user_id: int = Depends(get_current_user_id)):
    """
    获取前端配置
    
    返回前端需要的配置项，包括 NL2SQL 超时时间等
    """
    global _cached_config
    if _cached_config is None:
        settings = get_settings()
        _cached_config = FrontendConfigResponse(
            nl2sql_timeout=settings.nl2sql_timeout,
            nl2sql_timeout_ms=settings.nl2sql_timeout * 1000 + 60000  # 后端超时 + 60秒缓冲
        )
    return _cached_config
