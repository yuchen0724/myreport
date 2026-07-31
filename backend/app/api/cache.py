"""缓存管理API"""

from fastapi import APIRouter, Depends, HTTPException
from app.core.auth_deps import get_current_admin_user
from app.models.user import User
from app.services.cache_service import cache_service

router = APIRouter(prefix="/api/cache", tags=["缓存管理"])


@router.get("/stats")
async def get_cache_stats(
    current_user: User = Depends(get_current_admin_user),
):
    """获取缓存统计信息"""
    stats = cache_service.get_stats()
    return stats


@router.post("/clear")
async def clear_cache(
    current_user: User = Depends(get_current_admin_user),
):
    """仅清除查询结果缓存，不允许传入任意 Redis 键模式。"""
    pattern = "query_result:*"
    success = cache_service.clear_pattern(pattern)
    if success:
        return {"success": True, "message": f"已清除匹配模式 '{pattern}' 的缓存"}
    else:
        raise HTTPException(status_code=500, detail="缓存清除失败")


@router.delete("/query")
async def delete_query_cache(
    sql: str,
    params: dict = None,
    current_user: User = Depends(get_current_admin_user),
):
    """删除特定查询的缓存
    
    Args:
        sql: SQL语句
        params: 查询参数
    """
    success = cache_service.delete(sql, params)
    if success:
        return {"success": True, "message": "缓存已删除"}
    else:
        raise HTTPException(status_code=500, detail="缓存删除失败")
