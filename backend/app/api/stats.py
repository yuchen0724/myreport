# backend/app/api/stats.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.core.database import get_db
from app.models.data_source import DataSource
from app.models.query_history import QueryHistory
from app.models.export_task import ExportTask
from app.models.template import Template
from app.utils.metrics import metrics_collector

router = APIRouter(prefix="/api/stats", tags=["统计"])


@router.get("/dashboard")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """获取仪表盘统计数据"""
    # 数据源数量
    data_source_count = db.query(func.count(DataSource.id)).scalar() or 0

    # 查询次数
    query_count = db.query(func.count(QueryHistory.id)).scalar() or 0

    # 导出次数
    export_count = db.query(func.count(ExportTask.id)).scalar() or 0

    # 模板数量
    template_count = db.query(func.count(Template.id)).scalar() or 0

    return {
        "data_source_count": data_source_count,
        "query_count": query_count,
        "export_count": export_count,
        "template_count": template_count
    }


@router.get("/metrics")
async def get_metrics():
    """获取性能指标"""
    return metrics_collector.get_summary()


@router.get("/metrics/recent")
async def get_recent_metrics(limit: int = 50):
    """获取最近的请求指标"""
    return {"metrics": metrics_collector.get_recent_metrics(limit)}


@router.post("/metrics/reset")
async def reset_metrics():
    """重置性能指标"""
    metrics_collector.reset()
    return {"status": "reset"}


@router.get("/slow-queries")
async def get_slow_queries(limit: int = 50, threshold: Optional[int] = None):
    """获取慢查询列表
    - limit: 返回条数（默认50）
    - threshold: 查询阈值（毫秒），不传则使用默认阈值
    """
    if threshold is not None:
        metrics_collector.slow_query_threshold_ms = threshold
    return {
        "threshold_ms": metrics_collector.slow_query_threshold_ms,
        "slow_queries": metrics_collector.get_slow_queries(limit),
    }
