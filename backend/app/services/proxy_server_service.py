from typing import List, Optional
from sqlalchemy.orm import Session
from app.repositories.proxy_server_repository import ProxyServerRepository
from app.schemas.proxy_server import (
    ProxyServerCreate,
    ProxyServerUpdate,
    ProxyServerResponse,
    ProxyServerTestRequest,
    ProxyServerTestResponse,
)
from app.exceptions import NotFoundError, AuthorizationError


class ProxyServerService:
    def __init__(self, db: Session):
        self.db = db
        self.ps_repo = ProxyServerRepository(db)

    def _require_proxy_server(self, ps_id: int):
        """获取代理服务器，不存在则抛出 NotFoundError"""
        ps = self.ps_repo.get_by_id(ps_id)
        if not ps:
            raise NotFoundError(f"代理服务器不存在 (id={ps_id})")
        return ps

    def _check_owner(self, ps, user_id: int) -> None:
        """校验当前用户是否为代理服务器所有者，不是则抛出 AuthorizationError"""
        if ps.created_by and ps.created_by != user_id:
            raise AuthorizationError("您没有权限操作此代理服务器")

    def create_proxy_server(self, ps_data: ProxyServerCreate, user_id: int) -> ProxyServerResponse:
        """创建代理服务器"""
        ps = self.ps_repo.create(ps_data.model_dump(), user_id)
        return ProxyServerResponse.model_validate(ps)

    def get_proxy_server(self, ps_id: int, user_id: int) -> Optional[ProxyServerResponse]:
        """获取代理服务器"""
        ps = self.ps_repo.get_by_id(ps_id)
        if not ps or ps.created_by != user_id:
            return None
        return ProxyServerResponse.model_validate(ps)

    def list_proxy_servers(self, user_id: int, skip: int = 0, limit: int = 100) -> List[ProxyServerResponse]:
        """列出代理服务器"""
        ps_list = self.ps_repo.get_by_user(user_id, skip, limit)
        return [ProxyServerResponse.model_validate(ps) for ps in ps_list]

    def get_active_proxy_servers(self, user_id: int) -> List[ProxyServerResponse]:
        """获取所有启用的代理服务器"""
        ps_list = [ps for ps in self.ps_repo.get_active() if ps.created_by == user_id]
        return [ProxyServerResponse.model_validate(ps) for ps in ps_list]

    def update_proxy_server(self, ps_id: int, ps_data: ProxyServerUpdate, user_id: int) -> Optional[ProxyServerResponse]:
        """更新代理服务器"""
        db_ps = self._require_proxy_server(ps_id)
        self._check_owner(db_ps, user_id)
        
        # 处理密码更新
        update_data = ps_data.model_dump(exclude_unset=True)
        if 'password' in update_data:
            if update_data['password'] == '' or update_data['password'] is None:
                del update_data['password']
        
        updated_ps = self.ps_repo.update(db_ps, update_data)
        return ProxyServerResponse.model_validate(updated_ps)

    def delete_proxy_server(self, ps_id: int, user_id: int) -> bool:
        """删除代理服务器"""
        db_ps = self._require_proxy_server(ps_id)
        self._check_owner(db_ps, user_id)
        return self.ps_repo.delete(db_ps)

    def test_connection(self, request: ProxyServerTestRequest) -> ProxyServerTestResponse:
        """测试代理服务器连接"""
        import socket
        try:
            # 测试 TCP 连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((request.host, request.port))
            sock.close()
            
            if result == 0:
                return ProxyServerTestResponse(success=True, message="连接成功")
            else:
                return ProxyServerTestResponse(success=False, message=f"无法连接到代理服务器 {request.host}:{request.port}")
        except Exception as e:
            return ProxyServerTestResponse(success=False, message=f"连接失败: {str(e)}")
