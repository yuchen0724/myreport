# backend/app/models/template.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Template(Base):
    """模板模型"""
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    config = Column(Text, nullable=False)  # JSON 配置
    version = Column(Integer, default=1)
    is_public = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    versions = relationship("TemplateVersion", back_populates="template", cascade="all, delete-orphan")
    shares = relationship("TemplateShare", back_populates="template", cascade="all, delete-orphan")
