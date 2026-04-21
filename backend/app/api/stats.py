# backend/app/api/stats.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.data_source import DataSource
from app.models.query_history import QueryHistory
from app.models.export_task import ExportTask
from app.models.template import Template

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
