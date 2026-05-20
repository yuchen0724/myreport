from fastapi import APIRouter, Depends, HTTPException, Response, Query, Body
from datetime import datetime, date, timezone, timedelta
from typing import Optional
import logging
from sqlalchemy.orm import Session
from app.core.auth_deps import get_current_user
from app.core.database import get_db
from app.services.prediction_service import PredictionService
from app.schemas.prediction import (
    TrainRequest, TrainResponse,
    PredictRequest, PredictResponse,
    ForecastQuery, ForecastExportQuery, ForecastListResponse, ForecastItem,
    TaskStatusResponse,
    TrainAndPredictRequest,
)
from app.models.prediction import PredictionModel, ForecastHistory
from app.repositories.prediction_repository import PredictionResultRepository, PredictionModelRepository, ForecastHistoryRepository
from app.models.user import User

router = APIRouter(prefix="/api/prediction", tags=["预测"])

logger = logging.getLogger("myreport")


@router.post("/train", response_model=TrainResponse)
def train_model(
    req: TrainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发异步模型训练"""
    user_id = current_user.id
    from app.tasks.prediction_tasks import train_prediction_model_async
    try:
        task = train_prediction_model_async.delay(
            data_source_id=req.data_source_id,
            train_days=req.train_days,
            test_days=req.test_days,
            valid_days=req.valid_days,
            table_name=req.table_name,
            target_field=req.target_field,
            date_field=req.date_field,
            store_field=req.store_field,
            sku_field=req.sku_field,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(
            f"训练任务提交失败: data_source_id={req.data_source_id}, "
            f"train_days={req.train_days}, error={e}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"任务提交失败：Celery 消息队列连接异常，请检查 Redis 和 Celery Worker 状态。"
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
    """停止正在运行的训练任务

    支持清理残留状态：即使数据库状态已不是 training（如 Worker 崩溃后状态未同步），
    也可执行清理操作（撤销 Celery 任务、清除 Redis 进度、标记数据库为 failed）。
    """
    repo = PredictionModelRepository(db)
    model = db.query(PredictionModel).filter(
        PredictionModel.task_id == task_id,
        PredictionModel.created_by == current_user.id,
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或无权操作")

    is_active = model.status in ("training", "pending")

    if is_active:
        # 调用 Celery 撤销任务
        from app.celery_app import celery_app
        celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')

    # 更新数据库状态（不管当前是什么状态，都标记为 failed）
    repo.update_status(model.id, "failed", error_message="用户手动停止")

    # 清除 Redis 进度
    from app.tasks.prediction_tasks import _get_redis, _progress_key, _PROGRESS_TTL
    r = _get_redis()
    key = _progress_key(task_id)
    r.delete(key)

    action = "已停止" if is_active else "已清理残留状态"
    return {"status": "stopped", "model_id": model.id, "action": action}


@router.post("/train-and-predict", response_model=PredictResponse)
def train_and_predict(
    req: TrainAndPredictRequest,
    current_user: User = Depends(get_current_user),
):
    """触发异步训练+预测（三阶段一键完成）"""
    user_id = current_user.id
    from app.tasks.prediction_tasks import train_and_predict_prediction_async
    logger.info(
        f"训练+预测提交: data_source_id={req.data_source_id}, "
        f"train_days={req.train_days}, test_days={req.test_days}, valid_days={req.valid_days}, "
        f"forecast_days={req.forecast_days}, batch_size={req.batch_size}, batch_unit={req.batch_unit}"
    )
    try:
        task = train_and_predict_prediction_async.delay(
            data_source_id=req.data_source_id,
            train_days=req.train_days,
            test_days=req.test_days,
            valid_days=req.valid_days,
            forecast_days=req.forecast_days,
            table_name=req.table_name,
            user_id=user_id,
            batch_size=req.batch_size,
            batch_unit=req.batch_unit,
        )
    except Exception as e:
        logger.error(
            f"训练+预测任务提交失败: data_source_id={req.data_source_id}, "
            f"train_days={req.train_days}, forecast_days={req.forecast_days}, "
            f"batch_size={req.batch_size}, batch_unit={req.batch_unit}, "
            f"error={e}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"任务提交失败：Celery 消息队列连接异常，请检查 Redis 和 Celery Worker 状态。"
        )
    return PredictResponse(
        task_id=task.id,
        status="pending",
        message=f"训练+预测任务已提交，task_id={task.id}",
    )


@router.post("/train-and-predict/{task_id}/stop")
def stop_train_and_predict_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """停止正在运行的训练+预测任务"""
    from app.celery_app import celery_app
    from app.tasks.prediction_tasks import _get_redis, _progress_key

    # 撤销 Celery 任务
    celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')

    # 清除 Redis 进度
    r = _get_redis()
    key = _progress_key(task_id)
    r.delete(key)

    # 更新预测模型状态（如果有）
    repo = PredictionModelRepository(db)
    model = db.query(PredictionModel).filter(
        PredictionModel.task_id == task_id,
        PredictionModel.created_by == current_user.id,
    ).first()
    if model:
        repo.update_status(model.id, "failed", error_message="用户手动停止")

    # 更新 forecast_history ��态（如果有）
    from app.repositories.prediction_repository import ForecastHistoryRepository
    hist_repo = ForecastHistoryRepository(db)
    hist_records = hist_repo.get_by_task_id(task_id)
    for hr in hist_records:
        hr.status = "failed"
        hr.error_message = "用户手动停止"
    if hist_records:
        db.commit()

    return {"status": "stopped", "task_id": task_id, "action": "已停止"}


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
    status: Optional[str] = Query(None, description="过滤状态: ready, running, failed, completed"),
    data_source_id: Optional[int] = Query(None, description="过滤数据源"),
):
    """查询当前用户的训练任务

    所有"运行中"状态从 Redis 读取，数据库只做历史归档。
    支持 status 和 data_source_id 参数过滤。
    """
    user_id = current_user.id
    repo = PredictionModelRepository(db)
    from app.repositories.data_source_repository import DataSourceRepository
    ds_repo = DataSourceRepository(db)
    from app.tasks.prediction_tasks import get_async_task_progress, get_running_task_ids

    # 从 Redis 获取当前运行中的 task_id 列表
    running_task_ids = get_running_task_ids()

    # 获取该用户所有模型记录
    all_models = repo.get_running_by_user(user_id)

    # 分离运行中 + 已完成，并修复 DB/Redis 不同步
    running_models = []
    recent_models = []
    seen_ids = set()
    seen_task_ids = set()
    fixed_count = 0
    for m in all_models:
        if m.id in seen_ids:
            continue
        seen_ids.add(m.id)
        if m.task_id:
            if m.task_id in seen_task_ids:
                continue
            seen_task_ids.add(m.task_id)
        if m.task_id and m.task_id in running_task_ids:
            running_models.append(m)
        elif m.status in ("ready", "failed") and m.deleted_at is None:
            recent_models.append(m)
        elif m.status == "training" and m.deleted_at is None:
            # DB 标记为 training 但 Redis 中已无记录 → 不同步，修正
            m.status = "failed"
            m.error_message = "任务因异常中断已恢复"
            db.flush()
            fixed_count += 1
            recent_models.append(m)

    if fixed_count:
        db.commit()

    logger.info(f"[训练列表] running_models={len(running_models)}, recent={len(recent_models)}, fixed={fixed_count}")

    # 也补上所有 running_task_ids 中能找到 DB 记录但上面没命中的
    for tid in running_task_ids:
        already = any(m.task_id == tid for m in running_models)
        if already:
            continue
        m = db.query(PredictionModel).filter(
            PredictionModel.task_id == tid,
            PredictionModel.created_by == user_id,
        ).first()
        if m:
            running_models.append(m)

    # 合并，运行中在前
    all_items = running_models + recent_models[:10]

    result = []
    for m in all_items:
        ds_name = ""
        ds = ds_repo.get_by_id(m.data_source_id)
        if ds:
            ds_name = ds.name

        # 根据 Redis 状态判定最终状态
        final_status = m.status
        if m.task_id and m.task_id in running_task_ids:
            final_status = "training"

        item = {
            "model_id": m.id,
            "data_source_id": m.data_source_id,
            "data_source_name": ds_name,
            "status": final_status,
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
    
    # 后端过滤：status 和 data_source_id
    if status:
        result = [r for r in result if r.get("status") == status]
    if data_source_id is not None:
        result = [r for r in result if r.get("data_source_id") == data_source_id]
    
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return result


def _soft_delete_model(model, db):
    """软删除模型记录"""
    from datetime import timezone, timedelta
    model.deleted_at = datetime.now(timezone(timedelta(hours=8)))
    db.commit()


def _hard_delete_model(model, db):
    """硬删除模型记录及关联的预测历史"""
    if model is None:
        return
    # 清理预测历史
    try:
        db.query(ForecastHistory).filter(
            ForecastHistory.model_id == model.id
        ).delete()
    except Exception:
        pass
    if model.task_id:
        try:
            db.query(ForecastHistory).filter(
                ForecastHistory.task_id == model.task_id
            ).delete()
        except Exception:
            pass
    # 清理模型
    db.delete(model)
    db.commit()

    # 清理 Redis 进度
    try:
        from app.tasks.prediction_tasks import _get_redis, _progress_key
        r = _get_redis()
        if r and model.task_id:
            r.delete(_progress_key(model.task_id))
    except Exception:
        pass


@router.delete("/history/{model_id}", response_model=dict)
def delete_model_history(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """硬删除训练模型及所有关联的预测历史"""
    model = db.query(PredictionModel).filter(
        PredictionModel.id == model_id,
        PredictionModel.created_by == current_user.id,
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail="记录不存在或无权操作")

    _hard_delete_model(model, db)

    return {"status": "deleted"}


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
    _hard_delete_model(model, db)
    return {"status": "deleted"}


@router.delete("/train/by-task/{task_id}/history", response_model=dict)
def delete_train_history_by_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通过 task_id 删除训练记录（task_id 为主键）
    
    即使 PredictionModel 不存在（任务在创建模型前就失败了），
    也确保清理 ForecastHistory + Redis 进度。
    """
    model = db.query(PredictionModel).filter(
        PredictionModel.task_id == task_id,
        PredictionModel.created_by == current_user.id,
    ).first()

    if model:
        if model.status in ("training",):
            raise HTTPException(status_code=400, detail="正在训练中的任务不能删除，请先停止")
        _hard_delete_model(model, db)

    # 始终清理关联的预测历史记录
    try:
        db.query(ForecastHistory).filter(
            ForecastHistory.task_id == task_id
        ).delete()
        db.commit()
    except Exception:
        pass

    # 始终清理 Redis 进度
    try:
        from app.tasks.prediction_tasks import _get_redis, _progress_key
        r = _get_redis()
        if r:
            r.delete(_progress_key(task_id))
    except Exception:
        pass

    return {"status": "deleted"}


@router.post("/predict", response_model=PredictResponse)
def run_prediction(
    req: PredictRequest,
    db: Session = Depends(get_db),
):
    """触发异步预测 - 返回 task_id"""
    from app.tasks.prediction_tasks import predict_prediction_model_async
    task = predict_prediction_model_async.delay(
        data_source_id=req.data_source_id,
        forecast_days=req.forecast_days,
        table_name=req.table_name,
        model_id=req.model_id,
    )
    return PredictResponse(
        task_id=task.id,
        status="pending",
        message=f"预测任务已提交，task_id={task.id}",
    )


@router.get("/predict/status/{task_id}", response_model=TaskStatusResponse)
def get_predict_status(
    task_id: str,
):
    """查询异步预测任务状态"""
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


@router.get("/forecast", response_model=ForecastListResponse)
def get_forecast(
    req: ForecastQuery = Depends(),
    db: Session = Depends(get_db),
):
    """查询预测结果"""
    repo = PredictionResultRepository(db)
    total = repo.count_forecast(
        req.data_source_id, req.model_id, req.store_code, req.matnr,
        req.start_date, req.end_date,
    )
    results = repo.get_forecast(
        req.data_source_id, req.model_id, req.store_code, req.matnr,
        req.start_date, req.end_date,
        req.sort_by or "forecast_date", req.sort_order or "asc",
        req.page_size, (req.page - 1) * req.page_size,
    )

    # 已有预测结果可能没有 ware_name，查询时实时补填
    need_fill = [r for r in results if not r.ware_name]
    if need_fill:
        from app.services.prediction_service import PredictionService
        svc = PredictionService(db)
        pairs = [(r.store_code, r.matnr) for r in need_fill]
        unique_pairs = list({s: m for s, m in pairs})  # dedupe preserving last
        unique_pairs = list(set(pairs))  # simple dedupe
        name_map = svc._lookup_ware_names(req.data_source_id, unique_pairs)
        for r in need_fill:
            r.ware_name = name_map.get((r.store_code, r.matnr), "")

    items = [ForecastItem(
        id=r.id, store_code=r.store_code, matnr=r.matnr,
        ware_name=r.ware_name,
        forecast_date=r.forecast_date, predicted_value=r.predicted_value,
        lower_bound=r.lower_bound, upper_bound=r.upper_bound,
    ) for r in results]
    return ForecastListResponse(items=items, total=total)


@router.post("/forecast/export")
def export_forecast(
    data_source_id: int = Body(...),
    model_id: Optional[int] = Body(None),
    store_code: Optional[str] = Body(None),
    matnr: Optional[str] = Body(None),
    start_date: Optional[date] = Body(None),
    end_date: Optional[date] = Body(None),
    sort_by: Optional[str] = Body("forecast_date"),
    sort_order: Optional[str] = Body("asc"),
    db: Session = Depends(get_db),
):
    """导出预测结果为 Excel（同步，适用于万级数据量）"""
    from fastapi.responses import StreamingResponse
    import pandas as pd
    from io import BytesIO

    repo = PredictionResultRepository(db)
    results = repo.get_forecast(
        data_source_id, model_id, store_code, matnr,
        start_date, end_date,
        sort_by or "forecast_date", sort_order or "asc",
        limit=100000, offset=0,
    )

    data = [{
        "门店编码": r.store_code,
        "商品编码": r.matnr,
        "商品名称": r.ware_name or "",
        "预测日期": r.forecast_date.isoformat(),
        "预测值": r.predicted_value,
        "下限": r.lower_bound if r.lower_bound is not None else "",
        "上限": r.upper_bound if r.upper_bound is not None else "",
    } for r in results]

    if not data:
        data = [{"门店编码": "", "商品编码": "", "商品名称": "", "预测日期": "", "预测值": "", "下限": "", "上限": ""}]

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="预测结果")
    output.seek(0)

    filename = f"预测结果_{datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/forecast/running")
