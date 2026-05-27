"""RCA 根因分析数据模型"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, JSON, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class RcaMetricConfig(Base):
    """RCA 指标监控配置"""
    __tablename__ = "rca_metric_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="指标名称，如 total_sales")
    label = Column(String(200), nullable=False, comment="展示名，如 实销金额")
    metric_field = Column(String(200), nullable=False, comment="Doris 表字段名")
    source_table = Column(String(300), nullable=False, comment="Doris 表全名")
    threshold_type = Column(String(50), nullable=False, default="percent_change",
                            comment="阈值类型: percent_change / absolute / zscore")
    threshold_value = Column(Float, nullable=False, default=10.0, comment="阈值")
    compare_type = Column(String(20), nullable=False, default="mom",
                          comment="对比类型: yoy / mom / wow")
    drill_dimensions = Column(JSON, nullable=False,
                              comment='下钻维度列表')
    group_id = Column(Integer, nullable=False, comment="集团 ID")
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RcaAnalysisTask(Base):
    """RCA 分析任务"""
    __tablename__ = "rca_analysis_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, index=True, comment="UUID")
    metric_config_id = Column(Integer, ForeignKey("rca_metric_configs.id"), nullable=False)
    analysis_date = Column(Date, nullable=False)
    period_days = Column(Integer, nullable=False, default=7)
    status = Column(String(20), nullable=False, default="pending",
                    comment="pending / running / completed / failed")
    anomaly_count = Column(Integer, nullable=True)
    summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class RcaAnomaly(Base):
    """RCA 异常发现"""
    __tablename__ = "rca_anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False)
    dimension_path = Column(JSON, nullable=False)
    current_value = Column(Float, nullable=True)
    baseline_value = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)
    severity = Column(String(20), nullable=False, default="warning")
    contribution_pct = Column(Float, nullable=True)
    root_cause_hint = Column(Text, nullable=True)
    drill_details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
