from types import SimpleNamespace

import pytest

from app.api import config as config_api


@pytest.mark.asyncio
async def test_frontend_config_exposes_nl2sql_runtime_flags(monkeypatch):
    """配置 API 暴露 NL2SQL 运行时开关，但不暴露密钥"""
    config_api._cached_config = None
    monkeypatch.setattr(
        config_api,
        "get_settings",
        lambda: SimpleNamespace(
            nl2sql_timeout=300,
            llm_adapter="langchain",
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_mode="chat",
            nl2sql_schema_retrieval_enabled=True,
            nl2sql_schema_retrieval_min_chars=12000,
            nl2sql_schema_retrieval_max_sections=8,
        ),
    )

    response = await config_api.get_frontend_config(current_user_id=1)
    data = response.model_dump()

    assert data["nl2sql_timeout"] == 300
    assert data["nl2sql_timeout_ms"] == 360000
    assert data["llm_adapter"] == "langchain"
    assert data["llm_provider"] == "openai"
    assert data["llm_model"] == "gpt-4o-mini"
    assert data["nl2sql_structured_output_enabled"] is True
    assert data["nl2sql_schema_retrieval_enabled"] is True
    assert "llm_api_key" not in data
    config_api._cached_config = None


@pytest.mark.asyncio
async def test_frontend_config_structured_output_requires_langchain_openai_chat(monkeypatch):
    config_api._cached_config = None
    monkeypatch.setattr(
        config_api,
        "get_settings",
        lambda: SimpleNamespace(
            nl2sql_timeout=300,
            llm_adapter="raw",
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_mode="chat",
            nl2sql_schema_retrieval_enabled=False,
            nl2sql_schema_retrieval_min_chars=12000,
            nl2sql_schema_retrieval_max_sections=8,
        ),
    )

    response = await config_api.get_frontend_config(current_user_id=1)

    assert response.nl2sql_structured_output_enabled is False
    config_api._cached_config = None
