from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas.query import SQLQueryResponse
from app.services.business_briefing_service import BusinessBriefingService


def _result(value):
    return SQLQueryResponse(
        columns=["metric_value"], rows=[[value]], total=1,
        page=1, page_size=100, execution_time_ms=2,
    )


def test_business_briefing_uses_current_and_previous_period(db_session):
    service = BusinessBriefingService(db_session)
    service.metric_service = MagicMock()
    metric = SimpleNamespace(metric_key="gmv", name="成交金额")
    service.metric_service.execute.side_effect = [(metric, _result(120)), (metric, _result(100))]

    title, summary, evidence = service.generate(
        {
            "title": "经营晨报", "metric_keys": ["gmv"],
            "period": "yesterday", "include_ai_summary": False,
        },
        user_id=3,
        now=datetime(2026, 7, 31, 8, 0),
    )

    assert title == "经营晨报"
    assert "120.00" in summary
    assert "+20.00%" in summary
    assert evidence["period"] == {"start": "2026-07-30", "end": "2026-07-31"}
    assert evidence["comparison_period"] == {"start": "2026-07-29", "end": "2026-07-30"}
    assert service.metric_service.execute.call_count == 2


def test_business_briefing_zero_baseline_does_not_invent_rate(db_session):
    service = BusinessBriefingService(db_session)
    service.metric_service = MagicMock()
    metric = SimpleNamespace(metric_key="orders", name="订单数")
    service.metric_service.execute.side_effect = [(metric, _result(8)), (metric, _result(0))]

    _, summary, evidence = service.generate(
        {"metric_keys": ["orders"], "include_ai_summary": False},
        user_id=3,
        now=datetime(2026, 7, 31, 8, 0),
    )

    assert "无法计算涨跌幅" in summary
    assert evidence["metrics"][0]["change_rate"] is None
