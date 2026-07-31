"""缓存服务 - 用于缓存查询结果"""

import json
import hashlib
import logging
import threading
import time
from typing import Optional, Any, Dict
from datetime import datetime
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class CacheStats:
    """缓存统计"""
    def __init__(self):
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.evictions = 0
        self._start_time = time.time()
    
    def record_hit(self):
        with self._lock:
            self.hits += 1
    
    def record_miss(self):
        with self._lock:
            self.misses += 1
    
    def record_set(self):
        with self._lock:
            self.sets += 1
    
    def record_eviction(self):
        with self._lock:
            self.evictions += 1
    
    def get_stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "sets": self.sets,
                "hit_rate_percent": round(hit_rate, 2),
                "uptime_seconds": round(time.time() - self._start_time, 2)
            }
    
    def reset(self):
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.sets = 0
            self.evictions = 0


class CacheService:
    """缓存服务 - 使用Redis作为缓存后端"""
    
    # 基于数据源的默认 TTL（秒）
    DEFAULT_TTL_BY_SOURCE = {
        "DORIS": 300,      # 5分钟
        "HIVE": 600,      # 10分钟
        "MYSQL": 300,     # 5分钟
        "POSTGRESQL": 300,
    }

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.stats = CacheStats()
        if redis_client is None:
            self._init_redis()

    def _init_redis(self):
        """初始化Redis客户端（带连接池）"""
        try:
            import redis
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
            logger.warning("Redis连接失败: %s", e)
            self.redis_client = None

    def _generate_cache_key(self, sql: str, params: dict = None) -> str:
        """生成缓存键"""
        cache_data = {
            "sql": sql,
            "params": params or {}
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return f"query_result:{hashlib.md5(cache_str.encode()).hexdigest()}"

    def get(self, sql: str, params: dict = None) -> Optional[dict]:
        """从缓存获取查询结果"""
        if not self.redis_client:
            self.stats.record_miss()
            return None
        try:
            cache_key = self._generate_cache_key(sql, params)
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.stats.record_hit()
                return json.loads(cached_data)
            self.stats.record_miss()
            return None
        except Exception as e:
            logger.warning("缓存读取失败: %s", e)
            self.stats.record_miss()
            return None

    def set(self, sql: str, result: dict, params: dict = None, ttl: int = 300) -> bool:
        """将查询结果存入缓存"""
        if not self.redis_client:
            return False
        try:
            cache_key = self._generate_cache_key(sql, params)
            cached_data = {
                "result": result,
                "cached_at": datetime.now().isoformat(),
                "ttl": ttl
            }
            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(cached_data)
            )
            self.stats.record_set()
            return True
        except Exception as e:
            logger.warning("缓存写入失败: %s", e)
            return False
    
    def get_stats_extended(self) -> dict:
        """获取扩展缓存统计信息"""
        base_stats = self.stats.get_stats()
        redis_stats = self.get_stats()
        return {**base_stats, "redis": redis_stats}

    def delete(self, sql: str, params: dict = None) -> bool:
        """删除缓存"""
        if not self.redis_client:
            return False
        try:
            cache_key = self._generate_cache_key(sql, params)
            self.redis_client.delete(cache_key)
            return True
        except Exception as e:
            logger.warning("缓存删除失败: %s", e)
            return False

    def exists(self, sql: str, params: dict = None) -> bool:
        """检查缓存是否存在"""
        if not self.redis_client:
            return False
        try:
            cache_key = self._generate_cache_key(sql, params)
            return bool(self.redis_client.exists(cache_key))
        except Exception as e:
            logger.warning("缓存检查失败: %s", e)
            return False

    def clear_pattern(self, pattern: str) -> bool:
        """清除查询缓存命名空间，拒绝操作其他 Redis 业务键。"""
        if not self.redis_client:
            return False
        if pattern != "query_result:*":
            logger.warning("拒绝清除非查询缓存命名空间: %s", pattern)
            return False
        try:
            batch = []
            for key in self.redis_client.scan_iter(match=pattern, count=500):
                batch.append(key)
                if len(batch) >= 500:
                    self.redis_client.delete(*batch)
                    batch.clear()
            if batch:
                self.redis_client.delete(*batch)
            return True
        except Exception as e:
            logger.warning("批量缓存删除失败: %s", e)
            return False

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        if not self.redis_client:
            return {"status": "disconnected"}
        try:
            info = self.redis_client.info()
            query_keys = self.redis_client.keys("query_result:*")
            return {
                "status": "connected",
                "total_keys": info.get("db0", {}).get("keys", 0),
                "query_cache_count": len(query_keys),
                "memory_used": info.get("used_memory_human", "N/A")
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# 全局缓存服务实例
cache_service = CacheService()


class FullCacheService(CacheService):
    """全量缓存服务 - 用于缓存完整查询结果供分页使用"""
    
    def get_full(self, sql_key: str, params: dict = None) -> Optional[dict]:
        """从缓存获取全量查询结果"""
        if not self.redis_client:
            self.stats.record_miss()
            return None
        try:
            # 使用特殊的前缀来区分全量缓存
            full_key = f"query_full:{sql_key}"
            cached_data = self.redis_client.get(full_key)
            if cached_data:
                self.stats.record_hit()
                return json.loads(cached_data)
            self.stats.record_miss()
            return None
        except Exception as e:
            logger.warning("全量缓存读取失败: %s", e)
            self.stats.record_miss()
            return None
    
    def set_full(self, sql_key: str, result: dict, params: dict = None, ttl: int = 300) -> bool:
        """将全量查询结果存入缓存"""
        if not self.redis_client:
            return False
        try:
            full_key = f"query_full:{sql_key}"
            cached_data = {
                "result": result,
                "cached_at": datetime.now().isoformat(),
                "ttl": ttl
            }
            self.redis_client.setex(
                full_key,
                ttl,
                json.dumps(cached_data)
            )
            self.stats.record_set()
            return True
        except Exception as e:
            logger.warning("全量缓存写入失败: %s", e)
            return False


# 全量缓存服务实例
full_cache_service = FullCacheService()
