"""DashboardService 单元测试"""

import pytest
from sqlalchemy import func
from app.services.dashboard_service import DashboardService
from app.models.dashboard_widget import DashboardLayout, DashboardWidgetConfig
from app.models.data_source import DataSource
from app.models.query_history import QueryHistory
from app.models.template import Template
from app.models.export_task import ExportTask
from app.models.user import User
from app.core.security import get_password_hash


# ==================== Layout CRUD ====================

class TestDashboardLayout:
    """布局 CRUD 测试"""

    def test_create_layout(self, db_session, test_user):
        """创建布局"""
        svc = DashboardService(db_session)
        layout = svc.create_layout(user_id=test_user.id, name="默认布局", is_default=True)
        assert layout.id is not None
        assert layout.name == "默认布局"
        assert layout.is_default is True
        assert layout.user_id == test_user.id

    def test_get_layouts(self, db_session, test_user):
        """获取用户布局列表"""
        svc = DashboardService(db_session)
        svc.create_layout(test_user.id, "布局A")
        svc.create_layout(test_user.id, "布局B")
        layouts = svc.get_layouts(test_user.id)
        assert len(layouts) == 2
        names = [l.name for l in layouts]
        assert "布局A" in names
        assert "布局B" in names

    def test_get_layouts_empty(self, db_session, test_user):
        """无布局时返回空列表"""
        svc = DashboardService(db_session)
        assert svc.get_layouts(test_user.id) == []

    def test_get_layout(self, db_session, test_user):
        """按 ID 获取布局"""
        svc = DashboardService(db_session)
        layout = svc.create_layout(test_user.id, "我的布局")
        got = svc.get_layout(layout.id, test_user.id)
        assert got is not None
        assert got.id == layout.id
        assert got.name == "我的布局"

    def test_get_layout_not_found(self, db_session, test_user):
        """获取不存在的布局返回 None"""
        svc = DashboardService(db_session)
        assert svc.get_layout(999, test_user.id) is None

    def test_get_layout_wrong_user(self, db_session, test_user):
        """不能获取其他用户的布局"""
        svc = DashboardService(db_session)
        layout = svc.create_layout(test_user.id, "私有")
        another = User(username="other", email="other@t.com", password_hash="x", is_active=True)
        db_session.add(another)
        db_session.commit()
        assert svc.get_layout(layout.id, another.id) is None

    def test_update_layout_name(self, db_session, test_user):
        """更新布局名称"""
        svc = DashboardService(db_session)
        layout = svc.create_layout(test_user.id, "旧名称")
        updated = svc.update_layout(layout.id, test_user.id, {"name": "新名称"})
        assert updated is not None
        assert updated.name == "新名称"

    def test_update_layout_default(self, db_session, test_user):
        """更新布局默认状态"""
        svc = DashboardService(db_session)
        layout = svc.create_layout(test_user.id, "L")
        updated = svc.update_layout(layout.id, test_user.id, {"is_default": True})
        assert updated is not None
        assert updated.is_default is True

    def test_update_layout_not_found(self, db_session, test_user):
        """更新不存在的布局返回 None"""
        svc = DashboardService(db_session)
        assert svc.update_layout(999, test_user.id, {"name": "x"}) is None

    def test_delete_layout(self, db_session, test_user):
        """删除布局"""
        svc = DashboardService(db_session)
        layout = svc.create_layout(test_user.id, "待删除")
        assert svc.delete_layout(layout.id, test_user.id) is True
        assert svc.get_layout(layout.id, test_user.id) is None

    def test_delete_layout_not_found(self, db_session, test_user):
        """删除不存在的布局返回 False"""
        svc = DashboardService(db_session)
        assert svc.delete_layout(999, test_user.id) is False

    def test_delete_layout_wrong_user(self, db_session, test_user):
        """不能删除其他用户的布局"""
        svc = DashboardService(db_session)
        layout = svc.create_layout(test_user.id, "L")
        another = User(username="other2", email="other2@t.com", password_hash="x", is_active=True)
        db_session.add(another)
        db_session.commit()
        assert svc.delete_layout(layout.id, another.id) is False
