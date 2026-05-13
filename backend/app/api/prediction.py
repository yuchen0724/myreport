from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth_deps import get_current_user
from app.core.database import get_db
from app.services.prediction_service import PredictionService
from app.schemas.prediction import (
    TrainRequest, TrainResponse,
    PredictRequest, PredictResponse,
    ForecastQuery, ForecastListResponse, ForecastItem,
)
from app.repositories.prediction_repository import PredictionResultRepository

router = APIRouter(prefix="/api/prediction", tags=["预测"])


@router.post("/train", response_model=TrainResponse)
def train_model(
    req: TrainRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """触发模型训练"""
    service = PredictionService(db)
    try:
        model_id = service.train(req.data_source_id, req.train_days)
        return TrainResponse(model_id=model_id, status="success", message="训练完成")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict", response_model=PredictResponse)
def run_prediction(
    req: PredictRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """运行预测"""
    service = PredictionService(db)
    try:
        count = service.predict(req.data_source_id, req.forecast_days)
        return PredictResponse(count=count, message=f"成功预测 {count} 条记录")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast", response_model=ForecastListResponse)
def get_forecast(
    req: ForecastQuery = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """查询预测结果"""
    repo = PredictionResultRepository(db)
    results = repo.get_forecast(
        req.data_source_id, req.store_code,
        req.start_date, req.end_date,
        req.page_size, (req.page - 1) * req.page_size,
    )
    items = [ForecastItem(
        id=r.id, store_code=r.store_code, matnr=r.matnr,
        forecast_date=r.forecast_date, predicted_value=r.predicted_value,
        lower_bound=r.lower_bound, upper_bound=r.upper_bound,
    ) for r in results]
    return ForecastListResponse(items=items, total=len(items))
