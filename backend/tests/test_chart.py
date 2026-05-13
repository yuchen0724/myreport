# backend/tests/test_chart.py
import pytest
from unittest.mock import Mock, MagicMock
from app.schemas.chart import ChartRequest, ChartConfig


def test_generate_chart(db_session):
    """测试生成图表（使用 mock）"""
    from app.services.chart_service import ChartService
    from app.services.query_service import QueryService
    from app.repositories.data_source_repository import DataSourceRepository
    
    # Mock QueryService 返回带 rows/columns 属性的对象
    mock_result = MagicMock()
    mock_result.rows = [[1, "user1"], [2, "user2"], [3, "user3"]]
    mock_result.columns = ["id", "username"]
    
    mock_query_service = Mock(spec=QueryService)
    mock_query_service.execute_sql.return_value = mock_result
    # ChartService 需要 ds_repo 来加载字段名映射
    mock_query_service.ds_repo = Mock(spec=DataSourceRepository)
    mock_query_service.ds_repo.get_by_id.return_value = None
    
    chart_service = ChartService(mock_query_service)

    request = ChartRequest(
        data_source_id=1,
        sql="SELECT id, username FROM users LIMIT 5",
        chart_config=ChartConfig(
            chart_type="bar",
            x_axis="id",
            y_axis="username",
            title="用户图表"
        )
    )

    response = chart_service.generate_chart(request, user_id=1)

    assert response.chart_type == "bar"
    assert len(response.data) > 0