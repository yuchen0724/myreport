import pytest

from app.api import rca


def test_rca_ai_analysis_includes_semantic_context(monkeypatch, db_session):
    captured = {}

    def fake_build_semantic_runtime_context(db, data_source_id, question=None, max_chars=12000):
        captured["question"] = question
        return "SEMANTIC_CONTEXT"

    monkeypatch.setattr(rca, "build_semantic_runtime_context", fake_build_semantic_runtime_context)

    semantic = rca.build_semantic_runtime_context(db_session, 99, "GMV\n异常摘要")
    assert semantic == "SEMANTIC_CONTEXT"
    assert captured["question"] == "GMV\n异常摘要"
