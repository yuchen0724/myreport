# backend/app/api/ai_analyst.py
"""
AI 数据分析师 API
- POST /api/ai-analyst/chat       — 同步对话
- POST /api/ai-analyst/chat/stream — 流式对话 (SSE)
- GET  /api/ai-analyst/schema     — 获取表结构
"""
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth_deps import get_current_admin_user, get_current_user_id
from app.schemas.ai_analyst import (
    AIAnalystChatRequest,
    AIAnalystChatResponse,
    AIAnalystSchemaRequest,
    AIAnalystSchemaResponse,
    AIAnalystFeedbackRequest,
    AIAnalystFeedbackResponse,
    SQLCorrectionItem,
    SQLCorrectionReviewRequest,
)
from app.services.ai_analyst_service import AIAnalystService
from app.services.sql_correction_service import SqlCorrectionService
from app.services.data_source_service import DataSourceService
from app.models.sql_correction import SqlCorrection
from app.models.user import User
from app.exceptions import BaseAppException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai-analyst", tags=["AI 数据分析师"])


def _get_service(db: Session = Depends(get_db)) -> AIAnalystService:
    return AIAnalystService(db)


@router.post("/chat", response_model=AIAnalystChatResponse)
async def chat(
    request: AIAnalystChatRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    同步对话接口（非流式）

    - **message**: 用户消息
    - **data_source_id**: 数据源 ID
    - **conversation_id**: 对话 ID（可选，用于多轮对话）
    - **group_id**: 集团 ID（可选）
    """
    service = AIAnalystService(db)
    try:
        response = service.chat(
            message=request.message,
            data_source_id=request.data_source_id,
            conversation_id=request.conversation_id,
            group_id=request.group_id,
            user_id=current_user_id,
        )
        return response
    except BaseAppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"[AI-Analyst] 对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(
    request: AIAnalystChatRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    流式对话接口 (SSE)

    返回 Server-Sent Events 流，事件类型:
    - token: 文本内容片段
    - tool_call: 工具调用开始
    - tool_result: 工具执行结果
    - chart: 图表配置
    - done: 对话完成
    - error: 错误
    """
    service = AIAnalystService(db)

    async def event_generator():
        try:
            async for chunk in service.chat_stream(
                message=request.message,
                data_source_id=request.data_source_id,
                conversation_id=request.conversation_id,
                group_id=request.group_id,
                user_id=current_user_id,
            ):
                event_type = chunk.get("type", "token")
                data = json.dumps(chunk, ensure_ascii=False, default=str)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as e:
            logger.error(f"[AI-Analyst] 流式对话失败: {e}", exc_info=True)
            error_data = json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback", response_model=AIAnalystFeedbackResponse)
async def feedback(
    request: AIAnalystFeedbackRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    提交 SQL 修正反馈，用于持续优化 LLM 生成质量。

    - **data_source_id**: 数据源 ID
    - **question**: 用户原始问题
    - **original_sql**: LLM 生成的有问题的 SQL
    - **corrected_sql**: 用户修正后的正确 SQL
    - **user_feedback**: 用户的文字反馈（可选）
    """
    DataSourceService(db).require_access(request.data_source_id, current_user_id)
    service = SqlCorrectionService(db)
    try:
        record = service.save_correction(
            data_source_id=request.data_source_id,
            question=request.question,
            original_sql=request.original_sql,
            corrected_sql=request.corrected_sql,
            user_feedback=request.user_feedback,
            user_id=current_user_id,
            review_status="candidate",
            source="user_feedback",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AIAnalystFeedbackResponse(
        id=record.id,
        message="反馈已提交，审核通过后将用于 SQL 学习",
    )


@router.get("/feedback/candidates", response_model=List[SQLCorrectionItem])
async def list_feedback_candidates(
    data_source_id: int = Query(..., description="数据源 ID"),
    status: str = Query("candidate", description="candidate / verified / rejected"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    DataSourceService(db).require_access(data_source_id, current_user.id)
    try:
        return SqlCorrectionService(db).list_for_review(data_source_id, status, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/feedback/{correction_id}/review", response_model=SQLCorrectionItem)
async def review_feedback_candidate(
    correction_id: int,
    request: SQLCorrectionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    service = SqlCorrectionService(db)
    record = db.query(SqlCorrection).filter(SqlCorrection.id == correction_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="SQL 学习案例不存在")
    DataSourceService(db).require_access(record.data_source_id, current_user.id)
    return service.review_correction(
        correction_id=correction_id,
        approved=request.approved,
        reviewer_id=current_user.id,
        review_comment=request.comment,
    )


@router.get("/schema", response_model=AIAnalystSchemaResponse)
async def get_schema(
    data_source_id: int = Query(..., description="数据源 ID"),
    table_name: str = Query(None, description="指定表名（可选）"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    获取数据库表结构

    - **data_source_id**: 数据源 ID
    - **table_name**: 指定表名（可选）
    """
    service = AIAnalystService(db)
    try:
        result = service.get_schema(data_source_id, table_name, current_user_id)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "获取 schema 失败"))
        return AIAnalystSchemaResponse(
            tables=result.get("tables", []),
            total_count=result.get("total_count", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AI-Analyst] 获取 schema 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取 schema 失败: {str(e)}")
