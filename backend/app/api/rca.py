"""RCA 根因分析 API"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.rca import (
    RcaMetricConfigCreate, RcaMetricConfigResponse,
    RcaAnalyzeRequest, RcaAnomalyResponse, RcaTaskResponse,
    RcaDrillDownRequest,
)
from app.services.rca_service import RcaService

router = APIRouter(prefix="/api/rca", tags=["RCA根因分析"])


@router.get("/configs", response_model=List[RcaMetricConfigResponse])
async def list_configs(
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """获取指标配置列表"""
    return RcaService(db).list_configs()


@router.post("/configs", response_model=RcaMetricConfigResponse)
async def create_config(
    payload: RcaMetricConfigCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """创建指标配置"""
    return RcaService(db).create_config(payload.model_dump(), uid)


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """删除指标配置"""
    ok = RcaService(db).delete_config(config_id)
    if not ok:
        raise HTTPException(404, "配置不存在")
    return {"ok": True}


@router.post("/analyze", response_model=RcaTaskResponse)
async def trigger_analyze(
    payload: RcaAnalyzeRequest,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """触发分析（同步执行）"""
    svc = RcaService(db)
    data = payload.model_dump()
    if "analysis_date" not in data or data["analysis_date"] is None:
        data["analysis_date"] = date.today()
    task = svc.trigger_analysis(data, uid)
    try:
        svc.execute_analysis(task.task_id)
    except Exception:
        pass
    # 重新查询获取最新状态
    from app.models.rca import RcaAnalysisTask
    task = db.query(RcaAnalysisTask).filter(RcaAnalysisTask.task_id == task.task_id).first()
    return task


@router.get("/tasks", response_model=List[RcaTaskResponse])
async def list_tasks(
    limit: int = 20,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """分析任务列表"""
    return RcaService(db).list_tasks(limit)


@router.get("/tasks/{task_id}", response_model=RcaTaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """任务详情"""
    from app.models.rca import RcaAnalysisTask
    task = db.query(RcaAnalysisTask).filter(RcaAnalysisTask.task_id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/tasks/{task_id}/anomalies", response_model=List[RcaAnomalyResponse])
async def get_anomalies(
    task_id: str,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """异常列表"""
    return RcaService(db).get_anomalies(task_id)


@router.post("/drill-down")
async def drill_down(
    payload: RcaDrillDownRequest,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """手动下钻查询"""
    rows = RcaService(db).drill_down(payload.model_dump())
    return {"rows": rows}
