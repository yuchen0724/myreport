import json
from app.core.database import SessionLocal
from app.models.dashboard_widget import DashboardLayout, DashboardWidgetConfig

db = SessionLocal()
db.query(DashboardWidgetConfig).delete()
db.query(DashboardLayout).delete()
db.commit()

layout = DashboardLayout(user_id=1, name="默认看板", is_default=True)
db.add(layout)
db.flush()

widgets = [
    # === 第一行：4 个统计卡 ===
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="stat", widget_subtype="data_source_count", title="数据源",
        grid_x=0, grid_y=0, grid_w=3, grid_h=1, position=0, visible=True,
        extra_config={}),
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="stat", widget_subtype="query_count", title="查询次数",
        grid_x=3, grid_y=0, grid_w=3, grid_h=1, position=1, visible=True,
        extra_config={}),
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="stat", widget_subtype="export_count", title="导出次数",
        grid_x=6, grid_y=0, grid_w=3, grid_h=1, position=2, visible=True,
        extra_config={}),
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="stat", widget_subtype="template_count", title="模板数量",
        grid_x=9, grid_y=0, grid_w=3, grid_h=1, position=3, visible=True,
        extra_config={}),

    # === 第二行左：折线图 ===
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="chart", widget_subtype="line", title="近30天查询趋势",
        grid_x=0, grid_y=1, grid_w=6, grid_h=4, position=4, visible=True,
        extra_config={"x_axis": "日期", "y_axis": "查询次数", "x_axis_label": "日期", "y_axis_label": "查询次数"}),

    # === 第二行右：饼图 — 数据源查询分布 ===
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="chart", widget_subtype="pie", title="数据源查询分布",
        grid_x=6, grid_y=1, grid_w=6, grid_h=4, position=5, visible=True,
        extra_config={"x_axis": "数据源", "y_axis": "查询次数"}),

    # === 第三行左：柱状图 ===
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="chart", widget_subtype="bar", title="近7天导出趋势",
        grid_x=0, grid_y=5, grid_w=4, grid_h=3, position=6, visible=True,
        extra_config={"x_axis": "日期", "y_axis": "导出次数"}),

    # === 第三行中：饼图 — 模板类型分布 ===
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="chart", widget_subtype="pie", title="模板类型分布",
        grid_x=4, grid_y=5, grid_w=4, grid_h=3, position=7, visible=True,
        extra_config={"x_axis": "类型", "y_axis": "数量"}),

    # === 第三行右：散点图 ===
    DashboardWidgetConfig(user_id=1, layout_id=layout.id,
        widget_type="chart", widget_subtype="scatter", title="最近查询耗时",
        grid_x=8, grid_y=5, grid_w=4, grid_h=3, position=8, visible=True,
        extra_config={"x_axis": "查询", "y_axis": "耗时(ms)"}),
]
for w in widgets:
    db.add(w)
db.commit()

print(f"Layout id={layout.id}, widgets={len(widgets)}")
cnt = db.query(DashboardWidgetConfig).filter(DashboardWidgetConfig.layout_id == layout.id).count()
print(f"DB verified: {cnt} widgets")
db.close()