def get_forecast_running(
    current_user: User = Depends(get_current_user),
):
    """查询当前正在运行的预测任务"""
    from app.tasks.prediction_tasks import get_running_task_ids, get_async_task_progress
    from app.core.database import SessionLocal

    running_ids = get_running_task_ids()
    if not running_ids:
        return []

    db = SessionLocal()
    try:
        from app.repositories.prediction_repository import ForecastHistoryRepository
        from app.repositories.data_source_repository import DataSourceRepository
        fh_repo = ForecastHistoryRepository(db)
        ds_repo = DataSourceRepository(db)

        result = []
        for tid in running_ids:
            try:
                prog = get_async_task_progress(tid)
            except Exception:
                prog = {}
            status = prog.get("status", "running")
            if status != "running":
                continue

            # 查 forecast_history 获取 data_source_id 等信息
            hist = None
            try:
                hist = db.query(ForecastHistory).filter(
                    ForecastHistory.task_id == tid,
                ).first()
            except Exception:
                pass

            ds_name = ""
            data_source_id = None
            if hist:
                data_source_id = hist.data_source_id
                ds = ds_repo.get_by_id(hist.data_source_id)
                if ds:
                    ds_name = ds.name

            result.append({
                "task_id": tid,
                "model_id": prog.get("model_id"),
                "data_source_id": data_source_id,
                "data_source_name": ds_name,
                "percent": prog.get("percent", 0),
                "phase": prog.get("phase", ""),
                "detail": prog.get("detail", ""),
                "status": status,
            })
        return result
    finally:
        db.close()


