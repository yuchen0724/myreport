"""Semantic metric API schemas."""
from datetime import datetime
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.query import SQLQueryResponse

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
METRIC_EXPRESSION_RE = re.compile(
    r"^(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(\*|[A-Za-z_][A-Za-z0-9_]*|DISTINCT\s+[A-Za-z_][A-Za-z0-9_]*)\s*\)$",
    re.IGNORECASE,
)


class SemanticMetricBase(BaseModel):
    metric_key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    data_source_id: int
    base_sql: str = Field(..., min_length=1)
    metric_expression: str = Field("COUNT(*)", min_length=1, max_length=300)
    dimensions: list[str] = Field(default_factory=list)
    time_column: str = Field(..., min_length=1, max_length=200)
    is_active: bool = True

    @field_validator("base_sql")
    @classmethod
    def validate_base_sql(cls, value: str) -> str:
        sql = value.strip()
        if not sql:
            raise ValueError("base_sql 不能为空")
        if not sql.lower().startswith(("select", "with")):
            raise ValueError("base_sql 只允许 SELECT/WITH 查询")
        return sql

    @field_validator("metric_expression")
    @classmethod
    def validate_metric_expression(cls, value: str) -> str:
        expression = " ".join(value.strip().split())
        if not METRIC_EXPRESSION_RE.match(expression):
            raise ValueError("metric_expression 仅支持 COUNT/SUM/AVG/MIN/MAX 聚合表达式")
        return expression.upper() if expression.upper() == "COUNT(*)" else expression

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: list[str]) -> list[str]:
        cleaned = []
        for dimension in value:
            item = dimension.strip()
            if not item:
                raise ValueError("dimensions 不能包含空值")
            if not IDENTIFIER_RE.match(item):
                raise ValueError("dimensions 只能包含安全字段名")
            cleaned.append(item)
        return cleaned

    @field_validator("time_column")
    @classmethod
    def validate_time_column(cls, value: str) -> str:
        item = value.strip()
        if not IDENTIFIER_RE.match(item):
            raise ValueError("time_column 只能是安全字段名")
        return item


class SemanticMetricCreate(SemanticMetricBase):
    pass


class SemanticMetricUpdate(BaseModel):
    metric_key: Optional[str] = Field(None, min_length=1, max_length=100, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    data_source_id: Optional[int] = None
    base_sql: Optional[str] = Field(None, min_length=1)
    metric_expression: Optional[str] = Field(None, min_length=1, max_length=300)
    dimensions: Optional[list[str]] = None
    time_column: Optional[str] = Field(None, min_length=1, max_length=200)
    is_active: Optional[bool] = None

    @field_validator("base_sql")
    @classmethod
    def validate_base_sql(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        sql = value.strip()
        if not sql:
            raise ValueError("base_sql 不能为空")
        if not sql.lower().startswith(("select", "with")):
            raise ValueError("base_sql 只允许 SELECT/WITH 查询")
        return sql

    @field_validator("metric_expression")
    @classmethod
    def validate_metric_expression(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        expression = " ".join(value.strip().split())
        if not METRIC_EXPRESSION_RE.match(expression):
            raise ValueError("metric_expression 仅支持 COUNT/SUM/AVG/MIN/MAX 聚合表达式")
        return expression.upper() if expression.upper() == "COUNT(*)" else expression

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value
        cleaned = []
        for dimension in value:
            item = dimension.strip()
            if not item:
                raise ValueError("dimensions 不能包含空值")
            if not IDENTIFIER_RE.match(item):
                raise ValueError("dimensions 只能包含安全字段名")
            cleaned.append(item)
        return cleaned

    @field_validator("time_column")
    @classmethod
    def validate_time_column(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        item = value.strip()
        if not IDENTIFIER_RE.match(item):
            raise ValueError("time_column 只能是安全字段名")
        return item


class SemanticMetricResponse(SemanticMetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SemanticMetricVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_id: int
    version_number: int
    snapshot: dict[str, Any]
    change_summary: Optional[str] = None
    created_by: int
    created_at: Optional[datetime] = None


class SemanticMetricRollbackRequest(BaseModel):
    version_number: int = Field(..., ge=1)


class SemanticMetricPermissionCreate(BaseModel):
    user_id: int = Field(..., ge=1)
    permission_level: str = Field("viewer", pattern=r"^(viewer|editor)$")


class SemanticMetricPermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_id: int
    user_id: int
    permission_level: str
    granted_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SemanticMetricQueryRequest(BaseModel):
    metric_key: str = Field(..., min_length=1, max_length=100)
    start_time: Optional[str] = Field(None, description="开始时间，按指标 time_column 过滤，包含边界")
    end_time: Optional[str] = Field(None, description="结束时间，按指标 time_column 过滤，不包含边界")
    dimensions: list[str] = Field(default_factory=list, description="需要返回的维度，必须来自指标定义")
    filters: dict[str, Any] = Field(default_factory=dict, description="等值过滤条件，字段必须来自指标定义维度或 time_column")
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=1000)

    @field_validator("dimensions")
    @classmethod
    def validate_query_dimensions(cls, value: list[str]) -> list[str]:
        cleaned = []
        for dimension in value:
            item = dimension.strip()
            if not item:
                raise ValueError("dimensions 不能包含空值")
            if not IDENTIFIER_RE.match(item):
                raise ValueError("dimensions 只能包含安全字段名")
            cleaned.append(item)
        return cleaned


class SemanticMetricSqlPreview(BaseModel):
    data_source_id: int
    sql: str
    params: dict[str, Any]
    page: int
    page_size: int


class SemanticMetricQueryResponse(BaseModel):
    metric: SemanticMetricResponse
    query: SQLQueryResponse
