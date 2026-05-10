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


class ProxyServerService:
    def __init__(self, db: Session):
        self.db = db
        self.ps_repo = ProxyServerRepository(db)

    def create_proxy_server(self, ps_data: ProxyServerCreate, user_id: int) -> ProxyServerResponse:
        """创建代理服务器"""
        ps = self.ps_repo.create(ps_data.model_dump(), user_id)
        return ProxyServerResponse.model_validate(ps)

    def get_proxy_server(self, ps_id: int) -> Optional[ProxyServerResponse]:
        """获取代理服务器"""
        ps = self.ps_repo.get_by_id(ps_id)
        if not ps:
            return None
        return ProxyServerResponse.model_validate(ps)

    def list_proxy_servers(self, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[ProxyServerResponse]:
        """列出代理服务器"""
        if user_id:
            ps_list = self.ps_repo.get_by_user(user_id, skip, limit)
        else:
            ps_list = self.ps_repo.get_all(skip, limit)
        return [ProxyServerResponse.model_validate(ps) for ps in ps_list]

    def get_active_proxy_servers(self) -> List[ProxyServerResponse]:
        """获取所有启用的代理服务器"""
        ps_list = self.ps_repo.get_active()
        return [ProxyServerResponse.model_validate(ps) for ps in ps_list]

    def update_proxy_server(self, ps_id: int, ps_data: ProxyServerUpdate) -> Optional[ProxyServerResponse]:
        """更新代理服务器"""
        db_ps = self.ps_repo.get_by_id(ps_id)
        if not db_ps:
            return None
        
        # 处理密码更新
        update_data = ps_data.model_dump(exclude_unset=True)
        if 'password' in update_data:
            if update_data['password'] == '' or update_data['password'] is None:
                del update_data['password']
        
        updated_ps = self.ps_repo.update(db_ps, update_data)
        return ProxyServerResponse.model_validate(updated_ps)

    def delete_proxy_server(self, ps_id: int) -> bool:
        """删除代理服务器"""
        db_ps = self.ps_repo.get_by_id(ps_id)
        if not db_ps:
            return False
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