from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload
from typing import List
from app.models.dashboard_widget import DashboardWidgetConfig
from app.models.query_history import QueryHistory
from app.models.template import Template
from app.models.data_source import DataSource
from app.models.export_task import ExportTask

DEFAULT_WIDGETS = [
    {"widget_type": "data_source_count", "title": "数据源", "position": 0, "visible": True},
    {"widget_type": "query_count",       "title": "查询次数", "position": 1, "visible": True},
    {"widget_type": "export_count",      "title": "导出次数", "position": 2, "visible": True},
    {"widget_type": "template_count",    "title": "模板数量", "position": 3, "visible": True},
    {"widget_type": "recent_queries",    "title": "最近查询", "position": 4, "visible": True},
    {"widget_type": "recent_templates",  "title": "最近模板", "position": 5, "visible": True},
]


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_widgets(self, user_id: int) -> List[DashboardWidgetConfig]:
        configs = (
            self.db.query(DashboardWidgetConfig)
            .filter(DashboardWidgetConfig.user_id == user_id)
            .order_by(DashboardWidgetConfig.position)
            .all()
        )
        if configs:
            return configs
        return self._default_configs(user_id)

    def _default_configs(self, user_id: int) -> List[DashboardWidgetConfig]:
        return [
            DashboardWidgetConfig(user_id=user_id, **widget)
            for widget in DEFAULT_WIDGETS
        ]

    def save_widgets(self, user_id: int, widgets_data: List[dict]) -> List[DashboardWidgetConfig]:
        self.db.query(DashboardWidgetConfig).filter(
            DashboardWidgetConfig.user_id == user_id
        ).delete()

        new_configs = []
        for i, w in enumerate(widgets_data):
            config = DashboardWidgetConfig(
                user_id=user_id,
                widget_type=w["widget_type"],
                title=w["title"],
                position=i,
                visible=w.get("visible", True),
            )
            self.db.add(config)
            new_configs.append(config)

        self.db.commit()
        return new_configs

    def get_dashboard_data(self, user_id: int) -> dict:
        data_source_count = self.db.query(func.count(DataSource.id)).scalar() or 0
        query_count = self.db.query(func.count(QueryHistory.id)).scalar() or 0
        export_count = self.db.query(func.count(ExportTask.id)).scalar() or 0
        template_count = self.db.query(func.count(Template.id)).scalar() or 0

        recent_queries_rows = (
            self.db.query(QueryHistory, DataSource.name.label("data_source_name"))
            .outerjoin(DataSource, QueryHistory.data_source_id == DataSource.id)
            .filter(QueryHistory.user_id == user_id)
            .order_by(desc(QueryHistory.created_at))
            .limit(5)
            .all()
        )

        recent_templates = (
            self.db.query(Template)
            .order_by(desc(Template.created_at))
            .limit(5)
            .all()
        )

        return {
            "data_source_count": data_source_count,
            "query_count": query_count,
            "export_count": export_count,
            "template_count": template_count,
            "recent_queries": [
                {
                    "id": qh.id,
                    "query_text": qh.query_text[:80] + "..." if len(qh.query_text) > 80 else qh.query_text,
                    "data_source_name": data_source_name,
                    "created_at": str(qh.created_at) if qh.created_at else None,
                }
                for qh, data_source_name in recent_queries_rows
            ],
            "recent_templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "version": t.version,
                    "created_at": str(t.created_at) if t.created_at else None,
                }
                for t in recent_templates
            ],
        }
