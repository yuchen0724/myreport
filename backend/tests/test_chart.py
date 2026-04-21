# backend/tests/test_chart.py
import pytest
from app.services.chart_service import ChartService
from app.schemas.chart import ChartRequest, ChartConfig

def test_generate_chart(db_session):
    """测试生成图表"""
    from app.services.query_service import QueryService
    query_service = QueryService(db_session)
    chart_service = ChartService(query_service)

    request = ChartRequest(
        data_source_id=6,
        sql="SELECT id, username FROM users LIMIT 5",
        chart_config=ChartConfig(
            chart_type="bar",
            x_axis="id",
            y_axis="username",
            title="用户图表"
        )
    )

    response = chart_service.generate_chart(request, user_id=3)

    assert response.chart_type == "bar"
    assert len(response.data) > 0
    assert response.config["x_axis"] == "id"
    assert response.config["y_axis"] == "username"
