from unittest.mock import MagicMock, patch

from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.services.ai_design_service import AIDesignService


def _metric(db_session, key, expression="SUM(amount)", description="成交金额"):
    metric = SemanticMetricRepository(db_session).create(
        {
            "metric_key": key,
            "name": key.upper(),
            "description": description,
            "data_source_id": 1,
            "base_sql": "SELECT dt, store_id, amount FROM sales",
            "metric_expression": expression,
            "dimensions": ["store_id"],
            "time_column": "dt",
            "is_active": True,
        },
        user_id=1,
    )
    db_session.commit()
    return metric


def test_metric_audit_finds_duplicates_and_missing_description(db_session):
    _metric(db_session, "gmv")
    _metric(db_session, "sales_amount", description="")

    result = AIDesignService(db_session).audit_metrics(1, user_id=1)
    codes = {finding["code"] for finding in result["findings"]}

    assert "duplicate_definition" in codes
    assert "missing_description" in codes
    assert {frozenset(group) for group in result["duplicate_groups"]} == {
        frozenset({"gmv", "sales_amount"})
    }


def test_report_assistant_returns_draft_and_never_publishes(db_session):
    _metric(db_session, "gmv")
    llm = MagicMock()
    llm.chat_structured.return_value = {
        "name": "门店销售趋势",
        "description": "按门店查看销售额",
        "sql": "SELECT store_id, SUM(amount) AS metric_value FROM sales WHERE dt >= '2026-07-01' GROUP BY store_id LIMIT 100",
        "chart_type": "bar",
        "dimensions": ["store_id"],
        "filters": [],
        "metric_keys": ["gmv"],
        "reasoning": "复用 GMV 口径",
    }
    with patch("app.services.ai_design_service.get_llm_client", return_value=llm):
        result = AIDesignService(db_session).generate_report_draft(
            1, "查看门店销售趋势", user_id=1, preferred_chart="bar",
        )

    assert result["status"] == "draft"
    assert result["requires_confirmation"] is True
    assert result["template"]["config"]["semantic_metric_keys"] == ["gmv"]
    assert result["sql_pre_review"]["human_approval_required"] is True


def test_metric_draft_warns_about_snapshot_sum(db_session):
    llm = MagicMock()
    llm.chat_structured.return_value = {
        "metric_key": "closing_stock",
        "name": "期末库存",
        "description": "期末库存数量",
        "base_sql": "SELECT dt, store_id, end_stock_num FROM inventory",
        "metric_expression": "SUM(end_stock_num)",
        "dimensions": ["store_id"],
        "time_column": "dt",
        "reasoning": "库存快照指标",
    }
    with patch("app.services.ai_design_service.get_llm_client", return_value=llm):
        result = AIDesignService(db_session).generate_metric_draft(
            1, "创建期末库存指标", user_id=1,
        )

    assert result["status"] == "draft"
    assert any("边界快照" in warning for warning in result["warnings"])
    assert result["requires_confirmation"] is True
