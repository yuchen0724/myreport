from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth_deps import get_current_user
from app.core.database import get_db
from app.services.prediction_service import PredictionService
from app.schemas.prediction import (
    TrainRequest, TrainResponse,
    PredictRequest, PredictResponse,
    ForecastQuery, ForecastListResponse, ForecastItem,
    TaskStatusResponse,
)
from app.models.prediction import PredictionModel
from app.repositories.prediction_repository import PredictionResultRepository, PredictionModelRepository
from app.models.user import User

router = APIRouter(prefix="/api/prediction", tags=["预测"])


@router.post("/train", response_model=TrainResponse)
def train_model(
    req: TrainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发异步模型训练"""
    user_id = current_user.id
    from app.tasks.prediction_tasks import train_prediction_model_async
    task = train_prediction_model_async.delay(
        data_source_id=req.data_source_id,
        train_days=req.train_days,
        table_name=req.table_name,
        target_field=req.target_field,
        date_field=req.date_field,
        store_field=req.store_field,
        sku_field=req.sku_field,
        user_id=user_id,
    )
    return TrainResponse(
        model_id=0, status="pending",
        task_id=task.id,
        message=f"训练任务已提交，task_id={task.id}",
    )


@router.get("/train/status/{task_id}", response_model=TaskStatusResponse)
def get_train_status(
    task_id: str,
):
    """查询异步训练任务状态"""
    from app.tasks.prediction_tasks import get_async_task_progress
    progress = get_async_task_progress(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=progress["status"],
        model_id=progress.get("model_id"),
        error=progress.get("error"),
        percent=progress.get("percent"),
        phase=progress.get("phase"),
        detail=progress.get("detail"),
    )


@router.get("/train/tasks", response_model=list)
def get_my_train_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询当前用户的训练任务"""
    user_id = current_user.id
    repo = PredictionModelRepository(db)
    from app.repositories.data_source_repository import DataSourceRepository
    ds_repo = DataSourceRepository(db)

    models = repo.get_running_by_user(user_id)
    # 也返回最近的已完成任务（最近5条）
    recent = (
        db.query(PredictionModel)
        .filter(
            PredictionModel.created_by == user_id,
            PredictionModel.status.in_(["ready", "failed"]),
        )
        .order_by(PredictionModel.id.desc())
        .limit(5)
        .all()
    )
    all_items = list(models) + list(recent)
    result = []
    for m in all_items:
        ds_name = ""
        ds = ds_repo.get_by_id(m.data_source_id)
        if ds:
            ds_name = ds.name
        result.append({
            "model_id": m.id,
            "data_source_id": m.data_source_id,
            "data_source_name": ds_name,
            "status": m.status,
            "task_id": m.task_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            "error_message": m.error_message,
            "metrics": m.model_metrics,
        })
    return result


@router.post("/predict", response_model=PredictResponse)
def run_prediction(
    req: PredictRequest,
    db: Session = Depends(get_db),
):
    """运行预测"""
    service = PredictionService(db)
    try:
        count = service.predict(req.data_source_id, req.forecast_days, table_name=req.table_name)
        return PredictResponse(count=count, message=f"成功预测 {count} 条记录")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast", response_model=ForecastListResponse)
def get_forecast(
    req: ForecastQuery = Depends(),
    db: Session = Depends(get_db),
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
