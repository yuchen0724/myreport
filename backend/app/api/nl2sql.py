# backend/app/api/nl2sql.py
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.core.deps import get_data_source_or_404
from app.models.data_source import DataSource
from app.schemas.nl2sql import NL2SQLRequest, NL2SQLResponse
from app.services.nl2sql_service import NL2SQLService
from app.services.query_service import QueryService
from app.exceptions import BaseAppException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nl2sql", tags=["NL2SQL"])

@router.get("/groups")
async def get_groups(
    data_source_id: int = Query(..., description="数据源ID"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
    ds: DataSource = Depends(get_data_source_or_404),
):
    """查询集团列表（从 dim_store 获取 group_id, group_name）"""
    if not ds.load_group:
        return {"data": []}

    query_service = QueryService(db)
    nl2sql_service = NL2SQLService(query_service, db)
    try:
        groups = nl2sql_service.get_groups(data_source_id)
        return {"data": groups}
    except BaseAppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/groups/refresh")
async def refresh_groups_cache(
    data_source_id: int = Query(..., description="数据源ID"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
    ds: DataSource = Depends(get_data_source_or_404),
):
    """强制刷新指定数据源的集团缓存"""
    if not ds.load_group:
        return {"data": [], "message": "该数据源未开启集团加载"}

    query_service = QueryService(db)
    nl2sql_service = NL2SQLService(query_service, db)
    try:
        from app.core.redis import redis_client
        redis_client.delete(f"nl2sql:groups:{data_source_id}")
        groups = nl2sql_service.get_groups(data_source_id)
        return {"data": groups, "message": "缓存已刷新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/parse", response_model=NL2SQLResponse)
async def parse_question(
    request: NL2SQLRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    解析自然语言问题并执行查询

    - **question**: 自然语言问题
    - **data_source_id**: 数据源 ID
    """
    logger.info("NL2SQL /parse called | user_id=%s request=%s", current_user_id, request.model_dump_json(indent=2))

    query_service = QueryService(db)
    nl2sql_service = NL2SQLService(query_service, db)

    try:
        logger.info("Calling NL2SQLService.parse_question...")
        response = nl2sql_service.parse_question(request, current_user_id)
        logger.info("NL2SQL /parse succeeded")
        return response
    except BaseAppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error("NL2SQL /parse failed: %s: %s", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail=str(e))
