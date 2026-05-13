from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, JSON
from app.core.database import Base
from datetime import datetime


class PredictionResult(Base):
    """销售预测结果表"""
    __tablename__ = "prediction_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, nullable=False, index=True, comment="模型ID")
    data_source_id = Column(Integer, nullable=False, comment="数据源ID")
    store_code = Column(String(32), nullable=False, comment="门店编码")
    matnr = Column(String(32), nullable=False, comment="商品编码")
    forecast_date = Column(Date, nullable=False, comment="预测日期")
    predicted_value = Column(Float, nullable=False, comment="预测值（元）")
    lower_bound = Column(Float, nullable=True, comment="预测下限")
    upper_bound = Column(Float, nullable=True, comment="预测上限")
    created_at = Column(DateTime, default=datetime.utcnow)


class PredictionModel(Base):
    """训练好的模型元数据"""
    __tablename__ = "prediction_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source_id = Column(Integer, nullable=False, comment="关联数据源")
    model_type = Column(String(32), default="lightgbm", comment="模型类型")
    feature_count = Column(Integer, nullable=True, comment="特征数")
    train_start_date = Column(Date, nullable=True, comment="训练数据起始日期")
    train_end_date = Column(Date, nullable=True, comment="训练数据截止日期")
    train_row_count = Column(Integer, nullable=True, comment="训练样本数")
    model_metrics = Column(JSON, nullable=True, comment="模型指标(JSON)")
    model_path = Column(String(255), nullable=True, comment="模型文件路径")
    status = Column(String(16), default="training", comment="状态: training/ready/failed")
    error_message = Column(Text, nullable=True, comment="训练失败原因")
    created_at = Column(DateTime, default=datetime.utcnow)
    trained_at = Column(DateTime, nullable=True, comment="训练完成时间")
