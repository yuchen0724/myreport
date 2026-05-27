"""
钻取服务：根据图表点击事件和钻取配置，加载目标模板并执行带参数替换的查询。
"""
import json
import time
import logging
import re
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.dashboard_widget import DashboardWidgetConfig
from app.models.template import Template
from app.schemas.dashboard import DrilldownRequest, DrilldownResponse

logger = logging.getLogger(__name__)


class DrilldownService:
    """仪表盘钻取服务"""

    def __init__(self, db: Session):
        self.db = db

    def execute_drilldown(self, request: DrilldownRequest, user_id: int) -> DrilldownResponse:
        """
        执行钻取查询：
        1. 根据 widget_id 获取钻取配置
        2. 根据 template_id 获取目标模板的 SQL
        3. 根据 click_data 和 param_mapping 替换 SQL 参数
        4. 通过 QueryService 执行查询
        """
        # 1. 获取 widget 钻取配置
        widget = (
            self.db.query(DashboardWidgetConfig)
            .filter(
                DashboardWidgetConfig.id == request.widget_id,
                DashboardWidgetConfig.user_id == user_id,
            )
            .first()
        )
        if not widget:
            raise ValueError("Widget 不存在或无权限")

        drilldown_config = widget.drilldown_config
        if not drilldown_config or not drilldown_config.get("enabled"):
            raise ValueError("该组件未启用钻取功能")

        # 2. 获取目标模板
        template = self.db.query(Template).filter(Template.id == request.template_id).first()
        if not template:
            raise ValueError(f"目标模板不存在 (id={request.template_id})")

        # 解析模板配置
        try:
            template_config = json.loads(template.config) if isinstance(template.config, str) else template.config
        except (json.JSONDecodeError, TypeError):
            raise ValueError("模板配置格式错误")

        sql = template_config.get("sql", "")
        data_source_id = template_config.get("data_source_id")
        if not sql:
            raise ValueError("模板 SQL 为空")
        if not data_source_id:
            raise ValueError("模板缺少 data_source_id")

        # 3. 参数映射：将 click_data.value 替换到 SQL 中
        param_mapping = drilldown_config.get("param_mapping", {})
        params = dict(request.params or {})

        for param_name, mapping_expr in param_mapping.items():
            resolved_value = self._resolve_mapping(mapping_expr, request.click_data)
            params[param_name] = resolved_value

        # 4. 模板自身定义的参数（如 SQL 中 ${category} 这种占位符）
        # 也合并模板预定义的 params
        template_params = template_config.get("params", {})
        for k, v in template_params.items():
            if k not in params:
                params[k] = v

        # 5. 构造下钻标题
        title = drilldown_config.get("title_template", "")
        if not title:
            label = request.click_data.label or str(request.click_data.value)
            title = f"钻取明细: {label}"

        # 6. 执行查询
        from app.services.query_service import QueryService
        from app.schemas.query import SQLQueryRequest

        query_service = QueryService(self.db)

        # 将模板 SQL 中的 ${param} 替换为 :param 以支持参数绑定
        converted_sql = sql
        for param_name in params:
            converted_sql = converted_sql.replace(f"${{{param_name}}}", f":{param_name}")

        start_time = time.time()
        try:
            sql_request = SQLQueryRequest(
                data_source_id=data_source_id,
                sql=sql,
                params=params if params else None,
                page=1,
                page_size=500,
                skip_deep_pagination_check=True,
            )
            result = query_service.execute_sql(sql_request, user_id)
            execution_time_ms = int((time.time() - start_time) * 1000)

            return DrilldownResponse(
                columns=result.columns,
                rows=result.rows,
                total=result.total,
                execution_time_ms=execution_time_ms,
                title=title,
            )
        except ValueError as e:
            raise ValueError(f"钻取查询执行失败: {e}")
        except Exception as e:
            logger.error(f"钻取查询异常: {e}", exc_info=True)
            raise ValueError(f"钻取查询执行失败: {str(e)}")

    def _resolve_mapping(self, mapping_expr: str, click_data) -> Any:
        """
        解析参数映射表达式。

        支持的表达式格式：
        - "$click.value"    → 点击的值
        - "$click.field"    → 点击的字段名
        - "$click.label"    → 点击的标签
        - "$params.xxx"     → 从 params 中取值
        - "literal_string"  → 字面量字符串
        """
        if not isinstance(mapping_expr, str):
            return mapping_expr

        mapping_expr = mapping_expr.strip()

        # $click.value
        if mapping_expr == "$click.value":
            return click_data.value
        # $click.field
        if mapping_expr == "$click.field":
            return click_data.field
        # $click.label
        if mapping_expr == "$click.label":
            return click_data.label or str(click_data.value)
        # $params.xxx
        if mapping_expr.startswith("$params."):
            param_key = mapping_expr[8:]
            # 这里 params 还没有传入，返回 None，由调用方补充
            return None

        # 字面量
        return mapping_expr

    def get_widget_drilldown_config(self, widget_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """获取 widget 的钻取配置"""
        widget = (
            self.db.query(DashboardWidgetConfig)
            .filter(
                DashboardWidgetConfig.id == widget_id,
                DashboardWidgetConfig.user_id == user_id,
            )
            .first()
        )
        if not widget:
            return None
        return widget.drilldown_config
