import redis
from app.config import get_settings

settings = get_settings()


def _build_redis_url() -> str:
    if settings.redis_url:
        return settings.redis_url
    return f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"


redis_client = redis.from_url(_build_redis_url(), decode_responses=True)


def get_redis():
    return redis_client
