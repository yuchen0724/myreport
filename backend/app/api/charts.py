# backend/app/api/charts.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.chart import ChartRequest, ChartResponse
from app.services.chart_service import ChartService
from app.services.query_service import QueryService

router = APIRouter(prefix="/api/charts", tags=["Charts"])

@router.post("/generate", response_model=ChartResponse)
async def generate_chart(
    request: ChartRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    生成图表数据

    - **data_source_id**: 数据源 ID
    - **sql**: SQL 查询
    - **chart_config**: 图表配置
    """
    query_service = QueryService(db)
    chart_service = ChartService(query_service)

    try:
        response = chart_service.generate_chart(request, current_user_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
