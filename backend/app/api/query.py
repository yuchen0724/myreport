from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.query import SQLQueryRequest, SQLQueryResponse
from app.services.query_service import QueryService

router = APIRouter(prefix="/api/query", tags=["查询"])


@router.post("/sql", response_model=SQLQueryResponse)
async def execute_sql(
    request: SQLQueryRequest,
    db: Session = Depends(get_db),
    current_user_id: int = 1  # TODO: 从 JWT 获取
):
    """执行 SQL 查询"""
    query_service = QueryService(db)
    try:
        return query_service.execute_sql(request, current_user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
