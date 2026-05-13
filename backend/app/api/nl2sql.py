# backend/app/api/nl2sql.py
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.nl2sql import NL2SQLRequest, NL2SQLResponse
from app.services.nl2sql_service import NL2SQLService
from app.services.query_service import QueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nl2sql", tags=["NL2SQL"])

@router.get("/groups")
async def get_groups(
    data_source_id: int = Query(..., description="数据源ID"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """查询集团列表（从 dim_store 获取 group_id, group_name）"""
    # 检查数据源是否开启了集团加载
    from sqlalchemy import select
    from app.models.data_source import DataSource
    ds = db.execute(select(DataSource).where(DataSource.id == data_source_id)).scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not ds.load_group:
        return {"data": []}

    query_service = QueryService(db)
    nl2sql_service = NL2SQLService(query_service, db)
    try:
        groups = nl2sql_service.get_groups(data_source_id)
        return {"data": groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/groups/refresh")
async def refresh_groups_cache(
    data_source_id: int = Query(..., description="数据源ID"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """强制刷新指定数据源的集团缓存"""
    # 检查数据源是否开启了集团加载
    from sqlalchemy import select
    from app.models.data_source import DataSource
    ds = db.execute(select(DataSource).where(DataSource.id == data_source_id)).scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if not ds.load_group:
        return {"data": [], "message": "该数据源未开启集团加载"}

    query_service = QueryService(db)
    nl2sql_service = NL2SQLService(query_service, db)
    try:
        # 先删除 Redis 缓存
        from app.core.redis import redis_client
        redis_client.delete(f"nl2sql:groups:{data_source_id}")
        # 重新查询并缓存
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
    print(f"[API] 🌐 NL2SQL /parse 接口被调用", flush=True)
    print(f"[API] ├─ current_user_id: {current_user_id}", flush=True)
    print(f"[API] ├─ request: {request.model_dump_json(indent=2)}", flush=True)
    
    query_service = QueryService(db)
    nl2sql_service = NL2SQLService(query_service, db)

    try:
        print(f"[API] ├─ 调用 NL2SQLService.parse_question...", flush=True)
        response = nl2sql_service.parse_question(request, current_user_id)
        print(f"[API] └─ ✅ NL2SQLService.parse_question 执行成功", flush=True)
        return response
    except Exception as e:
        print(f"[API] ❌ NL2SQL 处理异常: {type(e).__name__}: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
