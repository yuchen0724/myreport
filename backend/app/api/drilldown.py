"""钻取 API 端点"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.dashboard import DrilldownRequest, DrilldownResponse
from app.services.drilldown_service import DrilldownService

router = APIRouter(prefix="/api/drilldown", tags=["钻取"])


@router.post("/execute", response_model=DrilldownResponse)
async def execute_drilldown(
    payload: DrilldownRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    执行仪表盘钻取查询。

    请求体：
    - widget_id: 触发钻取的 Widget ID
    - template_id: 目标查询模板 ID
    - click_data: 图表点击数据（field, value, label）
    - params: 附加参数（可选）
    """
    service = DrilldownService(db)
    try:
        return service.execute_drilldown(payload, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/config/{widget_id}")
async def get_drilldown_config(
    widget_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取指定 Widget 的钻取配置"""
    service = DrilldownService(db)
    config = service.get_widget_drilldown_config(widget_id, current_user_id)
    if config is None:
        return {"enabled": False}
    return config
