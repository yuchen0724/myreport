"""SQL normalization helpers shared by LLM-backed services."""

from __future__ import annotations


def strip_trailing_semicolon(sql: str) -> str:
    """Remove trailing semicolons so validators that forbid multi-statement SQL do not fail."""
    return (sql or "").strip().rstrip(";")
