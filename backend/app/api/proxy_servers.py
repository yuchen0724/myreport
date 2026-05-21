from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.schemas.proxy_server import (
    ProxyServerCreate,
    ProxyServerUpdate,
    ProxyServerResponse,
    ProxyServerTestRequest,
    ProxyServerTestResponse,
)
from app.services.proxy_server_service import ProxyServerService

router = APIRouter(prefix="/api/proxy-servers", tags=["代理服务器管理"])


@router.post("", response_model=ProxyServerResponse, status_code=status.HTTP_201_CREATED)
async def create_proxy_server(
    ps_data: ProxyServerCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """创建代理服务器"""
    ps_service = ProxyServerService(db)
    return ps_service.create_proxy_server(ps_data, current_user_id)


@router.get("", response_model=List[ProxyServerResponse])
async def list_proxy_servers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取代理服务器列表"""
    ps_service = ProxyServerService(db)
    return ps_service.list_proxy_servers(skip=skip, limit=limit)


@router.get("/active", response_model=List[ProxyServerResponse])
async def get_active_proxy_servers(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取所有启用的代理服务器"""
    ps_service = ProxyServerService(db)
    return ps_service.get_active_proxy_servers()


@router.get("/{ps_id}", response_model=ProxyServerResponse)
async def get_proxy_server(
    ps_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取代理服务器详情"""
    ps_service = ProxyServerService(db)
    ps = ps_service.get_proxy_server(ps_id)
    if not ps:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="代理服务器不存在",
        )
    return ps


@router.put("/{ps_id}", response_model=ProxyServerResponse)
async def update_proxy_server(
    ps_id: int,
    ps_data: ProxyServerUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """更新代理服务器"""
    ps_service = ProxyServerService(db)
    return ps_service.update_proxy_server(ps_id, ps_data, current_user_id)


@router.delete("/{ps_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy_server(
    ps_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """删除代理服务器"""
    ps_service = ProxyServerService(db)
    ps_service.delete_proxy_server(ps_id, current_user_id)


@router.post("/test", response_model=ProxyServerTestResponse)
async def test_proxy_server(
    request: ProxyServerTestRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """测试代理服务器连接"""
    ps_service = ProxyServerService(db)
    return ps_service.test_connection(request)