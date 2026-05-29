from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class DashboardLayout(Base):
    __tablename__ = "dashboard_layouts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DashboardWidgetConfig(Base):
    __tablename__ = "dashboard_widget_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    layout_id = Column(Integer, ForeignKey("dashboard_layouts.id", ondelete="CASCADE"), nullable=True, index=True)
    widget_type = Column(String(50), nullable=False)
    widget_subtype = Column(String(50), nullable=True)
    title = Column(String(100), nullable=False)
    grid_x = Column(Integer, default=0)
    grid_y = Column(Integer, default=0)
    grid_w = Column(Integer, default=4)
    grid_h = Column(Integer, default=2)
    position = Column(Integer, nullable=False, default=0)
    visible = Column(Boolean, default=True)
    extra_config = Column(JSON, default={})
    drilldown_config = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
