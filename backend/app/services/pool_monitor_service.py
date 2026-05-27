"""连接池监控服务 - 收集和缓存连接池指标"""

import json
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict
from threading import Lock
from sqlalchemy.orm import Session

from app.utils.connection_pool_manager import ConnectionPoolManager
from app.models.data_source import DataSource
from app.schemas.pool_metrics import PoolMetricsResponse, AllPoolMetricsResponse

logger = logging.getLogger(__name__)


class PoolMonitorService:
    """连接池监控服务"""

    def __init__(self, db: Session):
        self.db = db
        self.pool_manager = ConnectionPoolManager()
        self._query_times: Dict[int, List[float]] = {}
        self._query_lock = Lock()

    def record_query_time(self, ds_id: int, elapsed_ms: float):
        """记录查询耗时（用于计算平均查询时间）"""
        with self._query_lock:
            if ds_id not in self._query_times:
                self._query_times[ds_id] = []
            self._query_times[ds_id].append(elapsed_ms)
            # 只保留最近100条
            if len(self._query_times[ds_id]) > 100:
                self._query_times[ds_id] = self._query_times[ds_id][-100:]

    def _get_avg_query_time(self, ds_id: int) -> float:
        """获取指定数据源的平均查询时间"""
        with self._query_lock:
            times = self._query_times.get(ds_id, [])
            if not times:
                return 0.0
            return round(sum(times) / len(times), 2)

    def _build_metrics(self, ds: DataSource, pool, is_active: bool) -> PoolMetricsResponse:
        """构建连接池指标响应"""
        if pool is None:
            return PoolMetricsResponse(
                data_source_id=ds.id,  # type: ignore
                data_source_name=ds.name,  # type: ignore
                data_source_type=ds.type,  # type: ignore
                active_connections=0,
                idle_connections=0,
                waiting_queue_length=0,
                avg_query_time_ms=self._get_avg_query_time(ds.id),  # type: ignore
                pool_size=0,
                max_overflow=0,
                total_connections=0,
                checked_out=0,
                checked_in=0,
                overflow=0,
                is_active=False,
                timestamp=datetime.now(),
            )

        try:
            pool_obj = pool
            pool_size = pool_obj.size()
            checkedout = pool_obj.checkedout()
            checkedin = pool_obj.checkedin()
            overflow_val = pool_obj.overflow()

            active_connections = checkedout
            idle_connections = checkedin
            max_overflow_val = getattr(pool_obj, '_max_overflow', 10) if hasattr(pool_obj, '_max_overflow') else 10
            total_connections = pool_size + overflow_val
            waiting_queue = 0

            return PoolMetricsResponse(
                data_source_id=ds.id,  # type: ignore
                data_source_name=ds.name,  # type: ignore
                data_source_type=ds.type,  # type: ignore
                active_connections=active_connections,
                idle_connections=idle_connections,
                waiting_queue_length=waiting_queue,
                avg_query_time_ms=self._get_avg_query_time(ds.id),  # type: ignore
                pool_size=pool_size,
                max_overflow=max_overflow_val,
                total_connections=total_connections,
                checked_out=checkedout,
                checked_in=checkedin,
                overflow=overflow_val,
                is_active=is_active,
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.warning(f"获取连接池指标失败 (ds_id={ds.id}): {e}")  # type: ignore
            return PoolMetricsResponse(
                data_source_id=ds.id,  # type: ignore
                data_source_name=ds.name,  # type: ignore
                data_source_type=ds.type,  # type: ignore
                active_connections=0,
                idle_connections=0,
                waiting_queue_length=0,
                avg_query_time_ms=self._get_avg_query_time(ds.id),  # type: ignore
                pool_size=0,
                max_overflow=0,
                total_connections=0,
                checked_out=0,
                checked_in=0,
                overflow=0,
                is_active=False,
                timestamp=datetime.now(),
            )

    def get_metrics(self, ds_id: int) -> Optional[PoolMetricsResponse]:
        """获取指定数据源的连接池指标"""
        ds = self.db.query(DataSource).filter(DataSource.id == ds_id).first()
        if not ds:
            return None

        # 检查连接池是否在缓存中
        engines = ConnectionPoolManager._engines
        cached = engines.get(ds_id)

        if cached is None:
            return self._build_metrics(ds, None, False)

        return self._build_metrics(ds, cached.engine.pool, True)

    def get_all_metrics(self) -> AllPoolMetricsResponse:
        """获取所有已激活连接池的指标"""
        pools: List[PoolMetricsResponse] = []
        engines = ConnectionPoolManager._engines

        for ds_id in list(engines.keys()):
            metrics = self.get_metrics(ds_id)
            if metrics:
                pools.append(metrics)

        # 同时列出数据库中所有数据源（未建立连接池的显示为未激活）
        all_ds = self.db.query(DataSource).filter(DataSource.is_active == True).all()  # type: ignore
        active_ids = {p.data_source_id for p in pools}
        for ds in all_ds:
            if ds.id not in active_ids:  # type: ignore
                pools.append(self._build_metrics(ds, None, False))

        total_active = sum(p.active_connections for p in pools)
        total_idle = sum(p.idle_connections for p in pools)
        total_waiting = sum(p.waiting_queue_length for p in pools)

        return AllPoolMetricsResponse(
            pools=pools,
            total_active=total_active,
            total_idle=total_idle,
            total_waiting=total_waiting,
            timestamp=datetime.now(),
        )


class PoolMetricsCache:
    """Redis 缓存管理器，用于缓存连接池指标"""

    REDIS_KEY_PREFIX = "pool_metrics:"
    DEFAULT_TTL = 10  # 10秒缓存

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        if redis_client is None:
            self._init_redis()

    def _init_redis(self):
        """初始化Redis客户端"""
        try:
            import redis
            from app.config import get_settings
            settings = get_settings()
            pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                max_connections=settings.redis_pool_size,
                decode_responses=True,
                socket_keepalive=True,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
            self.redis_client = redis.Redis(connection_pool=pool)
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis连接失败，使用内存缓存: {e}")
            self.redis_client = None

    def _get_key(self, ds_id: int) -> str:
        return f"{self.REDIS_KEY_PREFIX}{ds_id}"

    def _get_all_key(self) -> str:
        return f"{self.REDIS_KEY_PREFIX}all"

    def get(self, ds_id: int) -> Optional[dict]:
        """从缓存获取指标"""
        if not self.redis_client:
            return None
        try:
            data = self.redis_client.get(self._get_key(ds_id))
            if data:
                return json.loads(str(data))
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")
        return None

    def set(self, ds_id: int, metrics: dict, ttl: int = None):
        """缓存指标"""
        if not self.redis_client:
            return
        try:
            ttl = ttl or self.DEFAULT_TTL
            self.redis_client.setex(
                self._get_key(ds_id),
                ttl,
                json.dumps(metrics, default=str)
            )
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")

    def get_all(self) -> Optional[dict]:
        """从缓存获取所有指标"""
        if not self.redis_client:
            return None
        try:
            data = self.redis_client.get(self._get_all_key())
            if data:
                return json.loads(str(data))
        except Exception as e:
            logger.warning(f"Redis读取失败: {e}")
        return None

    def set_all(self, metrics: dict, ttl: int = None):
        """缓存所有指标"""
        if not self.redis_client:
            return
        try:
            ttl = ttl or self.DEFAULT_TTL
            self.redis_client.setex(
                self._get_all_key(),
                ttl,
                json.dumps(metrics, default=str)
            )
        except Exception as e:
            logger.warning(f"Redis写入失败: {e}")

    def invalidate(self, ds_id: int):
        """清除指定数据源的缓存"""
        if not self.redis_client:
            return
        try:
            self.redis_client.delete(self._get_key(ds_id))
        except Exception as e:
            logger.warning(f"Redis删除失败: {e}")

    def invalidate_all(self):
        """清除所有连接池指标缓存"""
        if not self.redis_client:
            return
        try:
            keys = self.redis_client.keys(f"{self.REDIS_KEY_PREFIX}*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis批量删除失败: {e}")
