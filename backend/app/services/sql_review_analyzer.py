"""Deterministic SQL pre-review with optional LLM explanation."""

import json
import logging
from typing import Any, Dict, List

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from app.utils.llm_client import get_llm_client
from app.utils.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


class SqlReviewAnalyzer:
    """Produce auditable findings before a human approves SQL."""

    SEMI_ADDITIVE_TOKENS = (
        "opening", "closing", "begin_stock", "end_stock", "begin_qty",
        "end_qty", "start_inventory", "ending_inventory", "期初", "期末",
    )

    def analyze(self, sql: str, use_llm: bool = False) -> Dict[str, Any]:
        findings: List[Dict[str, str]] = []
        sql = (sql or "").strip()
        valid, validation_message = SQLValidator.validate(sql)
        if not valid:
            findings.append(self._finding(
                "unsafe_sql", "high", "SQL 未通过只读安全校验",
                validation_message, "修改为单条只读 SELECT 查询后再提交。",
            ))
            return self._result(findings, [], use_llm)

        try:
            tree = parse_one(sql)
        except ParseError as exc:
            findings.append(self._finding(
                "parse_error", "high", "SQL 无法解析", str(exc), "先修复 SQL 语法。",
            ))
            return self._result(findings, [], use_llm)

        tables = sorted({table.sql() for table in tree.find_all(exp.Table)})
        selects = list(tree.find_all(exp.Select))

        if any(self._projects_all_columns(select) for select in selects):
            findings.append(self._finding(
                "select_star", "medium", "使用了 SELECT *",
                "全字段读取会扩大扫描量，也可能意外暴露新增敏感字段。",
                "显式列出报表所需字段。",
            ))

        if tables and not any(select.args.get("where") for select in selects):
            findings.append(self._finding(
                "missing_filter", "high", "查询没有 WHERE 条件",
                "大表查询可能触发全表扫描，并遗漏日期或分区限制。",
                "增加业务范围、日期和分区过滤条件。",
            ))

        for join in tree.find_all(exp.Join):
            kind = str(join.args.get("kind") or "").upper()
            if kind == "CROSS" or (not join.args.get("on") and not join.args.get("using")):
                findings.append(self._finding(
                    "cartesian_join", "high", "存在笛卡尔积风险",
                    f"JOIN {join.this.sql()} 未发现有效关联条件。",
                    "补充 ON/USING 条件；如确需 CROSS JOIN，请由审核人确认数据规模。",
                ))

        for aggregate in tree.find_all(exp.Sum):
            target = aggregate.this.sql().lower() if aggregate.this is not None else ""
            if any(token in target for token in self.SEMI_ADDITIVE_TOKENS):
                findings.append(self._finding(
                    "semi_additive_sum", "high", "疑似直接汇总期初/期末库存",
                    f"检测到 {aggregate.sql()}。快照指标不能跨日期直接 SUM。",
                    "按区间首日取期初、末日取期末，再按商品/仓库等业务维度汇总。",
                ))

        outer = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
        if tables and outer is not None and outer.args.get("limit") is None:
            findings.append(self._finding(
                "unbounded_result", "medium", "结果集没有 LIMIT",
                "明细查询可能返回过多数据；聚合报表可由人工确认后忽略。",
                "明细预览增加 LIMIT，正式导出走异步导出流程。",
            ))

        return self._result(findings, tables, use_llm)

    @staticmethod
    def _projects_all_columns(select: exp.Select) -> bool:
        for projection in select.expressions:
            target = projection.this if isinstance(projection, exp.Alias) else projection
            if isinstance(target, exp.Star):
                return True
            if isinstance(target, exp.Column) and isinstance(target.this, exp.Star):
                return True
        return False

    @staticmethod
    def _finding(code: str, severity: str, title: str, detail: str, suggestion: str) -> Dict[str, str]:
        return {
            "code": code,
            "severity": severity,
            "title": title,
            "detail": detail,
            "suggestion": suggestion,
        }

    def _result(self, findings: List[Dict[str, str]], tables: List[str], use_llm: bool) -> Dict[str, Any]:
        severity_rank = {"low": 1, "medium": 2, "high": 3}
        risk = max((item["severity"] for item in findings), key=severity_rank.get, default="low")
        recommendation = "reject" if risk == "high" else "manual_review" if findings else "pass"
        result: Dict[str, Any] = {
            "risk_level": risk,
            "recommendation": recommendation,
            "findings": findings,
            "tables": tables,
            "engine": "sqlglot-rules-v1",
            "human_approval_required": True,
        }
        if use_llm:
            result["ai_summary"] = self._explain_with_llm(result)
        return result

    @staticmethod
    def _explain_with_llm(result: Dict[str, Any]) -> str:
        try:
            return get_llm_client().chat([
                {
                    "role": "system",
                    "content": "你是 SQL 审核助手。只能解释已检测到的事实，不得虚构执行结果；最终决定由人工审核人作出。",
                },
                {
                    "role": "user",
                    "content": "请用中文简要总结以下机器预审结果，并给出修改顺序：\n"
                    + json.dumps(result, ensure_ascii=False),
                },
            ], temperature=0.0)
        except Exception as exc:
            logger.warning("SQL 预审 LLM 解释失败: %s", exc)
            return "AI 解释暂不可用，请依据结构化风险项进行人工审核。"
