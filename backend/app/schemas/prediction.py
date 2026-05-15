from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date


class TrainRequest(BaseModel):
    data_source_id: int = Field(..., description="数据源ID")
    train_days: Optional[int] = Field(None, description="训练用历史天数，默认使用配置值")
    table_name: Optional[str] = Field(
        None,
        description="销售数据表名（完整名称，如 retail_analysis.ads_cockpit_fd_store_ware_d）"
    )
    date_field: Optional[str] = Field(None, description="日期字段名，默认 dt")
    store_field: Optional[str] = Field(None, description="门店字段名，默认 store_code")
    sku_field: Optional[str] = Field(None, description="商品字段名，默认 matnr")
    target_field: Optional[str] = Field(None, description="目标值字段名，默认 actual_sale_untaxed_amt")


class TrainResponse(BaseModel):
    model_id: int
    status: str
    metrics: Optional[Dict[str, Any]] = None
    message: str
    task_id: Optional[str] = Field(None, description="异步任务 ID，可用于查询训练进度")


class PredictRequest(BaseModel):
    data_source_id: int = Field(..., description="数据源ID")
    model_id: Optional[int] = Field(None, description="模型ID，不传则使用最新模型")
    forecast_days: Optional[int] = Field(None, description="预测天数，默认30")
    table_name: Optional[str] = Field(
        None,
        description="销售数据表名（完整名称），与训练时一致"
    )


class PredictResponse(BaseModel):
    task_id: str
    status: str
    message: str


class ForecastQuery(BaseModel):
    data_source_id: int
    model_id: Optional[int] = Field(None, description="模型ID，筛选该模型生成的预测结果")
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


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    model_id: Optional[int] = None
    error: Optional[str] = None
    percent: Optional[int] = None
    phase: Optional[str] = None
    detail: Optional[str] = None


class TrainAndPredictRequest(BaseModel):
    data_source_id: int = Field(..., description="数据源ID")
    train_days: Optional[int] = Field(None, description="训练用历史天数，默认365")
    forecast_days: Optional[int] = Field(None, description="预测天数，默认30")
    table_name: Optional[str] = Field(
        None,
        description="销售数据表名（完整名称，如 retail_analysis.ads_cockpit_fd_store_ware_d）"
    )
