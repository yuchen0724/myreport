# backend/app/services/chart_service.py
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.schemas.chart import ChartRequest, ChartResponse
from app.schemas.query import SQLQueryRequest
from app.services.query_service import QueryService
from app.repositories.data_source_repository import DataSourceRepository

logger = logging.getLogger(__name__)


class ChartService:
    """图表服务"""

    def __init__(self, query_service: QueryService):
        self.query_service = query_service
        self.ds_repo = query_service.ds_repo  # 复用 QueryService 的数据源仓库

    def generate_chart(self, request: ChartRequest, user_id: int) -> ChartResponse:
        """
        生成图表数据

        Args:
            request: 图表请求
            user_id: 用户 ID

        Returns:
            图表响应

        Raises:
            ValueError: 当配置的 X/Y 轴字段在查询结果中不存在时
        """
        # 处理钻取路径：在原始 SQL 末尾追加 WHERE 条件
        sql = request.sql
        if request.drill_path:
            for drill in request.drill_path:
                where_clause = f"WHERE {drill.field}='{drill.value}'"
                # 只在没有 WHERE 子句时追加，否则用 AND
                # 注意：这里简化处理，在复杂查询（含子查询/UNION）时可能有问题
                import re
                if re.search(r'\bWHERE\b', sql, re.IGNORECASE):
                    sql += f" AND {drill.field}='{drill.value}'"
                else:
                    sql += f" WHERE {drill.field}='{drill.value}'"
        # 执行查询
        query_request = SQLQueryRequest(
            data_source_id=request.data_source_id,
            sql=sql,
            params={}
        )
        result = self.query_service.execute_sql(query_request, user_id)

        # 校验字段是否存在
        self._validate_fields(result.columns, request.chart_config.x_axis, request.chart_config.y_axis)

        # 获取字段中文映射
        field_name_map = self._load_field_name_map(request.data_source_id)

        # 转换数据格式
        chart_data = self._convert_to_chart_data(
            result.rows,
            result.columns,
            request.chart_config
        )

        # 获取中文名
        x_axis_label = field_name_map.get(request.chart_config.x_axis, request.chart_config.x_axis)
        y_axis_label = field_name_map.get(request.chart_config.y_axis, request.chart_config.y_axis)

        return ChartResponse(
            chart_type=request.chart_config.chart_type,
            data=chart_data,
            config={
                "x_axis": request.chart_config.x_axis,
                "y_axis": request.chart_config.y_axis,
                "x_axis_label": x_axis_label,
                "y_axis_label": y_axis_label,
                "title": request.chart_config.title,
                "color": request.chart_config.color
            }
        )

    def _validate_fields(self, columns: List[str], x_axis: str, y_axis: str) -> None:
        """
        校验配置的 X/Y 轴字段是否在查询结果中存在

        Args:
            columns: 查询返回的列名列表
            x_axis: X 轴字段名
            y_axis: Y 轴字段名

        Raises:
            ValueError: 当字段不存在时抛出详细错误信息
        """
        missing_fields = []

        if x_axis and x_axis not in columns:
            missing_fields.append(f"X轴字段 '{x_axis}'")

        if y_axis and y_axis not in columns:
            missing_fields.append(f"Y轴字段 '{y_axis}'")

        if missing_fields:
            # 提供详细的可用字段列表
            available = ", ".join(columns[:10])
            if len(columns) > 10:
                available += f" ... (共 {len(columns)} 个字段)"
            error_msg = f"{'；'.join(missing_fields)} 不存在于查询结果中。可用字段: {available}"
            raise ValueError(error_msg)

        logger.info(f"字段校验通过: x_axis={x_axis}, y_axis={y_axis}")

    def _load_field_name_map(self, data_source_id: int) -> Dict[str, str]:
        """
        加载字段中文名映射

        从语义层文档中解析字段名 -> 中文注释的映射

        Returns:
            字段名映射字典 {字段名: 中文名}
        """
        field_map = {}

        try:
            ds = self.ds_repo.get_by_id(data_source_id)
            if not ds or not ds.name:
                return field_map

            ds_name = ds.name.lower()
            db_name = ds.database.lower() if ds.database else ""
            semantic_dir = self._get_semantic_dir()

            if not semantic_dir or not semantic_dir.exists():
                return field_map

            # 优先加载该数据源下所有的 .md 文件
            ds_dir = semantic_dir / ds_name
            md_files = []
            if ds_dir.exists() and ds_dir.is_dir():
                md_files = sorted(ds_dir.glob("*.md"))
                md_files = [f for f in md_files if f.name.upper() != "README.MD"]

            # 回退策略：按数据库名查找
            if not md_files and db_name:
                single_file = semantic_dir / ds_name / f"{db_name}.md"
                if single_file.exists():
                    md_files = [single_file]

            # 解析所有 md 文件
            for md_file in md_files:
                content = md_file.read_text(encoding="utf-8")
                self._parse_field_names(content, field_map)

            logger.info(f"加载字段中文名映射: {len(field_map)} 个字段")

        except Exception as e:
            logger.warning(f"加载字段中文名映射失败: {e}")

        return field_map

    def _parse_field_names(self, content: str, field_map: Dict[str, str]) -> None:
        """
        解析语义层文档中的字段名和中文注释

        支持的格式:
        | 字段 | 类型 | 注释 |
        || store_code | VARCHAR(32) | 门店编码 |
        """
        # 匹配表格中的字段行: | field_name | ... | comment |
        # 注释可能在最后一列
        pattern = r'\|\s*(\w+)\s*\|[^|]*\|\s*([^|\n]+?)\s*\|'

        for match in re.finditer(pattern, content):
            field_name = match.group(1).strip()
            comment = match.group(2).strip()

            # 过滤掉表头、类型等无效行
            if field_name and comment and field_name not in ['字段', 'Field', 'column']:
                # 取第一个分号或顿号前的中文作为简短名称
                short_name = re.split(r'[,，;；]', comment)[0].strip()
                if short_name and len(short_name) <= 20:  # 限制长度
                    field_map[field_name] = short_name

    def _get_semantic_dir(self) -> Optional[Path]:
        """获取语义层目录"""
        possible_paths = [
            Path("/home/zhou/myreport/semantic"),
            Path(__file__).parent.parent.parent / "semantic",
            Path(__file__).parent.parent / "semantic",
        ]
        for p in possible_paths:
            if p.exists():
                return p
        return None

    def _convert_to_chart_data(
        self,
        rows: List[List[Any]],
        columns: List[str],
        config
    ) -> List[Dict[str, Any]]:
        """
        转换查询结果为图表数据

        Args:
            rows: 数据行
            columns: 列名
            config: 图表配置

        Returns:
            图表数据
        """
        chart_data = []

        # 找到 X 轴和 Y 轴的索引
        x_index = columns.index(config.x_axis) if config.x_axis in columns else 0
        y_index = columns.index(config.y_axis) if config.y_axis in columns else 1

        # 转换数据
        for row in rows:
            chart_data.append({
                "x": row[x_index],
                "y": row[y_index]
            })

        return chart_data
