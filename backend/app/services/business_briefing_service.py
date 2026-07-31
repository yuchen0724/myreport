"""Generate evidence-based business briefings from governed semantic metrics."""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, Tuple
from zoneinfo import ZoneInfo

from app.schemas.semantic_metric import SemanticMetricQueryRequest
from app.services.semantic_metric_query_service import SemanticMetricQueryService
from app.utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class BusinessBriefingService:
    def __init__(self, db):
        self.db = db
        self.metric_service = SemanticMetricQueryService(db)

    def generate(
        self, config: Dict[str, Any], user_id: int, now: datetime | None = None
    ) -> Tuple[str, str, Dict[str, Any]]:
        period = config.get("period", "yesterday")
        current, previous = self._period_ranges(period, now)
        dimensions = config.get("dimensions") or []
        filters = config.get("filters") or {}
        evidence = []

        for metric_key in (config.get("metric_keys") or [])[:10]:
            metric, current_total_result = self.metric_service.execute(
                self._request(metric_key, current, [], filters),
                user_id=user_id,
                is_admin=False,
            )
            _, previous_total_result = self.metric_service.execute(
                self._request(metric_key, previous, [], filters),
                user_id=user_id,
                is_admin=False,
            )
            breakdown_result = current_total_result
            if dimensions:
                _, breakdown_result = self.metric_service.execute(
                    self._request(metric_key, current, dimensions, filters),
                    user_id=user_id,
                    is_admin=False,
                )

            # Totals must come from a dedicated ungrouped aggregate. Summing grouped
            # rows breaks non-additive metrics such as averages and period balances.
            current_value = self._metric_value(
                current_total_result.columns, current_total_result.rows
            )
            previous_value = self._metric_value(
                previous_total_result.columns, previous_total_result.rows
            )
            change_rate = None if previous_value == 0 else (current_value - previous_value) / abs(previous_value)
            evidence.append({
                "metric_key": metric.metric_key,
                "metric_name": metric.name,
                "current_value": current_value,
                "previous_value": previous_value,
                "change_rate": change_rate,
                "current_rows": breakdown_result.total,
                "top_dimensions": (
                    self._top_dimensions(
                        breakdown_result.columns, breakdown_result.rows
                    )
                    if dimensions
                    else []
                ),
            })

        title = config.get("title") or "智能经营日报"
        payload = {
            "title": title,
            "period": {"start": current[0], "end": current[1]},
            "comparison_period": {"start": previous[0], "end": previous[1]},
            "metrics": evidence,
            "generated_at": (now or datetime.now(ZoneInfo("Asia/Shanghai"))).isoformat(),
        }
        summary = self._deterministic_summary(payload)
        if config.get("include_ai_summary", True):
            summary = self._ai_summary(payload, summary)
        return title, summary, payload

    @staticmethod
    def _request(metric_key, period, dimensions, filters):
        return SemanticMetricQueryRequest(
            metric_key=metric_key,
            start_time=period[0],
            end_time=period[1],
            dimensions=dimensions,
            filters=filters,
            page=1,
            page_size=100,
        )

    @staticmethod
    def _period_ranges(period: str, now: datetime | None) -> Tuple[Tuple[str, str], Tuple[str, str]]:
        local_now = now or datetime.now(ZoneInfo("Asia/Shanghai"))
        today = local_now.date()
        if period == "today":
            start, end = today, today + timedelta(days=1)
        elif period == "last_7_days":
            start, end = today - timedelta(days=6), today + timedelta(days=1)
        else:
            start, end = today - timedelta(days=1), today
        duration = end - start
        previous_start = start - duration
        return (
            (start.isoformat(), end.isoformat()),
            (previous_start.isoformat(), start.isoformat()),
        )

    @staticmethod
    def _metric_value(columns: Iterable[str], rows: Iterable[Any]) -> float:
        columns = list(columns or [])
        try:
            value_index = columns.index("metric_value")
        except ValueError:
            return 0.0
        for row in rows or []:
            value = row.get("metric_value") if isinstance(row, dict) else row[value_index]
            try:
                return float(value or 0)
            except (TypeError, ValueError):
                return 0.0
        return 0.0

    @classmethod
    def _top_dimensions(cls, columns: Iterable[str], rows: Iterable[Any]) -> list[Dict[str, Any]]:
        columns = list(columns or [])
        dimension_columns = [column for column in columns if column != "metric_value"]
        values = []
        for row in rows or []:
            record = dict(zip(columns, row)) if not isinstance(row, dict) else row
            try:
                metric_value = float(record.get("metric_value") or 0)
            except (TypeError, ValueError):
                metric_value = 0.0
            values.append({
                "dimensions": {column: record.get(column) for column in dimension_columns},
                "metric_value": metric_value,
            })
        return sorted(values, key=lambda item: abs(item["metric_value"]), reverse=True)[:5]

    @staticmethod
    def _deterministic_summary(payload: Dict[str, Any]) -> str:
        lines = [f"# {payload['title']}", f"统计区间：{payload['period']['start']} 至 {payload['period']['end']}"]
        for item in payload["metrics"]:
            rate = item["change_rate"]
            change = "对比期为 0，无法计算涨跌幅" if rate is None else f"环比 {rate:+.2%}"
            lines.append(
                f"- {item['metric_name']}：{item['current_value']:,.2f}（对比期 {item['previous_value']:,.2f}，{change}）"
            )
        if not payload["metrics"]:
            lines.append("- 当前未配置可用指标。")
        return "\n".join(lines)

    @staticmethod
    def _ai_summary(payload: Dict[str, Any], fallback: str) -> str:
        try:
            return get_llm_client().chat([
                {
                    "role": "system",
                    "content": "你是经营日报助手。只能引用输入证据中的数字，禁止自行计算或补造数据。输出关键变化、主要贡献项、风险和建议；没有证据时明确说明。",
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                },
            ], temperature=0.0)
        except Exception as exc:
            logger.warning("经营日报 AI 摘要生成失败: %s", exc)
            return fallback