# ==================== Widget CRUD ====================

class TestDashboardWidget:
    """Widget CRUD 测试"""

    def _create_layout(self, svc, user_id, name="默认布局"):
        return svc.create_layout(user_id=user_id, name=name)

    def test_create_widget(self, db_session, test_user):
        """创建 widget"""
        svc = DashboardService(db_session)
        layout = self._create_layout(svc, test_user.id)
        widget = svc.create_widget(
            layout_id=layout.id,
            user_id=test_user.id,
            data={
                "widget_type": "data_source_count",
                "title": "数据源",
                "position": 0,
                "grid_x": 0,
                "grid_y": 0,
                "grid_w": 4,
                "grid_h": 2,
                "extra_config": {"color": "blue"},
            },
        )
        assert widget.id is not None
        assert widget.widget_type == "data_source_count"
        assert widget.title == "数据源"
        assert widget.grid_w == 4
        assert widget.visible is True
        assert widget.extra_config == {"color": "blue"}

    def test_get_widgets(self, db_session, test_user):
        """获取布局下的所有 widget"""
        svc = DashboardService(db_session)
        layout = self._create_layout(svc, test_user.id)
        svc.create_widget(layout.id, test_user.id, {"widget_type": "a", "title": "A", "position": 0})
        svc.create_widget(layout.id, test_user.id, {"widget_type": "b", "title": "B", "position": 1})
        widgets = svc.get_widgets(layout.id)
        assert len(widgets) == 2

    def test_get_widgets_empty(self, db_session, test_user):
        """无 widget 时返回空列表"""
        svc = DashboardService(db_session)
        layout = self._create_layout(svc, test_user.id)
        assert svc.get_widgets(layout.id) == []

    def test_update_widget(self, db_session, test_user):
        """更新 widget 属性"""
        svc = DashboardService(db_session)
        layout = self._create_layout(svc, test_user.id)
        widget = svc.create_widget(layout.id, test_user.id, {"widget_type": "x", "title": "旧", "position": 0})
        updated = svc.update_widget(widget.id, test_user.id, {"title": "新标题", "grid_w": 6, "visible": False})
        assert updated is not None
        assert updated.title == "新标题"
        assert updated.grid_w == 6
        assert updated.visible is False

    def test_update_widget_not_found(self, db_session, test_user):
        """更新不存在的 widget 返回 None"""
        svc = DashboardService(db_session)
        assert svc.update_widget(999, test_user.id, {"title": "x"}) is None

    def test_update_widget_wrong_user(self, db_session, test_user):
        """不能更新其他用户的 widget"""
        svc = DashboardService(db_session)
        layout = self._create_layout(svc, test_user.id)
        widget = svc.create_widget(layout.id, test_user.id, {"widget_type": "x", "title": "X", "position": 0})
        another = User(username="other3", email="other3@t.com", password_hash="x", is_active=True)
        db_session.add(another)
        db_session.commit()
        assert svc.update_widget(widget.id, another.id, {"title": "y"}) is None

    def test_delete_widget(self, db_session, test_user):
        """删除 widget"""
        svc = DashboardService(db_session)
        layout = self._create_layout(svc, test_user.id)
        widget = svc.create_widget(layout.id, test_user.id, {"widget_type": "x", "title": "待删", "position": 0})
        assert svc.delete_widget(widget.id, test_user.id) is True
        assert svc.get_widgets(layout.id) == []

    def test_delete_widget_not_found(self, db_session, test_user):
        """删除不存在的 widget 返回 False"""
        svc = DashboardService(db_session)
        assert svc.delete_widget(999, test_user.id) is False

    def test_delete_widget_wrong_user(self, db_session, test_user):
        """不能删除其他用户的 widget"""
        svc = DashboardService(db_session)
        layout = self._create_layout(svc, test_user.id)
        widget = svc.create_widget(layout.id, test_user.id, {"widget_type": "x", "title": "X", "position": 0})
        another = User(username="other4", email="other4@t.com", password_hash="x", is_active=True)
        db_session.add(another)
        db_session.commit()
        assert svc.delete_widget(widget.id, another.id) is False

    # ==================== save_layout_widgets ====================

    def test_save_layout_widgets(self, db_session, test_user):
        """批量保存布局 widgets（全量替换）"""
        svc = DashboardService(db_session)
        layout = self._create_layout(svc, test_user.id)
        svc.create_widget(layout.id, test_user.id, {"widget_type": "old", "title": "旧", "position": 0})

        widgets_data = [
            {"widget_type": "a", "title": "AA", "grid_x": 0, "grid_y": 0, "grid_w": 6, "grid_h": 2, "visible": True},
            {"widget_type": "b", "title": "BB", "grid_x": 6, "grid_y": 0, "grid_w": 6, "grid_h": 2, "visible": True},
        ]
        result = svc.save_layout_widgets(layout.id, test_user.id, widgets_data)
        assert len(result) == 2
        assert result[0].widget_type == "a"
        assert result[1].widget_type == "b"
        # 旧 widget 已被清除
        assert len(svc.get_widgets(layout.id)) == 2
