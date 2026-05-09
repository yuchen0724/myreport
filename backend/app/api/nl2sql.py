# backend/app/api/nl2sql.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.nl2sql import NL2SQLRequest, NL2SQLResponse
from app.services.nl2sql_service import NL2SQLService
from app.services.query_service import QueryService

router = APIRouter(prefix="/api/nl2sql", tags=["NL2SQL"])

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
    query_service = QueryService(db)
    nl2sql_service = NL2SQLService(query_service, db)

    try:
        response = nl2sql_service.parse_question(request, current_user_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
