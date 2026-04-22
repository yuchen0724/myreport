# backend/app/schemas/template.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class TemplateBase(BaseModel):
    """模板基础模式"""
    name: str = Field(..., description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    config: Dict[str, Any] = Field(..., description="模板配置")
    is_public: bool = Field(False, description="是否公开")

class TemplateCreate(TemplateBase):
    """创建模板"""
    pass

class TemplateUpdate(BaseModel):
    """更新模板"""
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None

class TemplateResponse(TemplateBase):
    """模板响应"""
    id: int
    version: int
    created_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TemplateVersionResponse(BaseModel):
    """模板版本响应"""
    id: int
    template_id: int
    version: int
    config: Dict[str, Any]
    created_by: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TemplateShareRequest(BaseModel):
    """模板分享请求"""
    user_ids: List[int] = Field(..., description="分享给的用户 ID 列表")

class SharedTemplateResponse(TemplateResponse):
    """分享的模板响应"""
    shared_by: Optional[int] = None
    shared_by_username: Optional[str] = None
    shared_at: Optional[datetime] = None
