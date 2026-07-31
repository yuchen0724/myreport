"""Inventory decision copilot API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth_deps import get_current_user_id
from app.core.database import get_db
from app.schemas.inventory_copilot import InventoryCopilotRequest
from app.services.inventory_copilot_service import InventoryCopilotService


router = APIRouter(prefix="/api/inventory-copilot", tags=["进销存决策助手"])


@router.post("/analyze")
async def analyze_inventory(
    request: InventoryCopilotRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    try:
        return InventoryCopilotService(db).analyze(request, current_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
