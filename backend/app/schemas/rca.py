"""RCA 请求/响应 Schema"""
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RcaMetricConfigCreate(BaseModel):
    name: str
    label: str
    metric_field: str
    source_table: str
    threshold_type: str = "percent_change"
    threshold_value: float = 10.0
    compare_type: str = "mom"
    drill_dimensions: List[str] = ["operation_category1_name", "store_code", "matnr"]
    group_id: int
    data_source_id: int


class RcaMetricConfigResponse(BaseModel):
    id: int
    name: str
    label: str
    metric_field: str
    source_table: str
    threshold_type: str
    threshold_value: float
    compare_type: str
    drill_dimensions: List[str]
    group_id: int
    data_source_id: int
    enabled: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class RcaTaskResponse(BaseModel):
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

    class Config:
        from_attributes = True
