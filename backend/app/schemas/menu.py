"""
菜单 Schema
"""
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class MenuBase(BaseModel):
    """菜单基础字段"""
    name: str
    path: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0
    parent_id: Optional[int] = None
    template_id: Optional[int] = None
    is_enabled: bool = True
    is_visible: bool = True
    remark: Optional[str] = None


class MenuCreate(MenuBase):
    """创建菜单"""
    pass


class MenuUpdate(BaseModel):
    """更新菜单"""
    name: Optional[str] = None
    path: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    parent_id: Optional[int] = None
    template_id: Optional[int] = None
    is_enabled: Optional[bool] = None
    is_visible: Optional[bool] = None
    remark: Optional[str] = None


class MenuResponse(MenuBase):
    """菜单响应"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class MenuTreeResponse(MenuBase):
    """菜单树形响应"""
    id: int
    created_at: Optional[datetime] = None
    children: List["MenuTreeResponse"] = []
    
    model_config = ConfigDict(from_attributes=True)