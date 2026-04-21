# backend/app/models/template_version.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class TemplateVersion(Base):
    """模板版本模型"""
    __tablename__ = "template_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    config = Column(Text, nullable=False)  # JSON 配置
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    template = relationship("Template", back_populates="versions")

    # 唯一约束
    __table_args__ = (
        {'comment': '模板版本表'},
    )
