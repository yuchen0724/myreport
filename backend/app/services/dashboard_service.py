from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload
from typing import List, Optional, Dict, Any
from app.models.dashboard_widget import DashboardLayout, DashboardWidgetConfig
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

    # ==================== 布局 CRUD ====================

    def get_layouts(self, user_id: int) -> List[DashboardLayout]:
        return (
            self.db.query(DashboardLayout)
            .filter(DashboardLayout.user_id == user_id)
            .order_by(DashboardLayout.updated_at.desc().nullslast(), DashboardLayout.id.desc())
            .all()
        )

    def get_layout(self, layout_id: int, user_id: int) -> Optional[DashboardLayout]:
        return (
            self.db.query(DashboardLayout)
            .filter(DashboardLayout.id == layout_id, DashboardLayout.user_id == user_id)
            .first()
        )

    def create_layout(self, user_id: int, name: str, is_default: bool = False) -> DashboardLayout:
        layout = DashboardLayout(user_id=user_id, name=name, is_default=is_default)
        self.db.add(layout)
        self.db.commit()
        self.db.refresh(layout)
        return layout

    def update_layout(self, layout_id: int, user_id: int, data: Dict[str, Any]) -> Optional[DashboardLayout]:
        layout = self.get_layout(layout_id, user_id)
        if not layout:
            return None
        if "name" in data:
            layout.name = data["name"]
        if "is_default" in data:
            layout.is_default = data["is_default"]
        self.db.commit()
        self.db.refresh(layout)
        return layout

    def delete_layout(self, layout_id: int, user_id: int) -> bool:
        layout = self.get_layout(layout_id, user_id)
        if not layout:
            return False
        self.db.delete(layout)
        self.db.commit()
        return True

    # ==================== Widget CRUD ====================

    def get_widgets(self, layout_id: int) -> List[DashboardWidgetConfig]:
        return (
            self.db.query(DashboardWidgetConfig)
            .filter(DashboardWidgetConfig.layout_id == layout_id)
            .order_by(DashboardWidgetConfig.position)
            .all()
        )

    def create_widget(self, layout_id: int, user_id: int, data: Dict[str, Any]) -> DashboardWidgetConfig:
        config = DashboardWidgetConfig(
            user_id=user_id,
            layout_id=layout_id,
            widget_type=data["widget_type"],
            widget_subtype=data.get("widget_subtype"),
            title=data.get("title", ""),
            grid_x=data.get("grid_x", 0),
            grid_y=data.get("grid_y", 0),
            grid_w=data.get("grid_w", 4),
            grid_h=data.get("grid_h", 2),
            position=data.get("position", 0),
            visible=True,
            extra_config=data.get("extra_config", {}),
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def update_widget(self, widget_id: int, user_id: int, data: Dict[str, Any]) -> Optional[DashboardWidgetConfig]:
        widget = (
            self.db.query(DashboardWidgetConfig)
            .filter(DashboardWidgetConfig.id == widget_id, DashboardWidgetConfig.user_id == user_id)
            .first()
        )
        if not widget:
            return None
        for field in ("title", "grid_x", "grid_y", "grid_w", "grid_h", "visible", "extra_config", "widget_subtype"):
            if field in data:
                setattr(widget, field, data[field])
        self.db.commit()
        self.db.refresh(widget)
        return widget

    def delete_widget(self, widget_id: int, user_id: int) -> bool:
        widget = (
            self.db.query(DashboardWidgetConfig)
            .filter(DashboardWidgetConfig.id == widget_id, DashboardWidgetConfig.user_id == user_id)
            .first()
        )
        if not widget:
            return False
        self.db.delete(widget)
        self.db.commit()
        return True

    # ==================== 批量更新布局内的 Widgets ====================

    def save_layout_widgets(self, layout_id: int, user_id: int, widgets_data: List[Dict]) -> List[DashboardWidgetConfig]:
        """清空布局内所有 widget，批量重建（用于编辑模式整体保存）"""
        self.db.query(DashboardWidgetConfig).filter(
            DashboardWidgetConfig.layout_id == layout_id
        ).delete()

        new_configs = []
        for i, w in enumerate(widgets_data):
            config = DashboardWidgetConfig(
                user_id=user_id,
                layout_id=layout_id,
                widget_type=w["widget_type"],
                widget_subtype=w.get("widget_subtype"),
                title=w.get("title", ""),
                grid_x=w.get("grid_x", 0),
                grid_y=w.get("grid_y", 0),
                grid_w=w.get("grid_w", 4),
                grid_h=w.get("grid_h", 2),
                position=i,
                visible=w.get("visible", True),
                extra_config=w.get("extra_config", {}),
            )
            self.db.add(config)
            new_configs.append(config)

        self.db.commit()
        return new_configs

    # ==================== 旧版兼容（无布局的 widgets） ====================

    def get_legacy_widgets(self, user_id: int) -> List[DashboardWidgetConfig]:
        configs = (
            self.db.query(DashboardWidgetConfig)
            .filter(DashboardWidgetConfig.user_id == user_id, DashboardWidgetConfig.layout_id.is_(None))
            .order_by(DashboardWidgetConfig.position)
            .all()
        )
        if configs:
            return configs
        return self._default_configs(user_id)

    def _default_configs(self, user_id: int) -> List[DashboardWidgetConfig]:
        configs = []
        for w in DEFAULT_WIDGETS:
            config = DashboardWidgetConfig(user_id=user_id, **w)
            self.db.add(config)
            configs.append(config)
        self.db.commit()
        return configs

    def save_legacy_widgets(self, user_id: int, widgets_data: List[dict]) -> List[DashboardWidgetConfig]:
        self.db.query(DashboardWidgetConfig).filter(
            DashboardWidgetConfig.user_id == user_id, DashboardWidgetConfig.layout_id.is_(None)
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

    # ==================== 仪表盘统计数据 ====================

    def get_dashboard_data(self, user_id: int) -> dict:
        from sqlalchemy import cast, Date

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

        # — 图表数据 —
        # 1. 近 30 天查询趋势（按日）
        daily_query = (
            self.db.query(
                cast(QueryHistory.created_at, Date).label("day"),
                func.count(QueryHistory.id).label("cnt"),
            )
            .filter(QueryHistory.user_id == user_id)
            .group_by(cast(QueryHistory.created_at, Date))
            .order_by(cast(QueryHistory.created_at, Date))
            .all()
        )
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone.utc).date()
        day_map = {r.day: r.cnt for r in daily_query}
        query_trend = []
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            query_trend.append({"x": d.strftime("%m-%d"), "y": day_map.get(d, 0)})

        # 2. 数据源查询分布
        ds_query = (
            self.db.query(
                DataSource.name.label("ds_name"),
                func.count(QueryHistory.id).label("cnt"),
            )
            .join(QueryHistory, QueryHistory.data_source_id == DataSource.id)
            .filter(QueryHistory.user_id == user_id)
            .group_by(DataSource.name)
            .order_by(func.count(QueryHistory.id).desc())
            .all()
        )
        data_source_trend = [{"x": r.ds_name, "y": r.cnt} for r in ds_query]

        # 3. 近 7 天导出趋势
        daily_export = (
            self.db.query(
                cast(ExportTask.created_at, Date).label("day"),
                func.count(ExportTask.id).label("cnt"),
            )
            .group_by(cast(ExportTask.created_at, Date))
            .order_by(cast(ExportTask.created_at, Date))
            .all()
        )
        export_day_map = {r.day: r.cnt for r in daily_export}
        export_trend = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            export_trend.append({"x": d.strftime("%m-%d"), "y": export_day_map.get(d, 0)})

        # 4. 模板类型分布（按描述中的关键词归类）
        template_type_map = {"销售预测": 0, "数据查询": 0, "基础统计": 0, "其他": 0}
        for t in recent_templates:
            t_desc = (t.description or "").lower()
            if "预测" in t_desc:
                template_type_map["销售预测"] += 1
            elif "查询" in t_desc or "sql" in t_desc:
                template_type_map["数据查询"] += 1
            elif "统计" in t_desc or "汇总" in t_desc:
                template_type_map["基础统计"] += 1
            else:
                template_type_map["其他"] += 1
        template_pie = [{"x": k, "y": v} for k, v in template_type_map.items() if v > 0]

        # 5. 最近 5 次查询耗时
        recent_durations = (
            self.db.query(QueryHistory)
            .filter(QueryHistory.user_id == user_id, QueryHistory.execution_time_ms.isnot(None))
            .order_by(desc(QueryHistory.created_at))
            .limit(5)
            .all()
        )
        # reverse 让时间正序排列
        recent_durations.reverse()
        duration_scatter = []
        for i, qh in enumerate(recent_durations):
            duration_scatter.append({"x": qh.query_text[:30] if qh.query_text else f"查询{i+1}", "y": qh.execution_time_ms})

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
            # 图表数据
            "chart_query_trend": query_trend,
            "chart_data_source_pie": data_source_trend,
            "chart_export_trend": export_trend,
            "chart_template_pie": template_pie,
            "chart_duration_scatter": duration_scatter,
        }
