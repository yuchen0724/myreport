from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List, Optional


class Settings(BaseSettings):
    # 应用配置
    app_name: str = "Custom Report System"
    app_version: str = "1.0.0"
    debug: bool = True

    # 数据库配置
    database_url: str = "postgresql://zhou@localhost:5433/report_db"

    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"

    # JWT 配置
    secret_key: str = "your-secret-key-please-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24小时

    # CORS 配置
    cors_origins: List[str] = ["*"]

    # 限流配置
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 100
    rate_limit_window: int = 60

    # 密码加密密钥
    password_encryption_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings():
    return Settings()