# ==================== Legacy Widgets ====================

class TestLegacyWidgets:
    """旧版无布局 widgets 测试"""

    def test_get_legacy_widgets_creates_defaults(self, db_session, test_user):
        """首次获取 legacy widgets 时创建默认 widgets"""
        svc = DashboardService(db_session)
        widgets = svc.get_legacy_widgets(test_user.id)
        assert len(widgets) == 6
        types = [w.widget_type for w in widgets]
        assert "data_source_count" in types
        assert "query_count" in types
        assert "export_count" in types
        assert "template_count" in types
        assert "recent_queries" in types
        assert "recent_templates" in types

    def test_get_legacy_widgets_existing(self, db_session, test_user):
        """已有 legacy widgets 时返回现有列表"""
        svc = DashboardService(db_session)
        # 先创建默认
        first = svc.get_legacy_widgets(test_user.id)
        # 再次获取，应返回相同的 widgets（不重复创建）
        second = svc.get_legacy_widgets(test_user.id)
        assert len(second) == 6
        assert [w.id for w in first] == [w.id for w in second]

    def test_save_legacy_widgets(self, db_session, test_user):
        """保存 legacy widgets（全量替换）"""
        svc = DashboardService(db_session)
        svc.get_legacy_widgets(test_user.id)  # 创建默认

        new_widgets = [
            {"widget_type": "custom_a", "title": "自定义A", "visible": True},
            {"widget_type": "custom_b", "title": "自定义B", "visible": False},
        ]
        result = svc.save_legacy_widgets(test_user.id, new_widgets)
        assert len(result) == 2
        assert result[0].widget_type == "custom_a"
        assert result[1].widget_type == "custom_b"

        # 验证已替换
        widgets = svc.get_legacy_widgets(test_user.id)
        assert len(widgets) == 2


# ==================== Dashboard Data ====================

