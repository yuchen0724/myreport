from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    database = Column(String(100), nullable=False)
    username = Column(String(100), nullable=False)
    password_encrypted = Column(String(255), nullable=False)
    use_proxy = Column(Boolean, default=False, comment="是否使用代理")
    proxy_server_id = Column(Integer, ForeignKey("proxy_servers.id"), nullable=True, comment="关联的代理服务器")
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by])
    proxy_server = relationship("ProxyServer", back_populates="data_sources")
