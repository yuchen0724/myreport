"""连接池监控指标 Schema"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PoolMetricsResponse(BaseModel):
    """单个数据源连接池指标"""
    data_source_id: int
    data_source_name: str
    data_source_type: str
    active_connections: int = 0
    idle_connections: int = 0
    waiting_queue_length: int = 0
    avg_query_time_ms: float = 0.0
    pool_size: int = 0
    max_overflow: int = 0
    total_connections: int = 0
    checked_out: int = 0
    checked_in: int = 0
    overflow: int = 0
    is_active: bool = False
    timestamp: Optional[datetime] = None


class PoolMetricsHistory(BaseModel):
    """连接池指标历史记录"""
    data_source_id: int
    metrics: List[PoolMetricsResponse]


class AllPoolMetricsResponse(BaseModel):
    """所有数据源的连接池指标"""
    pools: List[PoolMetricsResponse]
    total_active: int = 0
    total_idle: int = 0
    total_waiting: int = 0
    timestamp: Optional[datetime] = None