class TestDashboardData:
    """仪表盘数据聚合测试"""

    def _create_data_source(self, db_session, name="测试数据源"):
        ds = DataSource(
            name=name,
            type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
            password_encrypted="enc",
            is_active=True,
        )
        db_session.add(ds)
        db_session.flush()
        return ds

    def _create_query(self, db_session, user_id, data_source_id=None, exec_time_ms=None, days_ago=0):
        qh = QueryHistory(
            user_id=user_id,
            data_source_id=data_source_id,
            query_type="sql",
            query_text=f"SELECT {days_ago}",
            execution_time_ms=exec_time_ms,
            row_count=10,
        )
        db_session.add(qh)
        db_session.flush()
        return qh

    def _create_template(self, db_session, name, description, days_ago=0):
        tpl = Template(
            name=name,
            description=description,
            config='{"sql": "SELECT 1"}',
            version=1,
            is_public=False,
            created_by=0,
        )
        db_session.add(tpl)
        db_session.flush()
        return tpl

    def _create_export_task(self, db_session, user_id, days_ago=0):
        task = ExportTask(
            id=f"exp-{user_id}-{days_ago}",
            user_id=user_id,
            status="completed",
            retry_count=0,
        )
        db_session.add(task)
        db_session.flush()
        return task

    # ------------------------------------------------------------------
    # 以下测试 patch 了 cast() 以兼容 SQLite（SQLite 的 CAST ... AS DATE 行为异常）
    # 将 dssvc.cast 临时替换为 func.date，测试完成后恢复。
    # ------------------------------------------------------------------

    def test_get_dashboard_data_basic_counts(self, db_session, test_user):
        """仪表盘数据-基础计数"""
        from unittest.mock import patch
        with patch('sqlalchemy.cast', lambda col, typ: func.date(col)):
            svc = DashboardService(db_session)
            ds = self._create_data_source(db_session, "DS1")
            self._create_query(db_session, test_user.id, ds.id)
            self._create_template(db_session, "模板1", "销售预测报表")
            self._create_export_task(db_session, test_user.id)
            db_session.commit()
            data = svc.get_dashboard_data(test_user.id)
            assert data["data_source_count"] >= 1
            assert data["query_count"] >= 1
            assert data["export_count"] >= 1
            assert data["template_count"] >= 1
        # cast restored by context manager

    def test_get_dashboard_data_recent_queries(self, db_session, test_user):
        """仪表盘数据-最近查询"""
        from unittest.mock import patch
        with patch('sqlalchemy.cast', lambda col, typ: func.date(col)):
            svc = DashboardService(db_session)
            ds = self._create_data_source(db_session, "DS-Q")
            self._create_query(db_session, test_user.id, ds.id, exec_time_ms=100)
            db_session.commit()
            data = svc.get_dashboard_data(test_user.id)
            assert len(data["recent_queries"]) >= 1
            assert data["recent_queries"][0]["data_source_name"] == "DS-Q"
        # cast restored by context manager

    def test_get_dashboard_data_recent_templates(self, db_session, test_user):
        """仪表盘数据-最近模板"""
        from unittest.mock import patch
        with patch('sqlalchemy.cast', lambda col, typ: func.date(col)):
            svc = DashboardService(db_session)
            self._create_template(db_session, "T1", "预测模型")
            db_session.commit()
            data = svc.get_dashboard_data(test_user.id)
            assert len(data["recent_templates"]) >= 1
            assert data["recent_templates"][0]["name"] == "T1"
        # cast restored by context manager

    def test_get_dashboard_data_charts(self, db_session, test_user):
        """仪表盘数据-图表数据"""
        from unittest.mock import patch
        with patch('sqlalchemy.cast', lambda col, typ: func.date(col)):
            svc = DashboardService(db_session)
            ds = self._create_data_source(db_session, "销售数据源")
            self._create_query(db_session, test_user.id, ds.id, exec_time_ms=200)
            self._create_query(db_session, test_user.id, ds.id, exec_time_ms=150)
            self._create_template(db_session, "T预测", "预测分析报告")
            self._create_template(db_session, "T统计", "统计汇总")
            self._create_template(db_session, "T查询", "SQL查询报表")
            self._create_template(db_session, "T其他", "其它类型模板")
            db_session.commit()
            data = svc.get_dashboard_data(test_user.id)
            assert len(data["chart_query_trend"]) == 30
            assert len(data["chart_data_source_pie"]) >= 1
            assert len(data["chart_export_trend"]) == 7
            assert len(data["chart_template_pie"]) >= 1
            assert len(data["chart_duration_scatter"]) >= 1
        # cast restored by context manager

    def test_get_dashboard_data_empty_no_crash(self, db_session, test_user):
        """无任何数据时仪表盘数据不崩溃"""
        svc = DashboardService(db_session)
        data = svc.get_dashboard_data(test_user.id)
        assert data["data_source_count"] == 0
        assert data["query_count"] == 0
        assert data["export_count"] == 0
        assert data["template_count"] == 0
        assert data["recent_queries"] == []
        assert data["recent_templates"] == []
        assert len(data["chart_query_trend"]) == 30
        assert data["chart_data_source_pie"] == []
        assert len(data["chart_export_trend"]) == 7
        assert data["chart_template_pie"] == []
        assert data["chart_duration_scatter"] == []
