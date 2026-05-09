"""NL2SQL Redis Cache Module.

Provides caching for NL2SQL query results to improve performance.
"""
import hashlib
import json
import logging
from typing import Optional, Dict, Any

import redis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)


class NL2SQLCache:
    """Redis-based cache for NL2SQL query results.
    
    Features:
    - Lazy Redis connection initialization
    - Graceful degradation on Redis failures
    - Configurable TTL
    - MD5-based cache key generation
    
    Example:
        cache = NL2SQLCache()
        
        # Get cached SQL
        result = cache.get("show all users", data_source_id=1)
        
        # Set cache
        cache.set(
            question="show all users",
            data_source_id=1,
            sql="SELECT * FROM users",
            explanation="Retrieves all user records"
        )
    """
    
    def __init__(self, ttl: Optional[int] = None):
        """Initialize cache with optional custom TTL.
        
        Args:
            ttl: Cache TTL in seconds. Defaults to config.nl2sql_cache_ttl (3600).
        """
        settings = get_settings()
        self.ttl = ttl or settings.nl2sql_cache_ttl
        self._redis_client: Optional[redis.Redis] = None
        self._connection_failed = False
        
    def _get_redis(self) -> Optional[redis.Redis]:
        """Lazy-load Redis connection.
        
        Returns:
            Redis client instance or None if connection failed.
        """
        if self._redis_client is not None:
            return self._redis_client
            
        if self._connection_failed:
            return None
            
        try:
            settings = get_settings()
            
            # Use redis_url if configured, otherwise use individual settings
            if settings.redis_url:
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
            else:
                self._redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
            
            # Test connection
            self._redis_client.ping()
            logger.debug("Redis connection established for NL2SQL cache")
            return self._redis_client
            
        except (RedisError, ConnectionError, Exception) as e:
            logger.warning(f"Redis connection failed, caching disabled: {e}")
            self._connection_failed = True
            self._redis_client = None
            return None
    
    def _hash_question(self, question: str, data_source_id: int) -> str:
        """Generate cache key hash from question and data source.
        
        Args:
            question: The natural language question
            data_source_id: The data source identifier
            
        Returns:
            16-character MD5 hash string
        """
        # Normalize question: lowercase and strip whitespace
        normalized_question = question.lower().strip()
        key = f"{data_source_id}:{normalized_question}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()[:16]
    
    def _make_cache_key(self, question: str, data_source_id: int) -> str:
        """Create full Redis cache key.
        
        Args:
            question: The natural language question
            data_source_id: The data source identifier
            
        Returns:
            Redis key in format: nl2sql:{hash}
        """
        hash_key = self._hash_question(question, data_source_id)
        return f"nl2sql:{hash_key}"
    
    def get(self, question: str, data_source_id: int) -> Optional[Dict[str, Any]]:
        """Get cached SQL result.
        
        Args:
            question: The natural language question
            data_source_id: The data source identifier
            
        Returns:
            Cached result dict with keys: sql, explanation, confidence
            or None if not found or on error
        """
        try:
            client = self._get_redis()
            if client is None:
                return None
            
            cache_key = self._make_cache_key(question, data_source_id)
            cached_value = client.get(cache_key)
            
            if cached_value is None:
                logger.debug(f"Cache miss for question: {question[:50]}...")
                return None
            
            result = json.loads(cached_value)
            logger.debug(f"Cache hit for question: {question[:50]}...")
            return result
            
        except (RedisError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Cache get failed, returning None: {e}")
            return None
    
    def set(
        self,
        question: str,
        data_source_id: int,
        sql: str,
        explanation: Optional[str] = None,
        confidence: float = 0.9
    ) -> bool:
        """Set cache for a NL2SQL result.
        
        Args:
            question: The natural language question
            data_source_id: The data source identifier
            sql: The generated SQL query
            explanation: Optional explanation of the SQL
            confidence: Confidence score (default 0.9)
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            client = self._get_redis()
            if client is None:
                return False
            
            cache_key = self._make_cache_key(question, data_source_id)
            
            cache_value = {
                "sql": sql,
                "explanation": explanation,
                "confidence": confidence
            }
            
            client.setex(
                cache_key,
                self.ttl,
                json.dumps(cache_value, ensure_ascii=False)
            )
            
            logger.debug(f"Cached SQL for question: {question[:50]}...")
            return True
            
        except (RedisError, json.JSONEncodeError, Exception) as e:
            logger.warning(f"Cache set failed: {e}")
            return False
    
    def invalidate(self, data_source_id: int) -> bool:
        """Invalidate all cached entries for a data source.
        
        Note: This scans all keys with prefix 'nl2sql:' which may be slow
        if there are many cached entries. Consider using Redis SCAN
        for large-scale invalidation.
        
        Args:
            data_source_id: The data source identifier
            
        Returns:
            True if invalidation succeeded, False otherwise
        """
        try:
            client = self._get_redis()
            if client is None:
                return False
            
            # Find all nl2sql keys
            # Note: KEYS can be slow on large datasets, consider SCAN for production
            pattern = "nl2sql:*"
            keys = client.keys(pattern)
            
            if not keys:
                logger.debug("No cache keys to invalidate")
                return True
            
            # We need to check each key's value to match data_source_id
            # Since we only have hash in key, we need a different approach
            # For now, delete all nl2sql cache entries
            deleted = client.delete(*keys)
            logger.info(f"Invalidated {deleted} NL2SQL cache entries for data source {data_source_id}")
            return True
            
        except RedisError as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return False
    
    def invalidate_all(self) -> bool:
        """Invalidate all NL2SQL cache entries.
        
        Returns:
            True if invalidation succeeded, False otherwise
        """
        try:
            client = self._get_redis()
            if client is None:
                return False
            
            pattern = "nl2sql:*"
            keys = client.keys(pattern)
            
            if not keys:
                return True
            
            deleted = client.delete(*keys)
            logger.info(f"Invalidated {deleted} NL2SQL cache entries")
            return True
            
        except RedisError as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict with cache statistics or empty dict on error
        """
        try:
            client = self._get_redis()
            if client is None:
                return {"connected": False}
            
            pattern = "nl2sql:*"
            keys = client.keys(pattern)
            
            return {
                "connected": True,
                "total_cached": len(keys),
                "ttl": self.ttl
            }
            
        except RedisError as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"connected": False, "error": str(e)}


# Global cache instance for convenience
_cache_instance: Optional[NL2SQLCache] = None


def get_nl2sql_cache() -> NL2SQLCache:
    """Get or create global NL2SQL cache instance.
    
    Returns:
        Singleton NL2SQLCache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = NL2SQLCache()
    return _cache_instance
