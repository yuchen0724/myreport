import pytest

from app.services.sql_pagination import SqlPaginator


def test_build_regular_pagination_strips_existing_limit():
    paginator = SqlPaginator()

    result = paginator.build(
        "SELECT id, name FROM users WHERE status = ${status} ORDER BY id DESC LIMIT 100",
        page=2,
        page_size=20,
    )

    assert result.query_sql == (
        "SELECT id, name FROM users WHERE status = :status "
        "ORDER BY id DESC LIMIT 20 OFFSET 20"
    )
    assert result.order_cols == ["id"]
    assert result.should_count is True
    assert result.cursor_params == {}


def test_build_deep_pagination_uses_window_function():
    paginator = SqlPaginator()

    result = paginator.build(
        "SELECT id, name FROM users ORDER BY id ASC",
        page=52,
        page_size=20,
    )

    assert "ROW_NUMBER() OVER (ORDER BY id ASC)" in result.query_sql
    assert "WHERE _rn > 1020 AND _rn <= 1040" in result.query_sql
    assert result.order_cols == ["id"]
    assert result.should_count is True


def test_build_cursor_pagination_adds_parameterized_where():
    paginator = SqlPaginator()

    result = paginator.build(
        "SELECT id, name FROM users ORDER BY id ASC, name DESC",
        page=1,
        page_size=10,
        cursor="42,Alice",
    )

    assert result.query_sql == (
        "SELECT * FROM (SELECT id, name FROM users) as t "
        " WHERE id > :cursor_0 AND name > :cursor_1 "
        "ORDER BY id ASC, name DESC LIMIT 10"
    )
    assert result.order_cols == ["id", "name"]
    assert result.cursor_params == {"cursor_0": 42, "cursor_1": "Alice"}


def test_build_cursor_rejects_non_identifier_order_column():
    paginator = SqlPaginator()

    with pytest.raises(ValueError, match="无效的排序列名"):
        paginator.build(
            "SELECT u.id, name FROM users u ORDER BY u.id ASC",
            page=1,
            page_size=10,
            cursor="42",
        )


def test_build_requires_order_by_for_template_pagination():
    paginator = SqlPaginator()

    with pytest.raises(ValueError, match="深度分页需要明确的 ORDER BY"):
        paginator.build("SELECT id, name FROM users", page=1, page_size=20)


def test_build_skip_deep_pagination_uses_limit_offset_without_count():
    paginator = SqlPaginator()

    result = paginator.build(
        "SELECT id, name FROM users",
        page=3,
        page_size=15,
        skip_deep_pagination_check=True,
    )

    assert result.query_sql == "SELECT id, name FROM users LIMIT 15 OFFSET 30"
    assert result.order_cols == []
    assert result.should_count is False
    assert result.is_nl2sql_skip is True


def test_build_full_page_size_does_not_paginate_or_count():
    paginator = SqlPaginator()

    result = paginator.build(
        "SELECT id FROM users WHERE status = ${status}",
        page=1,
        page_size=999999,
    )

    assert result.query_sql == "SELECT id FROM users WHERE status = :status"
    assert result.should_count is False


def test_build_count_sql_strips_limit_and_converts_params():
    paginator = SqlPaginator()

    count_sql, count_base_sql = paginator.build_count_sql(
        "SELECT id FROM users WHERE status = ${status} ORDER BY id LIMIT 10 OFFSET 20"
    )

    assert count_base_sql == "SELECT id FROM users WHERE status = :status ORDER BY id"
    assert count_sql == (
        "SELECT COUNT(*) as cnt FROM "
        "(SELECT id FROM users WHERE status = :status ORDER BY id) as _subquery"
    )


def test_filter_params_defaults_missing_values():
    paginator = SqlPaginator()

    result = paginator.filter_params(
        "SELECT * FROM users WHERE name = :name AND status = :status",
        {"name": "Alice", "status": ""},
    )

    assert result == {"name": "Alice", "status": ""}
