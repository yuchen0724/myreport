"""Semantic context helpers for LLM-backed modules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

SEMANTIC_PROMPT_VERSION = "semantic-snapshot-v10"
SEMANTIC_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "semantic" / "semantic_layer.schema.json"


def load_semantic_schema() -> List[Dict[str, Any]]:
    try:
        if not SEMANTIC_SCHEMA_PATH.exists():
            return []
        return json.loads(SEMANTIC_SCHEMA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def find_schema_entry_by_text(doc: str) -> Dict[str, Any]:
    schema = load_semantic_schema()
    for item in schema:
        db = item.get("database") or ""
        title = item.get("title") or ""
        if db and (db in doc or title in doc):
            return item
    return {}


def compact_semantic_doc(doc: str, max_chars: int = 2600) -> str:
    lines: List[str] = []
    for line in doc.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("-"):
            lines.append(stripped)
        if len("\n".join(lines)) >= max_chars:
            break
    compacted = "\n".join(lines)
    return compacted[:max_chars]


def _schema_default_priority(schema_entry: Dict[str, Any]) -> List[str]:
    semantics = schema_entry.get("semantics") or {}
    return semantics.get("default_priority") or ["semantic_doc", "metric_definitions", "realtime_schema", "model_knowledge"]


def _schema_summary(schema_entry: Dict[str, Any]) -> Dict[str, Any]:
    semantics = schema_entry.get("semantics") or {}
    return {
        "purpose": semantics.get("purpose", ""),
        "units": semantics.get("units", ""),
        "default_priority": _schema_default_priority(schema_entry),
        "metrics": semantics.get("metrics", []),
        "dimensions": semantics.get("dimensions", []),
        "join_rules": semantics.get("join_rules", []),
        "default_filters": semantics.get("default_filters", []),
        "forbidden_patterns": semantics.get("forbidden_patterns", []),
    }


def build_semantic_snapshot(doc: str, data_source_id: int, question: Optional[str] = None) -> str:
    if not doc:
        return ""

    schema_entry = find_schema_entry_by_text(doc)
    summary: Dict[str, Any] = {
        "data_source_id": data_source_id,
        "question_hint": question or "",
        "prompt_version": SEMANTIC_PROMPT_VERSION,
        "rules": [
            "优先使用语义层文档中的指标口径、维度、JOIN 和过滤规则",
            "禁止发明字段、指标或 join",
            "比率类指标必须先汇总再计算",
            "金额默认按分存储，展示时转换为元",
        ],
        "schema": _schema_summary(schema_entry) if schema_entry else {},
        "document_head": compact_semantic_doc(doc, max_chars=2600),
    }
    return "## 结构化语义快照\n```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```"
