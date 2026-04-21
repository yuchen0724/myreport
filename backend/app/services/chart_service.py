# backend/app/services/chart_service.py
from typing import List, Dict, Any
from app.schemas.chart import ChartRequest, ChartResponse
from app.schemas.query import SQLQueryRequest
from app.services.query_service import QueryService

class ChartService:
    """图表服务"""

    def __init__(self, query_service: QueryService):
        self.query_service = query_service

    def generate_chart(self, request: ChartRequest, user_id: int) -> ChartResponse:
        """
        生成图表数据

        Args:
            request: 图表请求
            user_id: 用户 ID

        Returns:
            图表响应
        """
        # 执行查询
        query_request = SQLQueryRequest(
            data_source_id=request.data_source_id,
            sql=request.sql,
            params={}
        )
        result = self.query_service.execute_sql(query_request, user_id)

        # 转换数据格式
        chart_data = self._convert_to_chart_data(
            result.rows,
            result.columns,
            request.chart_config
        )

        return ChartResponse(
            chart_type=request.chart_config.chart_type,
            data=chart_data,
            config={
                "x_axis": request.chart_config.x_axis,
                "y_axis": request.chart_config.y_axis,
                "title": request.chart_config.title,
                "color": request.chart_config.color
            }
        )

    def _convert_to_chart_data(
        self,
        rows: List[List[Any]],
        columns: List[str],
        config
    ) -> List[Dict[str, Any]]:
        """
        转换查询结果为图表数据

        Args:
            rows: 数据行
            columns: 列名
            config: 图表配置

        Returns:
            图表数据
        """
        chart_data = []

        # 找到 X 轴和 Y 轴的索引
        x_index = columns.index(config.x_axis) if config.x_axis in columns else 0
        y_index = columns.index(config.y_axis) if config.y_axis in columns else 1

        # 转换数据
        for row in rows:
            chart_data.append({
                "x": row[x_index],
                "y": row[y_index]
            })

        return chart_data
