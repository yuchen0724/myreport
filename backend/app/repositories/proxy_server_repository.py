from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.proxy_server import ProxyServer
from app.core.security import encrypt_password


class ProxyServerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict, user_id: int) -> ProxyServer:
        """创建代理服务器"""
        # 处理密码字段映射
        if 'password' in data and data['password']:
            data['password_encrypted'] = encrypt_password(data['password'])
        # 移除 schema 字段，保留模型字段
        data.pop('password', None)
        
        ds = ProxyServer(**data, created_by=user_id)
        self.db.add(ds)
        self.db.flush()
        self.db.refresh(ds)
        return ds

    def get_by_id(self, ds_id: int) -> Optional[ProxyServer]:
        """根据 ID 获取"""
        return self.db.query(ProxyServer).filter(ProxyServer.id == ds_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ProxyServer]:
        """获取所有代理服务器"""
        return self.db.query(ProxyServer).offset(skip).limit(limit).all()

    def get_active(self) -> List[ProxyServer]:
        """获取所有启用的代理服务���"""
        return self.db.query(ProxyServer).filter(ProxyServer.is_active == True).all()

    def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[ProxyServer]:
        """获取用户创建的代理服务器"""
        return self.db.query(ProxyServer).filter(
            ProxyServer.created_by == user_id
        ).offset(skip).limit(limit).all()

    def update(self, db_obj: ProxyServer, data: dict) -> ProxyServer:
        """更新代理服务器"""
        for key, value in data.items():
            if key == 'password' and value:
                setattr(db_obj, 'password_encrypted', encrypt_password(value))
            elif key != 'password':
                setattr(db_obj, key, value)
        
        self.db.flush()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, db_obj: ProxyServer) -> bool:
        """删除代理服务器"""
        self.db.delete(db_obj)
        self.db.flush()
        return True