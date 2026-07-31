# backend/app/models/favorite.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Favorite(Base):
    """收藏夹模型"""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False, default="默认")  # 分类: 默认/工作/个人
    note = Column(Text, nullable=True)  # 备注
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user = relationship("User")
    template = relationship("Template")
