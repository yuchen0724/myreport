"""Deterministic inventory analysis with boundary snapshot semantics."""

import json
import logging
from datetime import date
from typing import Any, Dict, Iterable

from app.schemas.inventory_copilot import InventoryCopilotRequest
from app.schemas.query import SQLQueryRequest
from app.services.query_service import QueryService
from app.utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class InventoryCopilotService:
    def __init__(self, db):
        self.db = db
        self.query_service = QueryService(db)

    def analyze(self, request: InventoryCopilotRequest, user_id: int) -> Dict[str, Any]:
        sql, params = self.build_query(request)
        result = self.query_service.execute_sql(
            SQLQueryRequest(
                data_source_id=request.data_source_id,
                sql=sql,
                params=params,
                page=1,
                page_size=request.limit,
                skip_deep_pagination_check=True,
            ),
            user_id=user_id,
        )
        records = self._records(result.columns, result.rows)
        evidence = self._evaluate(records, request)
        response = {
            "period": {"start": request.start_date, "end": request.end_date},
            "snapshot_rule": {
                "opening": "start-date opening field" if request.fields.opening_stock_field else "latest closing snapshot before start",
                "closing": "latest closing snapshot on or before end",
                "flow": "sum within inclusive date range",
            },
            "columns": result.columns,
            "rows": result.rows,
            "total": result.total,
            "actions": evidence["actions"],
            "summary": evidence["summary"],
            "sql": sql,
            "params": params,
        }
        if request.include_ai_summary:
            response["ai_summary"] = self._ai_summary(response)
        return response

    @staticmethod
    def build_query(request: InventoryCopilotRequest) -> tuple[str, Dict[str, Any]]:
        fields = request.fields
        dimensions = request.dimensions
        dimension_sql = ", ".join(dimensions)
        entity_sql = ", ".join(request.entity_keys)
        filters = []
        params: Dict[str, Any] = {"start_date": request.start_date, "end_date": request.end_date}
        for index, (field, value) in enumerate(request.filters.items()):
            name = f"filter_{index}"
            filters.append(f"{field} = :{name}")
            params[name] = value
        filter_sql = "" if not filters else " AND " + " AND ".join(filters)

        opening_value = fields.opening_stock_field or fields.closing_stock_field
        opening_operator = "=" if fields.opening_stock_field else "<"
        flow_fields = {
            "sales_qty": fields.sales_field,
            "receipt_qty": fields.receipt_field,
            "other_inbound_qty": fields.other_inbound_field,
            "other_outbound_qty": fields.other_outbound_field,
        }
        flow_selects = [
            f"SUM(COALESCE({field}, 0)) AS {alias}" if field else f"0 AS {alias}"
            for alias, field in flow_fields.items()
        ]

        sql = f"""
WITH opening_ranked AS (
    SELECT {entity_sql}, {opening_value} AS snapshot_qty, {fields.date_field} AS snapshot_dt,
           ROW_NUMBER() OVER (PARTITION BY {entity_sql} ORDER BY {fields.date_field} DESC) AS rn
    FROM {request.table_name}
    WHERE {fields.date_field} {opening_operator} :start_date{filter_sql}
),
opening_snapshot AS (
    SELECT {dimension_sql}, SUM(COALESCE(snapshot_qty, 0)) AS opening_qty,
           MIN(snapshot_dt) AS opening_snapshot_dt_min, MAX(snapshot_dt) AS opening_snapshot_dt_max
    FROM opening_ranked WHERE rn = 1 GROUP BY {dimension_sql}
),
closing_ranked AS (
    SELECT {entity_sql}, {fields.closing_stock_field} AS snapshot_qty, {fields.date_field} AS snapshot_dt,
           ROW_NUMBER() OVER (PARTITION BY {entity_sql} ORDER BY {fields.date_field} DESC) AS rn
    FROM {request.table_name}
    WHERE {fields.date_field} <= :end_date{filter_sql}
),
closing_snapshot AS (
    SELECT {dimension_sql}, SUM(COALESCE(snapshot_qty, 0)) AS closing_qty,
           MIN(snapshot_dt) AS closing_snapshot_dt_min, MAX(snapshot_dt) AS closing_snapshot_dt_max
    FROM closing_ranked WHERE rn = 1 GROUP BY {dimension_sql}
),
period_flow AS (
    SELECT {dimension_sql}, {', '.join(flow_selects)}
    FROM {request.table_name}
    WHERE {fields.date_field} >= :start_date AND {fields.date_field} <= :end_date{filter_sql}
    GROUP BY {dimension_sql}
),
all_keys AS (
    SELECT {dimension_sql} FROM opening_snapshot
    UNION SELECT {dimension_sql} FROM closing_snapshot
    UNION SELECT {dimension_sql} FROM period_flow
)
SELECT {', '.join(f'k.{item}' for item in dimensions)},
       COALESCE(o.opening_qty, 0) AS opening_qty, o.opening_snapshot_dt_min, o.opening_snapshot_dt_max,
       COALESCE(f.receipt_qty, 0) AS receipt_qty,
       COALESCE(f.other_inbound_qty, 0) AS other_inbound_qty,
       COALESCE(f.sales_qty, 0) AS sales_qty,
       COALESCE(f.other_outbound_qty, 0) AS other_outbound_qty,
       COALESCE(c.closing_qty, 0) AS closing_qty, c.closing_snapshot_dt_min, c.closing_snapshot_dt_max
FROM all_keys k
LEFT JOIN opening_snapshot o ON {InventoryCopilotService._join(dimensions, 'k', 'o')}
LEFT JOIN closing_snapshot c ON {InventoryCopilotService._join(dimensions, 'k', 'c')}
LEFT JOIN period_flow f ON {InventoryCopilotService._join(dimensions, 'k', 'f')}
ORDER BY closing_qty DESC
LIMIT {request.limit}
"""
        return " ".join(sql.split()), params

    @staticmethod
    def _join(dimensions: Iterable[str], left: str, right: str) -> str:
        return " AND ".join(f"{left}.{dimension} = {right}.{dimension}" for dimension in dimensions)

    @staticmethod
    def _records(columns, rows):
        return [dict(zip(columns, row)) if not isinstance(row, dict) else row for row in rows]

    @staticmethod
    def _number(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _evaluate(self, records, request):
        try:
            days = (date.fromisoformat(request.end_date) - date.fromisoformat(request.start_date)).days + 1
        except ValueError:
            days = 1
        actions = []
        counts = {"stockout": 0, "shortage": 0, "overstock": 0, "slow_moving": 0, "balance_mismatch": 0}
        for record in records:
            opening = self._number(record.get("opening_qty"))
            closing = self._number(record.get("closing_qty"))
            sales = self._number(record.get("sales_qty"))
            receipts = self._number(record.get("receipt_qty"))
            other_in = self._number(record.get("other_inbound_qty"))
            other_out = self._number(record.get("other_outbound_qty"))
            daily_sales = sales / max(days, 1)
            cover_days = None if daily_sales <= 0 else closing / daily_sales
            action_type = None
            recommendation = None
            if closing <= 0 and sales > 0:
                action_type, recommendation = "stockout", "优先核查可售库存并补货或调拨"
            elif cover_days is not None and cover_days < request.stockout_cover_days:
                action_type, recommendation = "shortage", "按近期日均销量补足安全库存"
            elif sales <= 0 and closing > 0:
                action_type, recommendation = "slow_moving", "核查陈列、定价和清库存方案"
            elif cover_days is not None and cover_days > request.overstock_cover_days:
                action_type, recommendation = "overstock", "暂停补货并评估跨仓调拨或促销"
            if action_type:
                counts[action_type] += 1
                actions.append({
                    "type": action_type,
                    "dimensions": {key: record.get(key) for key in request.dimensions},
                    "opening_qty": opening,
                    "closing_qty": closing,
                    "sales_qty": sales,
                    "stock_cover_days": cover_days,
                    "recommendation": recommendation,
                })
            expected_closing = opening + receipts + other_in - sales - other_out
            tolerance = max(1.0, abs(closing) * 0.001)
            balance_enabled = bool(request.fields.sales_field and request.fields.receipt_field)
            if balance_enabled and abs(expected_closing - closing) > tolerance:
                counts["balance_mismatch"] += 1
                actions.append({
                    "type": "balance_mismatch",
                    "dimensions": {key: record.get(key) for key in request.dimensions},
                    "expected_closing_qty": expected_closing,
                    "actual_closing_qty": closing,
                    "difference": closing - expected_closing,
                    "recommendation": "核查退货、调拨、盘点或字段口径是否遗漏",
                })
        actions.sort(key=lambda item: abs(item.get("difference", 0)) + abs(item.get("closing_qty", 0)), reverse=True)
        return {"summary": {"row_count": len(records), **counts}, "actions": actions[:200]}

    @staticmethod
    def _ai_summary(response: Dict[str, Any]) -> str:
        evidence = {
            "period": response["period"],
            "snapshot_rule": response["snapshot_rule"],
            "summary": response["summary"],
            "actions": response["actions"][:30],
        }
        try:
            return get_llm_client().chat([
                {
                    "role": "system",
                    "content": "你是进销存决策助手。只能解释给定证据，不得重新汇总期初期末，不得编造补货量。按风险、证据、建议三段输出。",
                },
                {"role": "user", "content": json.dumps(evidence, ensure_ascii=False, default=str)},
            ], temperature=0.0)
        except Exception as exc:
            logger.warning("进销存 AI 摘要生成失败: %s", exc)
            return "AI 解读暂不可用，请依据结构化风险和快照日期处理。"
