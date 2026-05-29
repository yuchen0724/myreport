from typing import Any

from app.models.semantic_metric import SemanticMetric
from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.schemas.query import SQLQueryRequest, SQLQueryResponse
from app.schemas.semantic_metric import SemanticMetricQueryRequest, SemanticMetricSqlPreview
from app.services.query_service import QueryService


class SemanticMetricQueryService:
    def __init__(self, db):
        self.db = db
        self.metric_repo = SemanticMetricRepository(db)

    def get_active_metric(self, metric_key: str, user_id: int, is_admin: bool = False) -> SemanticMetric:
        metric = self.metric_repo.get_visible_by_key(
            metric_key,
            user_id=user_id,
            is_admin=is_admin,
            active_only=True,
        )
        if not metric:
            raise ValueError("指标不存在或已禁用")
        return metric

    def preview_sql(
        self,
        request: SemanticMetricQueryRequest,
        user_id: int,
        is_admin: bool = False,
    ) -> tuple[SemanticMetric, SemanticMetricSqlPreview]:
        metric = self.get_active_metric(request.metric_key, user_id=user_id, is_admin=is_admin)
        sql, params = self._compile_sql(metric, request)
        return metric, SemanticMetricSqlPreview(
            data_source_id=metric.data_source_id,
            sql=sql,
            params=params,
            page=request.page,
            page_size=request.page_size,
        )

    def execute(
        self,
        request: SemanticMetricQueryRequest,
        user_id: int,
        is_admin: bool = False,
    ) -> tuple[SemanticMetric, SQLQueryResponse]:
        metric, preview = self.preview_sql(request, user_id=user_id, is_admin=is_admin)
        query_request = SQLQueryRequest(
            data_source_id=preview.data_source_id,
            sql=preview.sql,
            params=preview.params,
            page=preview.page,
            page_size=preview.page_size,
            skip_deep_pagination_check=False,
        )
        return metric, QueryService(self.db).execute_sql(query_request, user_id)

    def _compile_sql(
        self,
        metric: SemanticMetric,
        request: SemanticMetricQueryRequest,
    ) -> tuple[str, dict[str, Any]]:
        allowed_dimensions = set(metric.dimensions or [])
        selected_dimensions = request.dimensions

        invalid_dimensions = [dimension for dimension in selected_dimensions if dimension not in allowed_dimensions]
        if invalid_dimensions:
            raise ValueError(f"未知维度: {', '.join(invalid_dimensions)}")

        allowed_filter_fields = allowed_dimensions | {metric.time_column}
        invalid_filters = [field for field in request.filters if field not in allowed_filter_fields]
        if invalid_filters:
            raise ValueError(f"未知过滤字段: {', '.join(invalid_filters)}")

        select_columns = selected_dimensions + ["metric_value"]
        group_by_clause = f"GROUP BY {', '.join(selected_dimensions)}" if selected_dimensions else ""
        order_by_columns = selected_dimensions or ["metric_value"]
        order_by_clause = "ORDER BY " + ", ".join(order_by_columns)

        where_parts = []
        params: dict[str, Any] = {}

        if request.start_time is not None:
            where_parts.append(f"{metric.time_column} >= :start_time")
            params["start_time"] = request.start_time
        if request.end_time is not None:
            where_parts.append(f"{metric.time_column} < :end_time")
            params["end_time"] = request.end_time

        for index, (field, value) in enumerate(request.filters.items()):
            param_name = f"filter_{index}"
            where_parts.append(f"{field} = :{param_name}")
            params[param_name] = value

        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""
        dimension_select = ", ".join(selected_dimensions)
        metric_expression = metric.metric_expression or "COUNT(*)"
        value_select = (
            f"{metric_expression} AS metric_value"
            if not dimension_select
            else f"{dimension_select}, {metric_expression} AS metric_value"
        )
        inner_clauses = [
            f"SELECT {value_select}",
            f"FROM ({metric.base_sql}) AS metric_base",
        ]
        if where_clause:
            inner_clauses.append(where_clause)
        if group_by_clause:
            inner_clauses.append(group_by_clause)

        sql = (
            f"SELECT {', '.join(select_columns)} "
            "FROM ("
            f"{' '.join(inner_clauses)}"
            ") AS metric_result "
            f"{order_by_clause}"
        )
        return " ".join(sql.split()), params
