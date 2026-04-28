from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class DashboardWidgetConfig(Base):
    __tablename__ = "dashboard_widget_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    widget_type = Column(String(50), nullable=False)
    title = Column(String(100), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    visible = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "widget_type", name="uq_user_widget_type"),
    )
