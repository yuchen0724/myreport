"""
菜单模型
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Menu(Base):
    """菜单模型"""
    __tablename__ = "menus"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="菜单名称")
    path = Column(String(200), nullable=True, comment="菜单路由路径")
    icon = Column(String(50), nullable=True, comment="菜单图标")
    sort_order = Column(Integer, default=0, comment="排序顺序")
    parent_id = Column(Integer, ForeignKey("menus.id"), nullable=True, comment="父菜单ID")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    is_visible = Column(Boolean, default=True, comment="是否可见")
    remark = Column(String(500), nullable=True, comment="备注")
    
    # 关联的报表模板ID
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True, comment="关联的报表模板")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    parent = relationship("Menu", remote_side=[id], backref="children")
    # 注意：不能定义 template relationship，因为 Template 模型加载时序不可控
    # 需要获取关联模板时，请通过 TemplateRepository 查询
    # template_id 字段仅用于存储外键
    
    def __repr__(self):
        return f"<Menu {self.name}>"