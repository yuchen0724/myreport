# backend/app/api/templates.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateVersionResponse,
    TemplateShareRequest,
    SharedTemplateResponse,
    TemplateShareUserResponse,
    UnshareRequest,
    PaginatedTemplateResponse,
)
from app.services.template_service import TemplateService

router = APIRouter(prefix="/api/templates", tags=["模板管理"])

@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """创建模板"""
    service = TemplateService(db)
    try:
        template = service.create_template(template_data, current_user_id)
        return template
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("", response_model=List[TemplateResponse])
async def get_templates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取模板列表（原始分页，无元数据）"""
    service = TemplateService(db)
    templates = service.get_templates(current_user_id, skip=skip, limit=limit)
    return templates

@router.get("/paginated", response_model=PaginatedTemplateResponse)
async def get_templates_paginated(
    page: int = 1,
    page_size: int = 100,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取模板列表（带分页元数据：total / page / page_size / total_pages）"""
    service = TemplateService(db)
    return service.get_templates_paginated(current_user_id, page=page, page_size=page_size)

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取模板详情"""
    service = TemplateService(db)
    template = service.get_template(template_id, current_user_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """更新模板"""
    service = TemplateService(db)
    try:
        return service.update_template(template_id, template_data, current_user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """删除模板"""
    service = TemplateService(db)
    service.delete_template(template_id, current_user_id)

@router.get("/{template_id}/versions", response_model=List[TemplateVersionResponse])
async def get_template_versions(
    template_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取模板版本列表"""
    service = TemplateService(db)
    versions = service.get_template_versions(template_id, current_user_id)
    return versions

@router.post("/{template_id}/rollback/{version}", response_model=TemplateResponse)
async def rollback_template(
    template_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """回滚模板到指定版本"""
    service = TemplateService(db)
    return service.rollback_template(template_id, version, current_user_id)

@router.post("/{template_id}/share")
async def share_template(
    template_id: int,
    share_request: TemplateShareRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """分享模板"""
    service = TemplateService(db)
    service.share_template(template_id, share_request, current_user_id)
    return {"success": True}

@router.get("/shared/me", response_model=List[SharedTemplateResponse])
async def get_shared_templates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取分享给我的模板列表"""
    service = TemplateService(db)
    templates = service.get_shared_templates(current_user_id, skip, limit)
    return templates

@router.get("/{template_id}/shares", response_model=List[TemplateShareUserResponse])
async def get_template_shares(
    template_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取模板的分享用户列表（仅模板所有者可查看）"""
    service = TemplateService(db)
    users = service.get_template_shares(template_id, current_user_id)
    return users

@router.post("/{template_id}/unshare")
async def unshare_template(
    template_id: int,
    request: UnshareRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """取消分享模板（仅模板所有者可操作）"""
    service = TemplateService(db)
    success = service.unshare_template(template_id, request.user_id, current_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="分享记录不存在")
    return {"success": True}

@router.get("/{template_id}/versions/diff")
async def get_version_diff(
    template_id: int,
    version1: int,
    version2: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取版本差异"""
    service = TemplateService(db)
    return service.get_version_diff(template_id, version1, version2, current_user_id)
