# backend/app/models/template_share.py
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class TemplateShare(Base):
    """模板分享模型"""
    __tablename__ = "template_shares"

    template_id = Column(Integer, ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    shared_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    shared_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    template = relationship("Template", back_populates="shares")
