"""
Token Blacklist Service using Redis.
"""
import hashlib
import logging
from typing import Optional
from app.core.redis import redis_client
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

BLACKLIST_PREFIX = "token_blacklist:"


def _token_key(token: str) -> str:
    """生成 token 在 Redis 中的 key（使用 hash 避免存储完整 token）"""
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
    return f"{BLACKLIST_PREFIX}{token_hash}"


def add_to_blacklist(token: str, ttl_seconds: Optional[int] = None) -> bool:
    """将 token 加入黑名单

    Args:
        token: JWT token string
        ttl_seconds: 黑名单有效期，默认从 token 剩余有效期获取

    Returns:
        True if added successfully
    """
    try:
        payload = decode_access_token(token)
        if not payload:
            logger.warning("无法解码 token，无法加入黑名单")
            return False

        # 计算剩余有效期
        if ttl_seconds is None:
            exp = payload.get("exp")
            if not exp:
                logger.warning("token 无 exp 声明，无法确定黑名单 TTL")
                return False
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc).timestamp()
            ttl_seconds = int(exp - now)
            if ttl_seconds <= 0:
                logger.info("token 已过期，跳过加入黑名单")
                return False

        key = _token_key(token)
        redis_client.setex(key, ttl_seconds, "1")
        logger.info(f"Token 加入黑名单，TTL={ttl_seconds}s")
        return True
    except Exception as e:
        logger.exception("Token 加入黑名单失败: %s", e)
        return False


def is_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中"""
    try:
        key = _token_key(token)
        return redis_client.exists(key) > 0
    except Exception as e:
        logger.exception("检查 token 黑名单失败: %s", e)
        return False  # 失败时安全放行，不阻断正常请求


def revoke_token(token: str) -> bool:
    """撤销 token（别名）"""
    return add_to_blacklist(token)