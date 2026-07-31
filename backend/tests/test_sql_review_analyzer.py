from app.services.sql_review_analyzer import SqlReviewAnalyzer


def _codes(result):
    return {finding["code"] for finding in result["findings"]}


def test_flags_unsafe_and_full_scan_queries():
    analyzer = SqlReviewAnalyzer()

    unsafe = analyzer.analyze("DELETE FROM users")
    assert unsafe["risk_level"] == "high"
    assert "unsafe_sql" in _codes(unsafe)

    full_scan = analyzer.analyze("SELECT * FROM sales")
    assert full_scan["risk_level"] == "high"
    assert {"select_star", "missing_filter", "unbounded_result"} <= _codes(full_scan)


def test_flags_cartesian_join():
    result = SqlReviewAnalyzer().analyze(
        "SELECT a.id FROM orders a JOIN stores b WHERE a.dt = '2026-07-30' LIMIT 10"
    )
    assert "cartesian_join" in _codes(result)
    assert result["risk_level"] == "high"


def test_flags_semi_additive_inventory_sum():
    result = SqlReviewAnalyzer().analyze(
        "SELECT SUM(closing_stock_qty) FROM inventory WHERE dt BETWEEN '2026-07-01' AND '2026-07-30'"
    )
    assert "semi_additive_sum" in _codes(result)
    assert result["recommendation"] == "reject"


def test_count_star_is_not_select_star():
    result = SqlReviewAnalyzer().analyze(
        "SELECT COUNT(*) FROM sales WHERE dt = '2026-07-30'"
    )
    assert "select_star" not in _codes(result)
