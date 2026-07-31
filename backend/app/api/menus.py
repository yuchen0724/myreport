"""
菜单 API
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id, get_current_admin_user
from app.models.user import User
from app.services.menu_service import MenuService
from app.schemas.menu import MenuCreate, MenuUpdate, MenuResponse

router = APIRouter(prefix="/api/menus", tags=["菜单管理"])


@router.get("", response_model=List[MenuResponse])
async def get_menus(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取所有菜单"""
    service = MenuService(db)
    return service.get_all(skip, limit)


@router.get("/tree")
async def get_menu_tree(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取菜单树（用于前端侧边栏）"""
    service = MenuService(db)
    return service.get_tree()


@router.get("/{menu_id}", response_model=MenuResponse)
async def get_menu(
    menu_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """根据ID获取菜单"""
    service = MenuService(db)
    menu = service.get_by_id(menu_id)
    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="菜单不存在")
    return menu


@router.post("", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
async def create_menu(
    data: MenuCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """创建菜单"""
    service = MenuService(db)
    return service.create(data)


@router.put("/{menu_id}", response_model=MenuResponse)
async def update_menu(
    menu_id: int,
    data: MenuUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """更新菜单"""
    service = MenuService(db)
    menu = service.update(menu_id, data)
    if not menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="菜单不存在")
    return menu


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu(
    menu_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """删除菜单"""
    service = MenuService(db)
    success = service.delete(menu_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="菜单不存在")
    return None


@router.get("/template/{menu_id}")
async def get_menu_with_template(
    menu_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取菜单及其关联的报表模板"""
    service = MenuService(db)
    result = service.get_menu_with_template(menu_id, current_user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="菜单不存在")
    return result
