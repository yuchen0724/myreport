"""连接池监控 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.pool_metrics import PoolMetricsResponse, AllPoolMetricsResponse
from app.services.pool_monitor_service import PoolMonitorService, PoolMetricsCache

router = APIRouter(prefix="/api/metrics", tags=["连接池监控"])

# Redis 缓存实例
_metrics_cache = PoolMetricsCache()


@router.get("/pool/{data_source_id}", response_model=PoolMetricsResponse)
async def get_pool_metrics(
    data_source_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取指定数据源的连接池指标"""
    # 尝试从 Redis 缓存获取
    cached = _metrics_cache.get(data_source_id)
    if cached:
        return PoolMetricsResponse(**cached)

    # 获取实时指标
    monitor_service = PoolMonitorService(db)
    metrics = monitor_service.get_metrics(data_source_id)
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )

    # 缓存到 Redis
    _metrics_cache.set(data_source_id, metrics.model_dump(mode="json"))

    return metrics


@router.get("/pool", response_model=AllPoolMetricsResponse)
async def get_all_pool_metrics(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取所有数据源的连接池指标"""
    # 尝试从 Redis 缓存获取
    cached = _metrics_cache.get_all()
    if cached:
        return AllPoolMetricsResponse(**cached)

    # 获取实时指标
    monitor_service = PoolMonitorService(db)
    result = monitor_service.get_all_metrics()

    # 缓存到 Redis
    _metrics_cache.set_all(result.model_dump(mode="json"))

    return result
