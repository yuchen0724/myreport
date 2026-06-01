"""Helpers for inferring chart axes from query result columns.

This module is intentionally small and self-contained so chart generation can
choose sensible defaults without depending on the AI model to supply perfect
x/y field names.
"""

from __future__ import annotations

from typing import Any, Sequence, Tuple

DATE_HINTS = ("dt", "date", "day", "time", "month", "hour")
NAME_HINTS = ("name", "code", "store", "sku", "shop", "brand", "category", "id")


def _safe_get(row: Any, field: str, columns: Sequence[str]) -> Any:
    if isinstance(row, dict):
        if field in row:
            return row[field]
        if field.lower() in row:
            return row[field.lower()]
        return None
    if field in columns:
        idx = columns.index(field)
        return row[idx] if idx < len(row) else None
    return None


def _is_numeric_column(columns: Sequence[str], data: Sequence[Any], col: str) -> bool:
    values = []
    for row in data[:50]:
        try:
            values.append(float(_safe_get(row, col, columns)))
        except (TypeError, ValueError):
            pass
    return len(values) >= max(1, min(3, len(data[:50])) // 2)


def infer_chart_axes(
    columns: Sequence[str],
    data: Sequence[Any],
    x_axis_field: str = "",
    y_axis_field: str = "",
) -> Tuple[str, str]:
    """Infer x/y axis fields using column semantics.

    Priority:
    - x: date/time columns -> name/code/id-like columns -> first column
    - y: numeric columns -> explicit numeric field -> first numeric not equal to x
    """
    if not columns:
        return x_axis_field, y_axis_field

    date_cols = [col for col in columns if any(hint in col.lower() for hint in DATE_HINTS)]
    name_cols = [col for col in columns if any(hint in col.lower() for hint in NAME_HINTS)]
    if any(col.lower() == "t.store_name" for col in columns):
        name_cols = [col for col in columns if col.lower().endswith("store_name") or "name" in col.lower()] + [col for col in columns if col.lower() not in {c.lower() for c in columns if c.lower().endswith("store_name") or "name" in c.lower()}]
    numeric_cols = [col for col in columns if _is_numeric_column(columns, data, col)]

    x_field = x_axis_field if x_axis_field in columns else ""
    if not x_field:
        x_field = date_cols[0] if date_cols else (name_cols[0] if name_cols else columns[0])

    y_field = y_axis_field if y_axis_field in numeric_cols and y_axis_field != x_field else ""
    if not y_field:
        candidates = [col for col in numeric_cols if col != x_field]
        y_field = candidates[0] if candidates else (columns[1] if len(columns) > 1 else columns[0])

    return x_field, y_field
