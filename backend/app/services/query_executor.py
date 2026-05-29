from typing import Any, Optional

from sqlalchemy import text


class QueryExecutor:
    def __init__(self, query_timeout_seconds: int = 30):
        self.query_timeout_seconds = query_timeout_seconds

    @property
    def count_timeout_seconds(self) -> int:
        return max(10, self.query_timeout_seconds // 2)

    def apply_timeout(self, conn, ds_type: str, timeout_seconds: Optional[int] = None) -> None:
        timeout = timeout_seconds or self.query_timeout_seconds
        normalized_type = ds_type.upper() if ds_type else ""

        if normalized_type in {"MYSQL", "DORIS"}:
            conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {timeout * 1000}"))
        elif normalized_type == "POSTGRESQL":
            conn.execute(text(f"SET SESSION STATEMENT_TIMEOUT = '{timeout}s'"))

    def execute_rows(self, conn, sql: str, params: Optional[dict[str, Any]] = None) -> tuple[list[str], list[list[Any]]]:
        result = self._execute(conn, sql, params)
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchall()]
        return columns, rows

    def execute_scalar(self, conn, sql: str, params: Optional[dict[str, Any]] = None) -> Any:
        result = self._execute(conn, sql, params)
        return result.scalar()

    def _execute(self, conn, sql: str, params: Optional[dict[str, Any]] = None):
        if params is None:
            return conn.execute(text(sql))
        return conn.execute(text(sql), params)
