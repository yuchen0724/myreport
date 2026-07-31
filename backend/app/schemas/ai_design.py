"""Schemas for AI-assisted report and metric drafts."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ReportDraftRequest(BaseModel):
    data_source_id: int
    requirement: str = Field(..., min_length=3, max_length=2000)
    preferred_chart: Optional[str] = None


class GeneratedReportDraft(BaseModel):
    name: str
    description: str = ""
    sql: str = ""
    chart_type: str = "table"
    dimensions: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    metric_keys: list[str] = Field(default_factory=list)
    reasoning: str = ""


class MetricDraftRequest(BaseModel):
    data_source_id: int
    requirement: str = Field(..., min_length=3, max_length=2000)


class GeneratedMetricDraft(BaseModel):
    metric_key: str
    name: str
    description: str = ""
    base_sql: str
    metric_expression: str
    dimensions: list[str] = Field(default_factory=list)
    time_column: str
    reasoning: str = ""
