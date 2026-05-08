"""
Application configuration.

Uses pydantic-settings to load from environment/.env.
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment/.env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Custom Report System"
    app_version: str = "1.0.0"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///./app.db"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_url: Optional[str] = None

    # JWT
    secret_key: str = "change-me-in-production-please"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Encryption for data source passwords
    password_encryption_key: str = ""

    # CORS
    cors_origins: List[str] = ["http://localhost:5173"]
    cors_origins_prod: Optional[str] = None

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 100
    rate_limit_window_seconds: int = 60

    # LLM / NL2SQL
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-3.5-turbo"

    @field_validator("database_url", "secret_key")
    @classmethod
    def validate_required(cls, v: str) -> str:
        """Validate required fields are not empty or placeholder."""
        if not v:
            raise ValueError("Config value cannot be empty")
        if v in ("changeme", "your-secret-key", "your-encryption-key"):
            raise ValueError(f"Config value is a placeholder: {v}")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v) -> List[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
