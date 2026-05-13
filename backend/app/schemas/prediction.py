from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date


class TrainRequest(BaseModel):
    data_source_id: int = Field(..., description="数据源ID")
    train_days: Optional[int] = Field(None, description="训练用历史天数，默认使用配置值")


class TrainResponse(BaseModel):
    model_id: int
    status: str
    metrics: Optional[Dict[str, Any]] = None
    message: str


class PredictRequest(BaseModel):
    data_source_id: int
    forecast_days: Optional[int] = Field(None, description="预测天数，默认30")


class PredictResponse(BaseModel):
    count: int
    message: str


class ForecastQuery(BaseModel):
    data_source_id: int
    store_code: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=1000)


class ForecastItem(BaseModel):
    id: int
    store_code: str
    matnr: str
    forecast_date: date
    predicted_value: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class ForecastListResponse(BaseModel):
    items: List[ForecastItem]
    total: int
