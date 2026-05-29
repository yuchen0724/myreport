from app.services.query_executor import QueryExecutor


class FakeResult:
    def __init__(self, columns=None, rows=None, scalar_value=None):
        self._columns = columns or []
        self._rows = rows or []
        self._scalar_value = scalar_value

    def keys(self):
        return self._columns

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._scalar_value


class FakeConnection:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        return self.result


def test_apply_timeout_for_mysql_uses_millisecond_limit():
    conn = FakeConnection(FakeResult())
    executor = QueryExecutor(query_timeout_seconds=30)

    executor.apply_timeout(conn, "MYSQL")

    assert conn.calls == [("SET SESSION MAX_EXECUTION_TIME = 30000", None)]


def test_apply_timeout_for_doris_uses_mysql_protocol_setting():
    conn = FakeConnection(FakeResult())
    executor = QueryExecutor(query_timeout_seconds=15)

    executor.apply_timeout(conn, "DORIS")

    assert conn.calls == [("SET SESSION MAX_EXECUTION_TIME = 15000", None)]


def test_apply_timeout_for_postgresql_uses_statement_timeout():
    conn = FakeConnection(FakeResult())
    executor = QueryExecutor(query_timeout_seconds=30)

    executor.apply_timeout(conn, "POSTGRESQL", timeout_seconds=10)

    assert conn.calls == [("SET SESSION STATEMENT_TIMEOUT = '10s'", None)]


def test_apply_timeout_ignores_unknown_datasource_type():
    conn = FakeConnection(FakeResult())
    executor = QueryExecutor()

    executor.apply_timeout(conn, "HIVE")

    assert conn.calls == []


def test_execute_rows_returns_columns_and_list_rows():
    conn = FakeConnection(FakeResult(columns=["id", "name"], rows=[(1, "Alice"), (2, "Bob")]))
    executor = QueryExecutor()

    columns, rows = executor.execute_rows(conn, "SELECT id, name FROM users", {"id": 1})

    assert columns == ["id", "name"]
    assert rows == [[1, "Alice"], [2, "Bob"]]
    assert conn.calls == [("SELECT id, name FROM users", {"id": 1})]


def test_execute_scalar_returns_scalar_value():
    conn = FakeConnection(FakeResult(scalar_value=42))
    executor = QueryExecutor()

    value = executor.execute_scalar(conn, "SELECT COUNT(*) FROM users")

    assert value == 42
    assert conn.calls == [("SELECT COUNT(*) FROM users", None)]


def test_count_timeout_has_minimum_ten_seconds():
    executor = QueryExecutor(query_timeout_seconds=12)

    assert executor.count_timeout_seconds == 10
