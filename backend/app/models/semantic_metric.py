"""Semantic metric metadata models."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SemanticMetric(Base):
    """Metric definition used by semantic-layer query generation."""

    __tablename__ = "semantic_metrics"
    __table_args__ = (
        UniqueConstraint("metric_key", name="uq_semantic_metrics_metric_key"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_key = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    base_sql = Column(Text, nullable=False)
    metric_expression = Column(String(300), nullable=False, default="COUNT(*)")
    dimensions = Column(JSON, nullable=False, default=list)
    time_column = Column(String(200), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    versions = relationship(
        "SemanticMetricVersion",
        back_populates="metric",
        cascade="all, delete-orphan",
        order_by="SemanticMetricVersion.version_number.desc()",
    )
    permissions = relationship(
        "SemanticMetricPermission",
        back_populates="metric",
        cascade="all, delete-orphan",
    )


class SemanticMetricVersion(Base):
    """Immutable snapshot of a semantic metric definition."""

    __tablename__ = "semantic_metric_versions"
    __table_args__ = (
        UniqueConstraint("metric_id", "version_number", name="uq_semantic_metric_versions_metric_version"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_id = Column(Integer, ForeignKey("semantic_metrics.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    change_summary = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    metric = relationship("SemanticMetric", back_populates="versions")


class SemanticMetricPermission(Base):
    """User-level sharing permission for a semantic metric."""

    __tablename__ = "semantic_metric_permissions"
    __table_args__ = (
        UniqueConstraint("metric_id", "user_id", name="uq_semantic_metric_permissions_metric_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_id = Column(Integer, ForeignKey("semantic_metrics.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_level = Column(String(20), nullable=False, default="viewer")
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    metric = relationship("SemanticMetric", back_populates="permissions")
