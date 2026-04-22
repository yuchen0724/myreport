# backend/app/services/cache_service.py
import json
from typing import Optional, Any
import redis
import os

class CacheService:
    def __init__(self):
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_db = int(os.getenv('REDIS_DB', 0))

        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None

    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存"""
        try:
            return self.redis_client.setex(
                key,
                expire,
                json.dumps(value)
            )
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            return self.redis_client.delete(key) > 0
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return self.redis_client.exists(key) > 0
        except Exception:
            return False

    def generate_query_key(self, data_source_id: int, sql: str, params: dict) -> str:
        """生成查询缓存键"""
        import hashlib
        key_str = f"query:{data_source_id}:{sql}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def generate_template_key(self, template_id: int) -> str:
        """生成模板缓存键"""
        return f"template:{template_id}"

    def clear_query_cache(self, data_source_id: Optional[int] = None) -> int:
        """清除查询缓存"""
        try:
            if data_source_id:
                pattern = f"query:{data_source_id}:*"
            else:
                pattern = "query:*"

            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception:
            return 0

    def clear_template_cache(self, template_id: Optional[int] = None) -> int:
        """清除模板缓存"""
        try:
            if template_id:
                pattern = f"template:{template_id}"
            else:
                pattern = "template:*"

            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception:
            return 0

# 全局缓存实例
cache_service = CacheService()
