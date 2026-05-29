import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class PaginatedSql:
    query_sql: str
    order_cols: list[str] = field(default_factory=list)
    cursor_params: dict[str, Any] = field(default_factory=dict)
    should_count: bool = False
    is_nl2sql_skip: bool = False


class SqlPaginator:
    """Build paginated SQL while preserving QueryService's existing behavior."""

    LIMIT_OFFSET_RE = re.compile(
        r";?\s*LIMIT\s+\d+\s*OFFSET\s+\d+\s*$",
        flags=re.IGNORECASE,
    )
    LIMIT_RE = re.compile(r";?\s*LIMIT\s+\d+\s*$", flags=re.IGNORECASE)
    ORDER_BY_RE = re.compile(
        r"\bORDER\s+BY\s+(.+?)(?:\s+LIMIT|\s+OFFSET|\s*$)",
        flags=re.IGNORECASE,
    )
    STRIP_ORDER_BY_RE = re.compile(
        r"\s+ORDER\s+BY\s+.+?(?=\s*LIMIT|\s*$)",
        flags=re.IGNORECASE,
    )
    NAMED_PARAM_RE = re.compile(r":(\w+)")

    def build(
        self,
        sql: str,
        page: int = 1,
        page_size: int = 100,
        cursor: Optional[str] = None,
        skip_deep_pagination_check: bool = False,
    ) -> PaginatedSql:
        converted_sql = self.convert_placeholders(sql)

        if page_size >= 999999:
            return PaginatedSql(query_sql=converted_sql)

        offset = (page - 1) * page_size
        converted_sql = self.strip_limit(converted_sql.rstrip(";").strip())

        if skip_deep_pagination_check:
            return PaginatedSql(
                query_sql=f"{converted_sql} LIMIT {page_size} OFFSET {offset}",
                is_nl2sql_skip=True,
            )

        order_by_match = self.ORDER_BY_RE.search(converted_sql)
        if not order_by_match:
            raise ValueError("深度分页需要明确的 ORDER BY，请在 SQL 中添加 ORDER BY 子句")

        order_by_clause = order_by_match.group(1)
        order_cols = [col.strip().split()[0] for col in order_by_clause.split(",")]
        base_sql = self.STRIP_ORDER_BY_RE.sub("", converted_sql).strip()
        cursor_where, cursor_params = self._build_cursor_where(
            order_cols=order_cols,
            cursor=cursor,
        )

        if cursor_where:
            final_sql = (
                f"SELECT * FROM ({base_sql}) as t {cursor_where} "
                f"ORDER BY {order_by_clause} LIMIT {page_size}"
            )
        elif offset > 1000:
            final_sql = (
                "SELECT * FROM (SELECT ROW_NUMBER() OVER "
                f"(ORDER BY {order_by_clause}) as _rn, t.* "
                f"FROM ({base_sql}) as t) as t_paged "
                f"WHERE _rn > {offset} AND _rn <= {offset + page_size}"
            )
        else:
            final_sql = f"{base_sql} ORDER BY {order_by_clause} LIMIT {page_size} OFFSET {offset}"

        return PaginatedSql(
            query_sql=final_sql,
            order_cols=order_cols,
            cursor_params=cursor_params,
            should_count=True,
        )

    def build_count_sql(self, sql: str) -> tuple[str, str]:
        count_base_sql = re.sub(r"\$\{(\w+)\}", r":\1", sql)
        count_base_sql = self.strip_limit(count_base_sql.strip())
        count_sql = f"SELECT COUNT(*) as cnt FROM ({count_base_sql}) as _subquery"
        return count_sql, count_base_sql

    def filter_params(
        self,
        sql: str,
        params: Optional[dict],
        default_missing: bool = True,
    ) -> dict[str, Any]:
        placeholders = set(self.NAMED_PARAM_RE.findall(sql))
        filtered_params: dict[str, Any] = {}
        for placeholder in placeholders:
            if params and placeholder in params and params[placeholder] is not None and params[placeholder] != "":
                filtered_params[placeholder] = params[placeholder]
            elif default_missing:
                filtered_params[placeholder] = ""
        return filtered_params

    def has_placeholders(self, sql: str) -> bool:
        return bool(self.NAMED_PARAM_RE.search(sql))

    def convert_placeholders(self, sql: str) -> str:
        return sql.replace("${", ":").replace("}", "")

    def strip_limit(self, sql: str) -> str:
        sql = self.LIMIT_OFFSET_RE.sub("", sql)
        return self.LIMIT_RE.sub("", sql)

    def _build_cursor_where(
        self,
        order_cols: list[str],
        cursor: Optional[str],
    ) -> tuple[str, dict[str, Any]]:
        if not cursor:
            return "", {}

        cursor_parts = [part.strip() for part in cursor.split(",")]
        where_parts = []
        query_params: dict[str, Any] = {}

        for i, col in enumerate(order_cols):
            if i >= len(cursor_parts):
                continue

            if not col.isidentifier():
                raise ValueError(f"无效的排序列名: {col}")

            val = cursor_parts[i]
            param_name = f"cursor_{i}"
            where_parts.append(f"{col} > :{param_name}")
            if val and val.lstrip("-").replace(".", "", 1).isdigit():
                query_params[param_name] = float(val) if "." in val else int(val)
            else:
                query_params[param_name] = val

        if not where_parts:
            return "", {}

        return " WHERE " + " AND ".join(where_parts), query_params
