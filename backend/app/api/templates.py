# backend/app/api/templates.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateVersionResponse,
    TemplateShareRequest
)
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["Templates"])

@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """创建模板"""
    service = TemplateService(db)
    template = service.create_template(template_data, current_user_id)
    return template

@router.get("", response_model=List[TemplateResponse])
async def get_templates(
    user_id: int = None,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """获取模板列表"""
    service = TemplateService(db)
    templates = service.get_templates(user_id or current_user_id)
    return templates

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """获取模板详情"""
    service = TemplateService(db)
    template = service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """更新模板"""
    service = TemplateService(db)
    template = service.update_template(template_id, template_data, current_user_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """删除模板"""
    service = TemplateService(db)
    success = service.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return None

@router.get("/{template_id}/versions", response_model=List[TemplateVersionResponse])
async def get_template_versions(
    template_id: int,
    db: Session = Depends(get_db)
):
    """获取模板版本列表"""
    service = TemplateService(db)
    versions = service.get_template_versions(template_id)
    return versions

@router.post("/{template_id}/rollback/{version}", response_model=TemplateResponse)
async def rollback_template(
    template_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """回滚模板到指定版本"""
    service = TemplateService(db)
    template = service.rollback_template(template_id, version, current_user_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template or version not found")
    return template

@router.post("/{template_id}/share")
async def share_template(
    template_id: int,
    share_request: TemplateShareRequest,
    db: Session = Depends(get_db),
    current_user_id: int = 3  # TODO: 从 JWT 获取
):
    """分享模板"""
    service = TemplateService(db)
    success = service.share_template(template_id, share_request, current_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True}
