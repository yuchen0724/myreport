# backend/app/api/ai_analyst.py
"""
AI 数据分析师 API
- POST /api/ai-analyst/chat       — 同步对话
- POST /api/ai-analyst/chat/stream — 流式对话 (SSE)
- GET  /api/ai-analyst/schema     — 获取表结构
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.ai_analyst import (
    AIAnalystChatRequest,
    AIAnalystChatResponse,
    AIAnalystSchemaRequest,
    AIAnalystSchemaResponse,
)
from app.services.ai_analyst_service import AIAnalystService

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
        result = service.get_schema(data_source_id, table_name)
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
