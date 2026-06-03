"""SQL normalization and lightweight validation helpers shared by LLM-backed services."""

from __future__ import annotations

import re

_FROM_JOIN_RE = re.compile(r"\b(?:from|join)\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_FORBIDDEN_SQL_TOKENS = ("qualify",)


def strip_trailing_semicolon(sql: str) -> str:
    """Remove trailing semicolons so validators that forbid multi-statement SQL do not fail."""
    return (sql or "").strip().rstrip(";")


def has_forbidden_sql_tokens(sql: str) -> bool:
    sql_lower = (sql or "").lower()
    return any(token in sql_lower for token in _FORBIDDEN_SQL_TOKENS)


def extract_table_references(sql: str) -> list[str]:
    """Extract table-like references after FROM/JOIN keywords.

    This is intentionally lightweight: it is used as a guardrail before execution,
    not as a full SQL parser.
    """
    sql = sql or ""
    refs: list[str] = []
    for match in _FROM_JOIN_RE.finditer(sql):
        tail = sql[match.end():].lstrip()
        if not tail:
            continue
        token_match = _TOKEN_RE.match(tail)
        if not token_match:
            continue
        token = token_match.group(0).rstrip(",)")
        if token and token[0] not in "(\"'":
            refs.append(token)
    return refs


def has_multi_level_table_reference(sql: str):
    """返回第一个多级引用，或 None"""
    for ref in extract_table_references(sql):
        if ref.count(".") > 1:
            return ref
    return None


# 允许跨库查询的系统 schema（information_schema、mysql 等）
_ALLOWED_FOREIGN_SCHEMAS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})


def has_foreign_schema_reference(sql: str, allowed_schema: str):
    """返回第一个外部库引用，或 None"""
    allowed_schema = (allowed_schema or "").strip()
    if not allowed_schema:
        return None
    for ref in extract_table_references(sql):
        if ref.count(".") == 1:
            schema, _table = ref.split(".", 1)
            if schema != allowed_schema and schema.lower() not in _ALLOWED_FOREIGN_SCHEMAS:
                return ref
    return None
