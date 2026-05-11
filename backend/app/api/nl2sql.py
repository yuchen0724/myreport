# backend/app/api/nl2sql.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.nl2sql import NL2SQLRequest, NL2SQLResponse
from app.services.nl2sql_service import NL2SQLService
from app.services.query_service import QueryService

logger = logging.getLogger(__name__)

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
