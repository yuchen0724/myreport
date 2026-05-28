"""RCA SQL 构建器 - 生成 Doris 异常检测和下钻 SQL"""
from typing import Optional, Dict


class RcaSqlBuilder:
    """基于 Doris 语义层的 RCA SQL 生成器"""

    def __init__(self, source_table: str, group_id: int):
        self.source_table = source_table
        self.group_id = group_id

    def _base_filter(self, dt_start: str, dt_end: str) -> str:
        """基础 WHERE 条件"""
        return (
            f"AND group_id = {self.group_id} "
            f"AND exclude_flag != 1 "
            f"AND dt >= {dt_start} AND dt <= {dt_end}"
        )

    def build_comparison_sql(
        self,
        metric_field: str,
        current_start: str, current_end: str,
        baseline_start: str, baseline_end: str,
        group_by: Optional[str] = None,
    ) -> str:
        """构建同比/环比对比 SQL"""
        select_dim = group_by or "'TOTAL'"

        return f"""
        WITH current_period AS (
            SELECT {select_dim} AS dim_key, SUM({metric_field}) AS current_val
            FROM {self.source_table}
            WHERE 1=1 {self._base_filter(current_start, current_end)}
            {"GROUP BY " + group_by if group_by else ""}
        ),
        baseline_period AS (
            SELECT {select_dim} AS dim_key, SUM({metric_field}) AS baseline_val
            FROM {self.source_table}
            WHERE 1=1 {self._base_filter(baseline_start, baseline_end)}
            {"GROUP BY " + group_by if group_by else ""}
        )
        SELECT
            COALESCE(c.dim_key, b.dim_key) AS dim_key,
            COALESCE(c.current_val, 0) AS current_val,
            COALESCE(b.baseline_val, 0) AS baseline_val,
            CASE WHEN COALESCE(b.baseline_val, 0) > 0
                 THEN ROUND((COALESCE(c.current_val, 0) - b.baseline_val) / b.baseline_val * 100, 2)
                 ELSE 0 END AS change_pct
        FROM current_period c
        FULL OUTER JOIN baseline_period b ON c.dim_key = b.dim_key
        ORDER BY ABS(COALESCE(c.current_val, 0) - COALESCE(b.baseline_val, 0)) DESC
        """

    # 维度 → 名称字段映射
    _NAME_MAP = {
        "store_code": ("ads_cockpit_qck.dim_store", "store_name"),
        "matnr": (None, "ware_name"),  # ware_name 在主表中
    }

    def build_drill_down_sql(
        self,
        metric_field: str,
        current_start: str, current_end: str,
        baseline_start: str, baseline_end: str,
        dimension: str,
        parent_filters: Optional[Dict[str, str]] = None,
    ) -> str:
        """构建维度下钻 SQL - 计算各维度值的贡献度"""
        extra = ""
        if parent_filters:
            for k, v in parent_filters.items():
                extra += f" AND {k} = '{v}'"

        # 名称字段
        name_info = self._NAME_MAP.get(dimension)
        name_join = ""
        name_select = ""
        if name_info:
            join_table, name_col = name_info
            if join_table:
                # 需要 JOIN 维表（如 dim_store），用 MIN 去重避免一对多产生重复行
                name_join = f"LEFT JOIN (SELECT {dimension}, MIN({name_col}) AS {name_col} FROM {join_table} GROUP BY {dimension}) n ON diff.dim_val = n.{dimension}"
                name_select = f", n.{name_col} AS dim_name"
            else:
                # 名称字段在主表中（如 ware_name），CTE 已带上
                name_select = ""  # 由 ware_name_diff_select 处理

        # 如果需要 ware_name，在 CTE 中也 SELECT 出来
        ware_name_cte_select = ""
        ware_name_diff_select = ""
        ware_name_final_select = ""
        if dimension == "matnr":
            # ware_name 函数依赖于 matnr，用 MAX 取名即可
            ware_name_cte_select = ", MAX(ware_name) AS dim_name"
            ware_name_diff_select = ", c.dim_name"
            ware_name_final_select = ", diff.dim_name"

        # 合并名称选择
        final_name_select = name_select or ware_name_final_select

        return f"""
        WITH current_period AS (
            SELECT {dimension} AS dim_val, SUM({metric_field}) AS current_val{ware_name_cte_select}
            FROM {self.source_table}
            WHERE 1=1 {self._base_filter(current_start, current_end)} {extra}
            GROUP BY {dimension}
        ),
        baseline_period AS (
            SELECT {dimension} AS dim_val, SUM({metric_field}) AS baseline_val
            FROM {self.source_table}
            WHERE 1=1 {self._base_filter(baseline_start, baseline_end)} {extra}
            GROUP BY {dimension}
        ),
        diff AS (
            SELECT
                COALESCE(c.dim_val, b.dim_val) AS dim_val,
                COALESCE(c.current_val, 0) AS current_val,
                COALESCE(b.baseline_val, 0) AS baseline_val,
                COALESCE(c.current_val, 0) - COALESCE(b.baseline_val, 0) AS abs_diff{ware_name_diff_select}
            FROM current_period c
            FULL OUTER JOIN baseline_period b ON c.dim_val = b.dim_val
        )
        SELECT diff.dim_val, current_val, baseline_val,
            ROUND(abs_diff / 100.0, 2) AS change_yuan,
            CASE WHEN baseline_val > 0
                 THEN ROUND((current_val - baseline_val) / baseline_val * 100, 2)
                 ELSE 0 END AS change_pct,
            CASE WHEN SUM(abs_diff) OVER () != 0
                 THEN ROUND(ABS(abs_diff) / SUM(ABS(abs_diff)) OVER () * 100, 2)
                 ELSE 0 END AS contribution_pct
            {final_name_select}
        FROM diff
        {name_join}
        WHERE abs_diff < 0
        ORDER BY abs_diff ASC
        LIMIT 20
        """
