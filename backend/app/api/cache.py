"""缓存管理API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.services.cache_service import cache_service

router = APIRouter(prefix="/api/cache", tags=["缓存管理"])


@router.get("/stats")
async def get_cache_stats(
    current_user_id: int = Depends(get_current_user_id)
):
    """获取缓存统计信息"""
    stats = cache_service.get_stats()
    return stats


@router.post("/clear")
async def clear_cache(
    pattern: str = "query_result:*",
    current_user_id: int = Depends(get_current_user_id)
):
    """清除缓存
    
    Args:
        pattern: 缓存键模式，默认清除所有查询结果缓存
    """
    success = cache_service.clear_pattern(pattern)
    if success:
        return {"success": True, "message": f"已清除匹配模式 '{pattern}' 的缓存"}
    else:
        raise HTTPException(status_code=500, detail="缓存清除失败")


@router.delete("/query")
async def delete_query_cache(
    sql: str,
    params: dict = None,
    current_user_id: int = Depends(get_current_user_id)
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
