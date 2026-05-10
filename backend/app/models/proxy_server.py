from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ProxyServer(Base):
    """代理服务器配置"""
    __tablename__ = "proxy_servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="代理名称")
    proxy_type = Column(String(20), nullable=False, default="http", comment="代理类型: http, https, socks5")
    host = Column(String(255), nullable=False, comment="代理主机")
    port = Column(Integer, nullable=False, comment="代理端口")
    username = Column(String(100), nullable=True, comment="代理用户名（可选）")
    password_encrypted = Column(String(255), nullable=True, comment="代理密码（加密存储，可选）")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by])
    
    # 关联使用该代理的数据源
    data_sources = relationship("DataSource", back_populates="proxy_server")