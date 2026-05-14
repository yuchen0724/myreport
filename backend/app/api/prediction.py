from fastapi import APIRouter, Depends, HTTPException, Response
from datetime import datetime
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


@router.post("/train/{task_id}/stop")
def stop_train_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """停止正在运行的训练任务"""
    # 验证任务存在：查数据库
    repo = PredictionModelRepository(db)
    model = db.query(PredictionModel).filter(
        PredictionModel.task_id == task_id,
        PredictionModel.created_by == current_user.id,
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或无权操作")

    if model.status != "training":
        raise HTTPException(status_code=400, detail=f"任务状态为 {model.status}，不能停止")

    # 调用 Celery 撤销任务
    from app.celery_app import celery_app
    celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')

    # 更新数据库状态
    repo.update_status(model.id, "failed", error_message="用户手动停止")

    # 写入 Redis 状态
    from app.tasks.prediction_tasks import _get_redis, _progress_key, _PROGRESS_TTL
    r = _get_redis()
    key = _progress_key(task_id)
    r.hset(key, mapping={
        "status": "failed",
        "model_id": str(model.id),
        "error": "用户手动停止",
        "percent": "0",
        "phase": "已停止",
        "detail": "用户手动停止",
    })
    r.expire(key, _PROGRESS_TTL)

    return {"status": "stopped", "model_id": model.id}


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
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    with_progress: bool = True,
):
    """查询当前用户的训练任务"""
    user_id = current_user.id
    repo = PredictionModelRepository(db)
    from app.repositories.data_source_repository import DataSourceRepository
    ds_repo = DataSourceRepository(db)

    models = repo.get_running_by_user(user_id)
    # 也返回最近的已完成任务（最近5条，排除已删除的）
    recent = (
        db.query(PredictionModel)
        .filter(
            PredictionModel.created_by == user_id,
            PredictionModel.status.in_(["ready", "failed"]),
            PredictionModel.deleted_at.is_(None),
        )
        .order_by(PredictionModel.id.desc())
        .limit(5)
        .all()
    )
    all_items = list(models) + list(recent)
    result = []
    from app.tasks.prediction_tasks import get_async_task_progress
    for m in all_items:
        ds_name = ""
        ds = ds_repo.get_by_id(m.data_source_id)
        if ds:
            ds_name = ds.name
        item = {
            "model_id": m.id,
            "data_source_id": m.data_source_id,
            "data_source_name": ds_name,
            "status": m.status,
            "task_id": m.task_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            "error_message": m.error_message,
            "metrics": m.model_metrics,
        }
        if with_progress and m.task_id:
            try:
                prog = get_async_task_progress(m.task_id)
                item["progress"] = {
                    "percent": prog.get("percent", 0),
                    "phase": prog.get("phase", ""),
                    "detail": prog.get("detail", ""),
                    "status": prog.get("status", m.status),
                }
            except Exception:
                item["progress"] = None
        else:
            item["progress"] = None
        result.append(item)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return result


def _soft_delete_model(model, db):
    """软删除模型记录"""
    model.deleted_at = datetime.utcnow()
    db.commit()


@router.delete("/train/{model_id}/history", response_model=dict)
def delete_train_history(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = db.query(PredictionModel).filter(
        PredictionModel.id == model_id,
        PredictionModel.created_by == current_user.id,
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail="训练记录不存在或无权操作")
    if model.status in ("training",):
        raise HTTPException(status_code=400, detail="正在训练中的任务不能删除，请先停止")
    _soft_delete_model(model, db)
    return {"status": "deleted"}


@router.delete("/train/by-task/{task_id}/history", response_model=dict)
def delete_train_history_by_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = db.query(PredictionModel).filter(
        PredictionModel.task_id == task_id,
        PredictionModel.created_by == current_user.id,
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail="训练记录不存在或无权操作")
    if model.status in ("training",):
        raise HTTPException(status_code=400, detail="正在训练中的任务不能删除，请先停止")
    _soft_delete_model(model, db)
    return {"status": "deleted"}


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