@router.get("/forecast/history")
def get_forecast_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """查询当前用户的预测历史列表"""
    repo = ForecastHistoryRepository(db)
    from app.repositories.data_source_repository import DataSourceRepository
    ds_repo = DataSourceRepository(db)
    records = repo.get_by_user(user_id=current_user.id, skip=skip, limit=limit)
    result = []
    for r in records:
        ds_name = ""
        ds = ds_repo.get_by_id(r.data_source_id)
        if ds:
            ds_name = ds.name
        result.append({
            "id": r.id,
            "task_id": r.task_id,
            "model_id": r.model_id,
            "data_source_id": r.data_source_id,
            "data_source_name": ds_name,
            "forecast_days": r.forecast_days,
            "result_count": r.result_count,
            "status": r.status,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return result


@router.delete("/forecast/progress/{task_id}")
def delete_forecast_progress(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """删除预测任务的 Redis 进度记录和 DB 历史"""
    from app.tasks.prediction_tasks import _get_redis, _progress_key
    from app.core.database import SessionLocal

    r = _get_redis()
    if r:
        try:
            key = _progress_key(task_id)
            r.delete(key)
        except Exception:
            pass

    # 同时清理数据
    try:
        db = SessionLocal()
        try:
            records = db.query(ForecastHistory).filter(
                ForecastHistory.task_id == task_id
            ).all()
            for rec in records:
                db.delete(rec)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass

    return {"success": True, "message": "已清理"}
