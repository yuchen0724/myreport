"""AI-assisted draft generation and deterministic metric governance checks."""

from collections import defaultdict
from typing import Any, Dict

from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.schemas.ai_design import GeneratedMetricDraft, GeneratedReportDraft
from app.schemas.semantic_metric import SemanticMetricCreate
from app.services.sql_review_analyzer import SqlReviewAnalyzer
from app.utils.llm_client import get_llm_client
from app.utils.semantic_runtime_context import build_semantic_runtime_context
from app.utils.sql_validator import SQLValidator


class AIDesignService:
    SEMI_ADDITIVE_TOKENS = ("opening", "closing", "begin_", "end_stock", "期初", "期末")

    def __init__(self, db):
        self.db = db
        self.metric_repo = SemanticMetricRepository(db)

    def generate_report_draft(
        self, data_source_id: int, requirement: str, user_id: int,
        preferred_chart: str | None = None,
    ) -> Dict[str, Any]:
        metrics = self.metric_repo.list_visible_for_data_source(
            data_source_id, user_id=user_id, is_admin=False, limit=50, active_only=True,
        )
        metric_context = [self._metric_dict(metric) for metric in metrics]
        semantic_context = build_semantic_runtime_context(
            self.db, data_source_id, requirement, max_chars=12000,
        )
        messages = [
            {
                "role": "system",
                "content": "你是报表搭建助手。只生成草稿，不发布。优先复用已有语义指标；SQL 必须是单条只读 SELECT，并包含合理日期过滤。期初期末库存必须先取边界快照。",
            },
            {
                "role": "user",
                "content": f"需求：{requirement}\n偏好图表：{preferred_chart or '自动'}\n可用指标：{metric_context}\n语义上下文：\n{semantic_context}",
            },
        ]
        try:
            generated = get_llm_client().chat_structured(messages, GeneratedReportDraft, temperature=0.0)
            draft = GeneratedReportDraft(**generated)
        except Exception:
            draft = self._fallback_report_draft(requirement, preferred_chart, metrics)

        warnings = []
        pre_review = None
        if draft.sql:
            valid, message = SQLValidator.validate(draft.sql)
            if not valid:
                warnings.append(f"生成 SQL 未通过安全校验: {message}")
                draft.sql = ""
            else:
                pre_review = SqlReviewAnalyzer().analyze(draft.sql, use_llm=False)
                warnings.extend(item["title"] for item in pre_review["findings"])
        else:
            warnings.append("当前草稿没有可执行 SQL，需要补充字段或口径后再预览。")

        return {
            "status": "draft",
            "requires_confirmation": True,
            "template": {
                "name": draft.name,
                "description": draft.description,
                "config": {
                    "data_source_id": data_source_id,
                    "sql": draft.sql,
                    "chart_type": draft.chart_type,
                    "dimensions": draft.dimensions,
                    "filters": draft.filters,
                    "semantic_metric_keys": draft.metric_keys,
                },
                "is_public": False,
            },
            "reasoning": draft.reasoning,
            "sql_pre_review": pre_review,
            "warnings": warnings,
            "evidence": {"available_metric_keys": [metric.metric_key for metric in metrics]},
        }

    def audit_metrics(self, data_source_id: int, user_id: int) -> Dict[str, Any]:
        metrics = self.metric_repo.list_visible_for_data_source(
            data_source_id, user_id=user_id, is_admin=False, limit=500, active_only=False,
        )
        findings = []
        by_signature = defaultdict(list)
        for metric in metrics:
            signature = (
                " ".join((metric.base_sql or "").lower().split()),
                " ".join((metric.metric_expression or "").lower().split()),
                metric.time_column,
                tuple(sorted(metric.dimensions or [])),
            )
            by_signature[signature].append(metric)
            if not (metric.description or "").strip():
                findings.append(self._finding("missing_description", "medium", metric, "指标缺少业务口径说明"))
            expression = (metric.metric_expression or "").lower()
            if expression.startswith("sum(") and any(token in expression for token in self.SEMI_ADDITIVE_TOKENS):
                findings.append(self._finding(
                    "semi_additive_risk", "high", metric,
                    "疑似对期初/期末库存直接 SUM；应在 base_sql 中先选边界快照",
                ))
            if not metric.dimensions:
                findings.append(self._finding("no_dimensions", "low", metric, "指标没有可下钻维度"))

        duplicate_groups = []
        for group in by_signature.values():
            if len(group) > 1:
                keys = [metric.metric_key for metric in group]
                duplicate_groups.append(keys)
                for metric in group:
                    findings.append(self._finding(
                        "duplicate_definition", "medium", metric,
                        f"与 {', '.join(key for key in keys if key != metric.metric_key)} 定义相同",
                    ))

        return {
            "data_source_id": data_source_id,
            "metric_count": len(metrics),
            "finding_count": len(findings),
            "duplicate_groups": duplicate_groups,
            "findings": findings,
            "release_gate": "blocked" if any(item["severity"] == "high" for item in findings) else "review",
        }

    def generate_metric_draft(
        self, data_source_id: int, requirement: str, user_id: int,
    ) -> Dict[str, Any]:
        existing = self.metric_repo.list_visible_for_data_source(
            data_source_id, user_id=user_id, is_admin=False, limit=100, active_only=False,
        )
        semantic_context = build_semantic_runtime_context(
            self.db, data_source_id, requirement, max_chars=12000,
        )
        messages = [
            {
                "role": "system",
                "content": "你是指标治理助手。生成待审核指标草稿，不得发布。metric_expression 仅使用 COUNT/SUM/AVG/MIN/MAX；库存快照边界逻辑必须写进 base_sql。",
            },
            {
                "role": "user",
                "content": f"需求：{requirement}\n已有指标键：{[m.metric_key for m in existing]}\n语义上下文：\n{semantic_context}",
            },
        ]
        try:
            generated = get_llm_client().chat_structured(messages, GeneratedMetricDraft, temperature=0.0)
            generated["data_source_id"] = data_source_id
            generated["is_active"] = False
            reasoning = generated.pop("reasoning", "")
            validated = SemanticMetricCreate(**generated)
            valid_sql, sql_message = SQLValidator.validate(validated.base_sql)
            if not valid_sql:
                raise ValueError(sql_message)
            draft = validated.model_dump()
            warnings = []
        except Exception as exc:
            return {
                "status": "needs_input",
                "requires_confirmation": True,
                "draft": None,
                "warnings": [f"暂时无法生成安全指标定义: {exc}"],
                "evidence": {"existing_metric_keys": [m.metric_key for m in existing]},
            }

        duplicates = [
            metric.metric_key for metric in existing
            if self._same_definition(metric, draft)
        ]
        if self.metric_repo.get_by_key(draft["metric_key"]):
            warnings.append("metric_key 已存在，发布前必须更名")
        if duplicates:
            warnings.append(f"定义疑似与现有指标重复: {', '.join(duplicates)}")
        expression = draft["metric_expression"].lower()
        if (
            expression.startswith("sum(")
            and any(token in expression for token in self.SEMI_ADDITIVE_TOKENS)
            and "row_number" not in draft["base_sql"].lower()
        ):
            warnings.append("期初/期末库存指标缺少边界快照选择逻辑，禁止直接发布")
        return {
            "status": "draft",
            "requires_confirmation": True,
            "draft": draft,
            "reasoning": reasoning,
            "warnings": warnings,
            "evidence": {"possible_duplicates": duplicates},
        }

    @staticmethod
    def _fallback_report_draft(requirement, preferred_chart, metrics):
        metric = metrics[0] if metrics else None
        sql = ""
        metric_keys = []
        if metric:
            dimensions = list(metric.dimensions or [])[:2]
            dimension_sql = ", ".join(dimensions)
            select_prefix = f"{dimension_sql}, " if dimension_sql else ""
            group_by = f" GROUP BY {dimension_sql}" if dimension_sql else ""
            sql = (
                f"SELECT {select_prefix}{metric.metric_expression} AS metric_value "
                f"FROM ({metric.base_sql}) AS metric_base{group_by} LIMIT 1000"
            )
            metric_keys = [metric.metric_key]
        return GeneratedReportDraft(
            name=requirement[:80], description="AI 生成的待审核报表草稿",
            sql=sql, chart_type=preferred_chart or "table",
            dimensions=list(metric.dimensions or [])[:2] if metric else [],
            metric_keys=metric_keys,
            reasoning="结构化生成不可用，已回退为现有语义指标草稿。",
        )

    @staticmethod
    def _metric_dict(metric):
        return {
            "metric_key": metric.metric_key, "name": metric.name,
            "description": metric.description, "dimensions": metric.dimensions,
            "time_column": metric.time_column,
        }

    @staticmethod
    def _finding(code, severity, metric, message):
        return {"code": code, "severity": severity, "metric_key": metric.metric_key, "message": message}

    @staticmethod
    def _same_definition(metric, draft):
        normalize = lambda value: " ".join((value or "").lower().split())
        return (
            normalize(metric.base_sql) == normalize(draft["base_sql"])
            and normalize(metric.metric_expression) == normalize(draft["metric_expression"])
            and metric.time_column == draft["time_column"]
            and sorted(metric.dimensions or []) == sorted(draft["dimensions"])
        )
