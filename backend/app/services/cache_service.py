"""缓存服务 - 用于缓存查询结果"""

import json
import hashlib
from typing import Optional, Any, Dict
from datetime import datetime
from app.config import get_settings

settings = get_settings()


class CacheService:
    """缓存服务 - 使用Redis作为缓存后端"""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        if redis_client is None:
            self._init_redis()

    def _init_redis(self):
        """初始化Redis客户端"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True
            )
            self.redis_client.ping()
        except Exception as e:
            print(f"Redis连接失败: {e}")
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
            return None
        try:
            cache_key = self._generate_cache_key(sql, params)
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"缓存读取失败: {e}")
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
            return True
        except Exception as e:
            print(f"缓存写入失败: {e}")
            return False

    def delete(self, sql: str, params: dict = None) -> bool:
        """删除缓存"""
        if not self.redis_client:
            return False
        try:
            cache_key = self._generate_cache_key(sql, params)
            self.redis_client.delete(cache_key)
            return True
        except Exception as e:
            print(f"缓存删除失败: {e}")
            return False

    def exists(self, sql: str, params: dict = None) -> bool:
        """检查缓存是否存在"""
        if not self.redis_client:
            return False
        try:
            cache_key = self._generate_cache_key(sql, params)
            return bool(self.redis_client.exists(cache_key))
        except Exception as e:
            print(f"缓存检查失败: {e}")
            return False

    def clear_pattern(self, pattern: str) -> bool:
        """根据模式清除缓存"""
        if not self.redis_client:
            return False
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            print(f"批量缓存删除失败: {e}")
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
