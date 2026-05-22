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
    database_url: str = "postgresql://zhou@localhost:5432/myreport"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_pool_size: int = 10
    redis_url: Optional[str] = None

    # JWT
    secret_key: str = "change-me-in-production-please"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Encryption for data source passwords
    # 生产环境务必通过 .env 或环境变量设置！生成命令: openssl rand -hex 32
    password_encryption_key: str = ""

    # CORS
    cors_origins: List[str] = ["http://localhost:5173"]
    cors_origins_prod: Optional[str] = None

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 100
    rate_limit_window_seconds: int = 60

    # LLM / NL2SQL
    llm_adapter: str = "langchain"  # raw, langchain
    llm_provider: str = "openai"  # openai, azure, ollama, anthropic
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_api_mode: str = "responses"  # chat (chat.completions) 或 responses (OpenAI Responses API)
    
    # Azure OpenAI
    azure_openai_endpoint: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    
    # NL2SQL 行为配置
    nl2sql_temperature: float = 0.0
    nl2sql_max_retries: int = 2
    nl2sql_timeout: int = 300  # LLM 调用超时 5 分钟（可配置）
    nl2sql_cache_ttl: int = 3600  # 缓存 1 小时
    nl2sql_schema_retrieval_enabled: bool = True
    nl2sql_schema_retrieval_min_chars: int = 12000
    nl2sql_schema_retrieval_max_sections: int = 8
    # 提示词模板路径（支持绝对路径或相对 backend/ 的路径）
    nl2sql_system_prompt_path: Optional[str] = "prompts/nl2sql/system_prompt.md"
    nl2sql_repair_prompt_path: Optional[str] = "prompts/nl2sql/repair_prompt.md"

    # Prediction (销售预测)
    prediction_enabled: bool = True
    prediction_model_dir: str = "./models/prediction"
    prediction_train_default_days: int = 365
    prediction_forecast_days: int = 30
    prediction_min_history_days: int = 90
    prediction_test_days: int = 30  # 测试集天数
    prediction_valid_days: int = 30  # 验证集天数
    prediction_retrain_cron: str = "0 2 * * *"  # 每天凌晨2点重训练

    # Prediction Celery task 参数
    prediction_task_max_retries: int = 1
    prediction_task_soft_time_limit: int = 1200
    prediction_task_time_limit: int = 1800
    prediction_task_batch_timeout: int = 120  # 单批超时（秒），超时则跳过该批

    @field_validator("database_url", "secret_key")
    @classmethod
    def validate_required(cls, v: str, info) -> str:
        """Validate required fields are not empty or placeholder."""
        if not v:
            raise ValueError("Config value cannot be empty")
        if v in ("changeme", "your-secret-key", "your-encryption-key", "change-me-in-production-please"):
            # 生产环境拒绝启动，开发环境仅警告（由 main.py 负责）
            if not info.data.get("debug", True):
                raise ValueError(f"Config value is a placeholder: {v}")
        return v

    @field_validator("password_encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str, info) -> str:
        """Validate password encryption key is not empty in production.
        
        Dev 环境允许为空（security.py 会从 secret_key 派生备用密钥），
        但会触发 main.py 的启动警告。
        """
        if not v:
            if not info.data.get("debug", True):
                raise ValueError(
                    "password_encryption_key must be set in production. "
                    "Generate via: openssl rand -hex 32"
                )
        return v

    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_api_key(cls, v: str, info) -> str:
        """Validate LLM API key is not empty when NL2SQL is in use.
        
        Dev 环境仅警告，生产环境抛出异常。
        """
        if not v:
            if not info.data.get("debug", True):
                raise ValueError(
                    "llm_api_key must be set in production when NL2SQL is enabled. "
                    "Set LLM_API_KEY via .env or environment variable."
                )
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
