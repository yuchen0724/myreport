# backend/app/schemas/favorite.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FavoriteBase(BaseModel):
    template_id: int
    category: str = "默认"
    note: Optional[str] = None

class FavoriteCreate(FavoriteBase):
    pass

class FavoriteUpdate(BaseModel):
    category: Optional[str] = None
    note: Optional[str] = None

class FavoriteResponse(FavoriteBase):
    id: int
    user_id: int
    created_at: datetime
    # 可选：返回模板信息
    template_name: Optional[str] = None
    template_description: Optional[str] = None

    class Config:
        from_attributes = True
