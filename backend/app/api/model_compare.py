"""模型对比 API

同一数据源/时间范围，多模型同时训练，对比 MAE/RMSE/R2 等指标
"""
import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth_deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-compare", tags=["模型对比"])


class CompareRequest(BaseModel):
    data_source_id: int = Field(..., description="数据源ID")
    model_types: List[str] = Field(..., description="要对比的模型类型列表", min_length=2, max_length=10)
    train_days: int = Field(default=365, description="训练天数")
    test_days: int = Field(default=30, description="测试天数")
    valid_days: int = Field(default=30, description="验证天数")
    table_name: str = Field(default="dwd_sales", description="数据表名")
    target_field: Optional[str] = None
    date_field: Optional[str] = None
    store_field: Optional[str] = None
    sku_field: Optional[str] = None


class CompareResultItem(BaseModel):
    model_type: str
    status: str
    task_id: Optional[str] = None
    metrics: dict = Field(default_factory=dict)
    error: Optional[str] = None
    trained_at: Optional[str] = None
    model_id: Optional[int] = None


class CompareResponse(BaseModel):
    compare_id: str
    status: str
    results: List[CompareResultItem] = Field(default_factory=list)
    created_at: Optional[str] = None


@router.post("/compare", response_model=CompareResponse)
def compare_models(
    req: CompareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发多模型对比训练

    对每种 model_type 分别提交异步训练任务，返回 compare_id 用于轮询结果。
    """
    valid_types = ["lightgbm", "prophet", "naive", "sarima"]
    invalid = [t for t in req.model_types if t not in valid_types]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的模型类型: {invalid}，可选: {valid_types}",
        )

    compare_id = str(uuid.uuid4())
    items = []

    from app.tasks.prediction_tasks import train_prediction_model_async, _get_redis

    # Store compare_id -> task_map in Redis for polling
    r = _get_redis()
    task_map = {}  # model_type -> task_id

    for mt in req.model_types:
        try:
            task = train_prediction_model_async.delay(
                data_source_id=req.data_source_id,
                model_type=mt,
                train_days=req.train_days,
                test_days=req.test_days,
                valid_days=req.valid_days,
                table_name=req.table_name,
                target_field=req.target_field,
                date_field=req.date_field,
                store_field=req.store_field,
                sku_field=req.sku_field,
                user_id=current_user.id,
            )
            task_map[mt] = task.id
            items.append(CompareResultItem(
                model_type=mt,
                status="pending",
                task_id=task.id,
            ))
        except Exception as e:
            items.append(CompareResultItem(
                model_type=mt,
                status="failed",
                error=str(e),
            ))

    # Persist task_map to Redis (expire after 24h)
    if r and task_map:
        import json
        r.setex(f"model_compare:{compare_id}", 86400, json.dumps(task_map))

    return CompareResponse(
        compare_id=compare_id,
        status="running",
        results=items,
    )


@router.get("/compare/{compare_id}")
def get_compare_status(
    compare_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询对比任务状态

    根据 compare_id 关联的 task_id 列表轮询各模型训练状态，
    返回最新指标。
    """
    # 从 Redis 获取任务跟踪（compare_id 在 Redis 中存储）
    from app.tasks.prediction_tasks import get_async_task_progress, _get_redis

    r = _get_redis()
    key = f"model_compare:{compare_id}"
    task_map = None
    if r:
        try:
            import json
            data = r.get(key)
            if data:
                task_map = json.loads(data)
        except Exception:
            pass

    if not task_map:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对比任务 {compare_id} 不存在或已过期",
        )

    results = []
    all_done = True

    for mt, tid in task_map.items():
        progress = get_async_task_progress(tid)
        item = CompareResultItem(
            model_type=mt,
            status=progress["status"],
            task_id=tid,
            metrics=progress.get("metrics", {}),
            error=progress.get("error"),
            model_id=progress.get("model_id"),
        )
        if progress["status"] not in ("pending", "running", "training"):
            # 已完成/失败
            # 尝试从 DB 获取更完整的 metrics
            from app.models.prediction import PredictionModel
            model = db.query(PredictionModel).filter(
                PredictionModel.task_id == tid,
                PredictionModel.created_by == current_user.id,
            ).first()
            if model and model.model_metrics:
                item.metrics = model.model_metrics
                item.model_id = model.id
                item.trained_at = model.trained_at.isoformat() if model.trained_at else None
            results.append(item)
        else:
            all_done = False
            results.append(item)

    overall = "completed" if all_done else "running"
    return CompareResponse(
        compare_id=compare_id,
        status=overall,
        results=results,
    )


@router.delete("/compare/{compare_id}")
def delete_compare(
    compare_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除对比任务及关联的训练记录"""
    from app.tasks.prediction_tasks import _get_redis
    from app.models.prediction import PredictionModel

    r = _get_redis()
    key = f"model_compare:{compare_id}"
    task_map = None
    if r:
        try:
            import json
            data = r.get(key)
            if data:
                task_map = json.loads(data)
                r.delete(key)
        except Exception:
            pass

    if not task_map:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对比任务不存在")

    # 删除关联的模型
    for tid in task_map.values():
        model = db.query(PredictionModel).filter(
            PredictionModel.task_id == tid,
            PredictionModel.created_by == current_user.id,
        ).first()
        if model:
            from app.api.prediction import _hard_delete_model
            _hard_delete_model(model, db)

    return {"status": "deleted"}
