"""应用配置

使用 pydantic-settings 进行配置管理
"""
from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # 忽略未知环境变量
    )
    
    # 应用配置
    app_name: str = "Custom Report System"
    app_version: str = "1.0.0"
    debug: bool = True

    # 数据库配置（必须配置）
    database_url: str = "postgresql://user:password@localhost:5432/report_db"

    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str = "redis://localhost:6379/0"

    # JWT 认证配置（必须配置）
    secret_key: str = "your-secret-key-change-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # 密码加密
    password_encryption_key: str = "your-encryption-key-change-here"

    # CORS 配置
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_origins_prod: str = ""  # 生产环境用逗号分隔的域名列表

    # 限流配置
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 100
    rate_limit_window: int = 60

    # Celery 配置
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    @field_validator("database_url", "secret_key", "password_encryption_key")
    @classmethod
    def validate_required(cls, v: str) -> str:
        """验证必须配置项"""
        if not v:
            raise ValueError("配置项不能为空")
        # 检查是否是明显的占位符
        if v in ("changeme", "your-secret-key", "your-encryption-key"):
            raise ValueError(f"配置项未正确设置: {v}")
        return v
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v) -> List[str]:
        """解析 CORS 源列表"""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（带缓存）"""
    return Settings()