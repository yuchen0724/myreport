from types import ModuleType, SimpleNamespace

import pytest

from app.schemas.nl2sql import GeneratedSQLResult
from app.utils.llm_client import LLMClient, LLMError


def make_settings(adapter="raw", provider="openai", api_mode="chat"):
    return SimpleNamespace(
        llm_adapter=adapter,
        llm_provider=provider,
        nl2sql_max_retries=2,
        nl2sql_timeout=1,
        llm_api_mode=api_mode,
        llm_model="test-model",
        llm_api_base="https://example.test/v1",
        llm_api_key="test-key",
        azure_openai_endpoint=None,
        azure_openai_deployment=None,
        ollama_base_url="http://localhost:11434",
    )


def test_raw_adapter_uses_existing_provider_call(monkeypatch):
    monkeypatch.setattr(
        "app.utils.llm_client.get_settings",
        lambda: make_settings(adapter="raw", provider="openai"),
    )
    client = LLMClient()
    monkeypatch.setattr(client, "_call_openai", lambda messages, temperature: "raw-ok")

    result = client.chat([{"role": "user", "content": "hi"}], temperature=0.1)

    assert result == "raw-ok"


def test_langchain_adapter_requires_supported_provider(monkeypatch):
    monkeypatch.setattr(
        "app.utils.llm_client.get_settings",
        lambda: make_settings(adapter="langchain", provider="ollama"),
    )
    client = LLMClient()

    with pytest.raises(LLMError, match="supports only openai provider"):
        client.chat([{"role": "user", "content": "hi"}])


def test_langchain_adapter_reports_missing_dependency(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("langchain_openai"):
            raise ImportError("missing langchain-openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    monkeypatch.setattr(
        "app.utils.llm_client.get_settings",
        lambda: make_settings(adapter="langchain", provider="openai"),
    )
    client = LLMClient()

    with pytest.raises(LLMError, match="requires langchain-core and langchain-openai"):
        client.chat([{"role": "user", "content": "hi"}])


def test_langchain_adapter_invokes_chat_model(monkeypatch):
    captured = {}

    messages_module = ModuleType("langchain_core.messages")

    class SystemMessage:
        def __init__(self, content):
            self.content = content

    class HumanMessage:
        def __init__(self, content):
            self.content = content

    class AIMessage:
        def __init__(self, content):
            self.content = content

    messages_module.SystemMessage = SystemMessage
    messages_module.HumanMessage = HumanMessage
    messages_module.AIMessage = AIMessage

    openai_module = ModuleType("langchain_openai")

    class ChatOpenAI:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def invoke(self, messages):
            captured["messages"] = messages
            return SimpleNamespace(content='{"sql": "SELECT 1"}')

    openai_module.ChatOpenAI = ChatOpenAI

    monkeypatch.setitem(__import__("sys").modules, "langchain_core.messages", messages_module)
    monkeypatch.setitem(__import__("sys").modules, "langchain_openai", openai_module)
    monkeypatch.setattr(
        "app.utils.llm_client.get_settings",
        lambda: make_settings(adapter="langchain", provider="openai"),
    )

    client = LLMClient()
    result = client.chat(
        [
            {"role": "system", "content": "rules"},
            {"role": "assistant", "content": "previous"},
            {"role": "user", "content": "hi"},
        ],
        temperature=0.2,
    )

    assert result == '{"sql": "SELECT 1"}'
    assert captured["init"]["model"] == "test-model"
    assert captured["init"]["base_url"] == "https://example.test/v1"
    assert captured["init"]["temperature"] == 0.2
    assert [type(message).__name__ for message in captured["messages"]] == [
        "SystemMessage",
        "AIMessage",
        "HumanMessage",
    ]


def test_langchain_adapter_invokes_structured_output(monkeypatch):
    captured = {}

    messages_module = ModuleType("langchain_core.messages")

    class SystemMessage:
        def __init__(self, content):
            self.content = content

    class HumanMessage:
        def __init__(self, content):
            self.content = content

    class AIMessage:
        def __init__(self, content):
            self.content = content

    messages_module.SystemMessage = SystemMessage
    messages_module.HumanMessage = HumanMessage
    messages_module.AIMessage = AIMessage

    openai_module = ModuleType("langchain_openai")

    class StructuredModel:
        def invoke(self, messages):
            captured["messages"] = messages
            return GeneratedSQLResult(
                sql="SELECT 1",
                confidence=0.95,
                explanation="structured",
            )

    class ChatOpenAI:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def with_structured_output(self, response_model):
            captured["response_model"] = response_model
            return StructuredModel()

    openai_module.ChatOpenAI = ChatOpenAI

    monkeypatch.setitem(__import__("sys").modules, "langchain_core.messages", messages_module)
    monkeypatch.setitem(__import__("sys").modules, "langchain_openai", openai_module)
    monkeypatch.setattr(
        "app.utils.llm_client.get_settings",
        lambda: make_settings(adapter="langchain", provider="openai"),
    )

    client = LLMClient()
    result = client.chat_structured(
        [{"role": "user", "content": "hi"}],
        GeneratedSQLResult,
        temperature=0.0,
    )

    assert result["sql"] == "SELECT 1"
    assert result["confidence"] == 0.95
    assert captured["response_model"] is GeneratedSQLResult
    assert captured["init"]["model"] == "test-model"
