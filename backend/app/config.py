from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 数据库配置
    database_url: str = "postgresql://user:password@localhost:5432/report_db"

    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"

    # JWT 配置
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # 应用配置
    app_name: str = "Custom Report System"
    app_version: str = "1.0.0"
    debug: bool = True

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
