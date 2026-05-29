"""RCA 根因分析 API"""
import os
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.rca import (
    RcaMetricConfigCreate, RcaMetricConfigUpdate, RcaMetricConfigResponse,
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
    return RcaService(db).list_configs()


@router.post("/configs", response_model=RcaMetricConfigResponse)
async def create_config(
    payload: RcaMetricConfigCreate,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    return RcaService(db).create_config(payload.model_dump(), uid)


@router.put("/configs/{config_id}", response_model=RcaMetricConfigResponse)
async def update_config(
    config_id: int,
    payload: RcaMetricConfigUpdate,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    return RcaService(db).update_config(config_id, payload.model_dump(), uid)


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    RcaService(db).delete_config(config_id)
    return {"ok": True}


@router.post("/analyze")
async def trigger_analyze(
    payload: RcaAnalyzeRequest,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """触发 RCA 分析"""
    service = RcaService(db)
    task = service.trigger_analysis(payload.model_dump(), uid)
    result = service.execute_analysis(task.task_id)
    return {"task_id": task.task_id, **result}


@router.get("/tasks", response_model=List[RcaTaskResponse])
async def list_tasks(
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    return RcaService(db).list_tasks()


@router.get("/tasks/{task_id}", response_model=RcaTaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    task = RcaService(db).get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    RcaService(db).delete_task(task_id)
    return {"ok": True}


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


@router.get("/tasks/{task_id}/ai-analysis")
async def ai_analysis(
    task_id: str,
    db: Session = Depends(get_db),
    uid: int = Depends(get_current_user_id),
):
    """AI 解读异常数据（SSE 流式）"""
    from app.utils.llm_client import get_llm_client
    from app.models.rca import RcaAnalysisTask, RcaAnomaly, RcaMetricConfig

    task = db.query(RcaAnalysisTask).filter(RcaAnalysisTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    anomalies = db.query(RcaAnomaly).filter(RcaAnomaly.task_id == task_id).all()
    if not anomalies:
        raise HTTPException(status_code=400, detail="无异常数据")

    config = db.query(RcaMetricConfig).filter(RcaMetricConfig.id == task.metric_config_id).first()
    metric_name = config.name if config is not None else "未知指标"

    # 构建数据摘要
    summary_lines = []
    for a in anomalies:
        dim = a.dimension_path
        dim_type = [k for k in dim if k != 'name'][0] if len(dim) > 1 else list(dim.keys())[0]
        name = dim.get('name', dim[dim_type])
        summary_lines.append(
            f"- [{dim_type}] {name}({dim[dim_type]}): "
            f"当前={a.current_value:,.0f}, 基线={a.baseline_value:,.0f}, "
            f"变化={a.change_pct}%, 贡献度={a.contribution_pct}%, 严重度={a.severity}"
        )

    summary = "\n".join(summary_lines)

    # 读取提示词模板
    prompts_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'prompts')
    with open(os.path.join(prompts_dir, 'rca_analysis_system.md'), 'r', encoding='utf-8') as f:
        system_prompt = f.read().strip()
    with open(os.path.join(prompts_dir, 'rca_analysis_user.md'), 'r', encoding='utf-8') as f:
        user_template = f.read().strip()

    user_prompt = user_template.format(
        metric_name=metric_name,
        analysis_date=task.analysis_date,
        period_days=task.period_days,
        total_change_pct=task.summary.get('total_change_pct', 0) if task.summary else 0,
        anomaly_count=len(anomalies),
        anomaly_details=summary,
    )

    llm = get_llm_client()

    async def event_stream():
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            # 用普通 chat 生成完整结果，按行输出
            result = llm.chat(messages, temperature=0.3)
            lines = result.split('\n')
            for i, line in enumerate(lines):
                suffix = '\n' if i < len(lines) - 1 else ''
                yield f"data: {line + suffix}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
