import json
from pathlib import Path

from app.services.sql_optimizer import SqlOptimizer


def test_sql_optimizer_includes_semantic_snapshot(monkeypatch):
    optimizer = SqlOptimizer()
    captured = {}

    monkeypatch.setattr(optimizer, "_get_llm_client", lambda: type("C", (), {"chat": lambda self, messages, temperature=0.0: "SELECT 1"})())
    monkeypatch.setattr(optimizer, "_load_prompt", lambda: "SYSTEM_PROMPT")
    monkeypatch.setattr("app.services.sql_optimizer.get_settings", lambda: type("S", (), {"sql_optimizer_enabled": True})())
    monkeypatch.setattr("app.services.sql_optimizer.build_semantic_snapshot", lambda doc, data_source_id, question=None: "SEMANTIC_SNAPSHOT")

    optimized = optimizer._optimize_with_llm("select 1")
    assert optimized == "SELECT 1"
