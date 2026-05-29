"""RCA 请求/响应 Schema"""
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class RcaMetricConfigCreate(BaseModel):
    name: str
    label: str
    metric_field: str
    source_table: str
    semantic_metric_key: Optional[str] = None
    threshold_type: str = "percent_change"
    threshold_value: float = 10.0
    compare_type: str = "mom"
    drill_dimensions: List[str] = ["operation_category1_name", "store_code", "matnr"]
    group_id: int
    data_source_id: int


class RcaMetricConfigUpdate(BaseModel):
    name: Optional[str] = None
    label: Optional[str] = None
    metric_field: Optional[str] = None
    source_table: Optional[str] = None
    semantic_metric_key: Optional[str] = None
    threshold_type: Optional[str] = None
    threshold_value: Optional[float] = None
    compare_type: Optional[str] = None
    drill_dimensions: Optional[List[str]] = None
    group_id: Optional[int] = None
    data_source_id: Optional[int] = None
    enabled: Optional[bool] = None


class RcaMetricConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    label: str
    metric_field: str
    source_table: str
    semantic_metric_key: Optional[str] = None
    threshold_type: str
    threshold_value: float
    compare_type: str
    drill_dimensions: List[str]
    group_id: int
    data_source_id: int
    enabled: bool
    created_at: Optional[datetime] = None


class RcaAnalyzeRequest(BaseModel):
    metric_config_id: int
    analysis_date: date = Field(default_factory=date.today)
    period_days: int = 7


class RcaDrillDownRequest(BaseModel):
    task_id: str
    metric_name: str
    dimension: Optional[str] = None
    dimension_value: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class RcaAnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    metric_name: str
    dimension_path: Dict[str, Any]
    current_value: Optional[float] = None
    baseline_value: Optional[float] = None
    change_pct: Optional[float] = None
    severity: str
    contribution_pct: Optional[float] = None
    root_cause_hint: Optional[str] = None
    drill_details: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class RcaTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    metric_config_id: int
    analysis_date: date
    period_days: int
    status: str
    anomaly_count: Optional[int] = None
    summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
