# backend/app/api/favorites.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.favorite import (
    FavoriteCreate,
    FavoriteUpdate,
    FavoriteResponse,
)
from app.services.favorite_service import FavoriteService

router = APIRouter(prefix="/api/favorites", tags=["收藏夹管理"])

@router.get("", response_model=List[FavoriteResponse])
async def get_favorites(
    category: Optional[str] = Query(None, description="按分类筛选"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取收藏夹列表"""
    service = FavoriteService(db)
    return service.get_favorites(current_user_id, category)

@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    data: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """添加收藏"""
    service = FavoriteService(db)
    return service.add_favorite(data, current_user_id)

@router.put("/{favorite_id}", response_model=FavoriteResponse)
async def update_favorite(
    favorite_id: int,
    data: FavoriteUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """更新收藏"""
    service = FavoriteService(db)
    favorite = service.update_favorite(favorite_id, data, current_user_id)
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return favorite

@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    favorite_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """取消收藏"""
    service = FavoriteService(db)
    success = service.remove_favorite(favorite_id, current_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Favorite not found")

@router.delete("/by-template/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite_by_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """根据模板ID取消收藏"""
    service = FavoriteService(db)
    success = service.remove_favorite_by_template(template_id, current_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Favorite not found")

@router.get("/check/{template_id}")
async def check_favorite(
    template_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """检查是否已收藏"""
    service = FavoriteService(db)
    is_fav = service.is_favorited(template_id, current_user_id)
    return {"is_favorited": is_fav}
