"""RCA 根因分析 API"""
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
    return RcaService(db).update_config(config_id, payload.model_dump())


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

    system_prompt = (
        "你是一位资深的零售业务数据分析师。请根据以下 RCA 根因分析结果，生成一份专业的业务解读报告。\n"
        "报告要求：\n"
        "1. 概述总体变化趋势和严重程度\n"
        "2. 按维度（品类/门店/商品）分析主要异常原因\n"
        "3. 找出贡献度最大的 TOP 3 异常项并深入分析\n"
        "4. 给出可执行的业务建议\n"
        "5. 用 Markdown 格式输出，使用标题、列表、加粗等格式\n"
        "6. 语言简洁专业，适合管理层阅读\n"
    )

    user_prompt = (
        f"指标：{metric_name}\n"
        f"分析日期：{task.analysis_date}\n"
        f"对比周期：{task.period_days}天\n"
        f"总体变化：{task.summary.get('total_change_pct', 0) if task.summary else 0}%\n"
        f"异常总数：{len(anomalies)}\n\n"
        f"异常明细：\n{summary}\n\n"
        f"请生成详细解读报告："
    )

    llm = get_llm_client()

    async def event_stream():
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            # 用普通 chat 生成完整结果，再逐块输出模拟流式
            result = llm.chat(messages, temperature=0.3)
            chunk_size = 20
            for i in range(0, len(result), chunk_size):
                yield f"data: {result[i:i+chunk_size]}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
