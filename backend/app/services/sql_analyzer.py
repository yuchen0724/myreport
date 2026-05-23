"""SQL 复杂度分析器

分析 SQL 语句的复杂度、检测慢查询模式、生成优化建议。
纯规则驱动，不依赖 LLM（与 sql_optimizer 互补）。
"""
import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class SQLIssue:
    type: str
    severity: str
    position: str
    description: str


@dataclass
class SQLSuggestion:
    action: str
    field: str
    description: str


@dataclass
class SQLComplexityMetrics:
    select_column_count: int = 0
    join_count: int = 0
    subquery_depth: int = 0
    group_by_count: int = 0
    order_by_count: int = 0
    function_call_count: int = 0
    where_condition_count: int = 0
    has_select_star: bool = False
    has_or_in_where: bool = False
    has_subquery_in_select: bool = False
    has_subquery_in_where: bool = False
    has_left_join: bool = False
    has_distinct: bool = False
    has_union: int = 0
    has_having: bool = False
    table_count: int = 0


class SQLAnalyzer:
    """SQL 复杂度分析器

    特性:
    1. 纯规则驱动，不调用 LLM
    2. 复杂度评分 1-100
    3. 检测常见慢查询模式
    4. 生成优化建议
    """

    ANALYZER_VERSION = "v1"

    # ── 评分权重 ──
    WEIGHTS = {
        "join": 8,
        "subquery": 12,
        "select_star": 10,
        "or_in_where": 6,
        "no_where": 15,
        "function_call": 2,
        "group_by": 3,
        "order_by": 2,
        "distinct": 4,
        "union": 5,
        "having": 3,
        "left_join": 4,
        "table_count": 5,
        "column_count": 1,
    }

    # ── 聚合函数列表 ──
    AGGREGATE_FUNCTIONS = {
        "COUNT", "SUM", "AVG", "MAX", "MIN",
        "STDDEV", "VARIANCE", "PERCENTILE",
        "COLLECT_LIST", "COLLECT_SET",  # Doris/Hive
    }

    # ── 公开接口 ──

    def analyze(self, sql: str) -> Dict[str, Any]:
        """分析 SQL 并返回完整结果

        Returns:
            {
                "sql_hash": str,
                "complexity_score": int,
                "complexity_level": str,
                "metrics": {...},
                "issues": [...],
                "suggestions": [...],
                "estimated_time_ms": int|None,
            }
        """
        sql_stripped = sql.strip()
        if not sql_stripped:
            return self._empty_result()

        sql_normalized = self._normalize(sql_stripped)
        sql_hash = self._hash(sql_normalized)

        # 1. 提取指标
        metrics = self._extract_metrics(sql_normalized)

        # 2. 计算复杂度评分
        score = self._compute_score(metrics)

        # 3. 确定复杂度等级
        level = self._determine_level(score)
        level_str = level.value if hasattr(level, 'value') else str(level)

        # 4. 检测问题
        issues = self._detect_issues(sql_normalized, metrics)

        # 5. 生成建议
        suggestions = self._generate_suggestions(sql_normalized, metrics, issues)

        # 6. 预估耗时
        estimated_ms = self._estimate_time(score, metrics)

        return {
            "sql_hash": sql_hash,
            "complexity_score": score,
            "complexity_level": level if isinstance(level, str) else level.value,
            "metrics": {
                "select_column_count": metrics.select_column_count,
                "join_count": metrics.join_count,
                "subquery_depth": metrics.subquery_depth,
                "group_by_count": metrics.group_by_count,
                "order_by_count": metrics.order_by_count,
                "function_call_count": metrics.function_call_count,
                "where_condition_count": metrics.where_condition_count,
                "table_count": metrics.table_count,
                "has_select_star": metrics.has_select_star,
                "has_or_in_where": metrics.has_or_in_where,
                "has_distinct": metrics.has_distinct,
                "has_union": metrics.has_union,
            },
            "issues": [self._issue_to_dict(i) for i in issues],
            "suggestions": [self._suggestion_to_dict(s) for s in suggestions],
            "estimated_time_ms": estimated_ms,
            "has_full_table_scan_risk": "yes" if any(i.type == "full_table_scan" for i in issues) else "no",
            "missing_where_clause": "yes" if any(i.type == "no_where_clause" for i in issues) else "no",
        }

    # ── SQL 预处理 ──

    @staticmethod
    def _normalize(sql: str) -> str:
        """标准化 SQL：去除多余空白、统一大小写"""
        # 去除行尾注释
        sql = re.sub(r'--\s*$', '', sql, flags=re.MULTILINE)
        # 去除块注释
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        # 多空白 → 单空白
        sql = re.sub(r'\s+', ' ', sql).strip()
        # 统一关键字大写
        keywords = [
            'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'IS',
            'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'FULL',
            'ON', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'OFFSET',
            'UNION', 'ALL', 'INTERSECT', 'EXCEPT', 'DISTINCT',
            'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP',
            'AS', 'BETWEEN', 'LIKE', 'EXISTS', 'CASE', 'WHEN', 'THEN',
            'ELSE', 'END', 'WITH', 'ASC', 'DESC', 'NULL', 'TRUE', 'FALSE',
        ]
        for kw in keywords:
            pattern = r'\b' + kw + r'\b'
            sql = re.sub(pattern, kw, sql, flags=re.IGNORECASE)
        return sql

    @staticmethod
    def _hash(sql: str) -> str:
        return hashlib.sha256(sql.encode("utf-8")).hexdigest()

    # ── 指标提取 ──

    def _extract_metrics(self, sql: str) -> SQLComplexityMetrics:
        m = SQLComplexityMetrics()

        # SELECT 列数
        m.select_column_count = self._count_select_columns(sql)
        m.has_select_star = self._has_select_star(sql)

        # JOIN
        m.join_count = self._count_joins(sql)
        m.has_left_join = bool(re.search(r'\bLEFT\s+JOIN\b', sql, re.IGNORECASE))

        # 子查询
        m.subquery_depth = self._calc_subquery_depth(sql)
        m.has_subquery_in_select = self._has_subquery_in_select(sql)
        m.has_subquery_in_where = self._has_subquery_in_where(sql)

        # GROUP BY / ORDER BY / HAVING
        m.group_by_count = self._count_group_by(sql)
        m.order_by_count = self._count_order_by(sql)
        m.has_having = bool(re.search(r'\bHAVING\b', sql, re.IGNORECASE))

        # 函数调用
        m.function_call_count = self._count_function_calls(sql)

        # WHERE 条件
        m.where_condition_count = self._count_where_conditions(sql)
        m.has_or_in_where = self._has_or_in_where(sql)

        # DISTINCT / UNION
        m.has_distinct = bool(re.search(r'\bSELECT\s+DISTINCT\b', sql, re.IGNORECASE))
        m.has_union = len(re.findall(r'\bUNION\b', sql, re.IGNORECASE))

        # 表数量
        m.table_count = self._count_tables(sql)

        return m

    def _count_select_columns(self, sql: str) -> int:
        match = re.search(r'\bSELECT\s+(DISTINCT\s+)?(.*?)\bFROM\b', sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return 0
        cols_str = match.group(2).strip()
        if cols_str == '*':
            return 1
        # 简单计数：按顶层逗号分割
        return len(self._split_top_level(cols_str, ','))

    def _has_select_star(self, sql: str) -> bool:
        return bool(re.search(r'\bSELECT\s+\*\s*FROM\b', sql, re.IGNORECASE))

    def _count_joins(self, sql: str) -> int:
        return len(re.findall(
            r'\b(INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\b', sql, re.IGNORECASE
        ))

    def _calc_subquery_depth(self, sql: str) -> int:
        """计算子查询最大嵌套深度"""
        max_depth = 0
        depth = 0
        for ch in sql:
            if ch == '(':
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch == ')':
                depth = max(0, depth - 1)
        # 减去函数调用产生的括号
        func_calls = len(re.findall(r'\w+\s*\(', sql))
        return max(0, max_depth - func_calls)

    def _has_subquery_in_select(self, sql: str) -> bool:
        match = re.search(r'\bSELECT\s+(.*?)\bFROM\b', sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return False
        return '(' in match.group(1)

    def _has_subquery_in_where(self, sql: str) -> bool:
        match = re.search(r'\bWHERE\b(.+?)(?:\bGROUP BY\b|\bORDER BY\b|\bHAVING\b|\bLIMIT\b|$)',
                          sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return False
        where_clause = match.group(1)
        return bool(re.search(r'\bSELECT\b', where_clause, re.IGNORECASE))

    def _count_group_by(self, sql: str) -> int:
        match = re.search(r'\bGROUP\s+BY\s+(.*?)(?:\bHAVING\b|\bORDER BY\b|\bLIMIT\b|$)',
                          sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return 0
        return len(self._split_top_level(match.group(1).strip(), ','))

    def _count_order_by(self, sql: str) -> int:
        match = re.search(r'\bORDER\s+BY\s+(.*?)(?:\bLIMIT\b|\bOFFSET\b|$)',
                          sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return 0
        return len(self._split_top_level(match.group(1).strip(), ','))

    def _count_function_calls(self, sql: str) -> int:
        # 统计聚合函数 + 常用函数
        funcs = self.AGGREGATE_FUNCTIONS | {
            "DATE", "DATE_FORMAT", "COALESCE", "IFNULL", "NULLIF",
            "CAST", "CONVERT", "CONCAT", "SUBSTRING", "TRIM",
            "UPPER", "LOWER", "LENGTH", "ROUND", "FLOOR", "CEIL",
            "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD",
            "FIRST_VALUE", "LAST_VALUE",
        }
        pattern = r'\b(' + '|'.join(funcs) + r')\s*\('
        return len(re.findall(pattern, sql, re.IGNORECASE))

    def _count_where_conditions(self, sql: str) -> int:
        match = re.search(r'\bWHERE\b(.+?)(?:\bGROUP BY\b|\bORDER BY\b|\bHAVING\b|\bLIMIT\b|$)',
                          sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return 0
        where_clause = match.group(1)
        # 顶层 AND/OR 分割
        ands = len(re.findall(r'\bAND\b', where_clause, re.IGNORECASE))
        ors = len(re.findall(r'\bOR\b', where_clause, re.IGNORECASE))
        return 1 + ands + ors

    def _has_or_in_where(self, sql: str) -> bool:
        match = re.search(r'\bWHERE\b(.+?)(?:\bGROUP BY\b|\bORDER BY\b|\bHAVING\b|\bLIMIT\b|$)',
                          sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return False
        return bool(re.search(r'\bOR\b', match.group(1), re.IGNORECASE))

    def _count_tables(self, sql: str) -> int:
        """统计 FROM/JOIN 中引用的表数量"""
        # FROM 子句中的表
        tables = set()
        from_match = re.finditer(
            r'\bFROM\s+(\w+(?:\.\w+)*)', sql, re.IGNORECASE
        )
        for m in from_match:
            tables.add(m.group(1).lower())
        # JOIN 子句中的表
        join_match = re.finditer(
            r'\bJOIN\s+(\w+(?:\.\w+)*)', sql, re.IGNORECASE
        )
        for m in join_match:
            tables.add(m.group(1).lower())
        return len(tables)

    # ── 评分算法 ──

    def _compute_score(self, metrics: SQLComplexityMetrics) -> int:
        """计算复杂度评分 (1-100)"""
        score = 0.0

        score += metrics.join_count * self.WEIGHTS["join"]
        score += metrics.subquery_depth * self.WEIGHTS["subquery"]
        score += metrics.group_by_count * self.WEIGHTS["group_by"]
        score += metrics.order_by_count * self.WEIGHTS["order_by"]
        score += metrics.function_call_count * self.WEIGHTS["function_call"]
        score += metrics.table_count * self.WEIGHTS["table_count"]
        score += min(metrics.select_column_count, 20) * self.WEIGHTS["column_count"]

        if metrics.has_select_star:
            score += self.WEIGHTS["select_star"]
        if metrics.has_or_in_where:
            score += self.WEIGHTS["or_in_where"]
        if metrics.where_condition_count == 0:
            score += self.WEIGHTS["no_where"]
        if metrics.has_distinct:
            score += self.WEIGHTS["distinct"]
        if metrics.has_union > 0:
            score += self.WEIGHTS["union"] * metrics.has_union
        if metrics.has_having:
            score += self.WEIGHTS["having"]
        if metrics.has_left_join:
            score += self.WEIGHTS["left_join"]

        return max(1, min(100, int(score)))

    @staticmethod
    def _determine_level(score: int) -> str:
        if score <= 20:
            return "low"
        elif score <= 45:
            return "medium"
        elif score <= 70:
            return "high"
        else:
            return "critical"

    # ── 问题检测 ──

    def _detect_issues(self, sql: str, metrics: SQLComplexityMetrics) -> List[SQLIssue]:
        issues: List[SQLIssue] = []

        # 1. SELECT *
        if metrics.has_select_star:
            issues.append(SQLIssue(
                type="select_star",
                severity=IssueSeverity.WARNING,
                position="SELECT",
                description="使用了 SELECT *，会返回所有列，增加网络传输和内存消耗",
            ))

        # 2. 无 WHERE 条件
        if metrics.where_condition_count == 0 and not self._is_ddl(sql):
            issues.append(SQLIssue(
                type="no_where_clause",
                severity=IssueSeverity.CRITICAL,
                position="FROM",
                description="缺少 WHERE 条件，可能导致全表扫描",
            ))

        # 3. OR 拼接
        if metrics.has_or_in_where:
            issues.append(SQLIssue(
                type="or_in_where",
                severity=IssueSeverity.WARNING,
                position="WHERE",
                description="WHERE 中使用 OR 拼接，部分数据库无法使用索引；建议改用 IN 或 UNION",
            ))

        # 4. 子查询嵌套过深
        if metrics.subquery_depth >= 3:
            issues.append(SQLIssue(
                type="deep_subquery",
                severity=IssueSeverity.WARNING,
                position="SUBQUERY",
                description=f"子查询嵌套深度 {metrics.subquery_depth} 层，建议改用 CTE 或 JOIN",
            ))

        # 5. JOIN 过多
        if metrics.join_count >= 5:
            issues.append(SQLIssue(
                type="too_many_joins",
                severity=IssueSeverity.WARNING,
                position="JOIN",
                description=f"JOIN 数量 {metrics.join_count} 个，可能导致执行计划复杂化",
            ))

        # 6. LEFT JOIN 可能产生笛卡尔积
        if metrics.has_left_join and metrics.join_count >= 3:
            issues.append(SQLIssue(
                type="left_join_risk",
                severity=IssueSeverity.INFO,
                position="JOIN",
                description="多表 LEFT JOIN 可能导致结果集膨胀，请确认关联条件正确",
            ))

        # 7. DISTINCT 可能掩盖重复数据
        if metrics.has_distinct:
            issues.append(SQLIssue(
                type="distinct_usage",
                severity=IssueSeverity.INFO,
                position="SELECT",
                description="使用 DISTINCT 去重，可能掩盖数据重复问题；建议检查 JOIN 条件",
            ))

        # 8. UNION 无 ALL
        if metrics.has_union > 0:
            union_without_all = re.search(r'\bUNION\s+(?!ALL\b)\w', sql, re.IGNORECASE)
            if union_without_all:
                issues.append(SQLIssue(
                    type="union_without_all",
                    severity=IssueSeverity.INFO,
                    position="UNION",
                    description="UNION 会执行去重排序，如无需去重建议使用 UNION ALL",
                ))

        # 9. 全表扫描风险（无 WHERE 且有 ORDER BY）
        if metrics.where_condition_count == 0 and metrics.order_by_count > 0:
            issues.append(SQLIssue(
                type="full_table_scan",
                severity=IssueSeverity.CRITICAL,
                position="ORDER BY",
                description="无 WHERE 条件 + ORDER BY，将触发全表扫描 + 排序",
            ))

        # 10. 函数作用在索引列上
        func_on_col = re.search(
            r'\b(?:DATE|DATE_FORMAT|COALESCE|UPPER|LOWER|TRIM|SUBSTRING|ROUND|CAST)\s*\(\s*\w+\.',
            sql, re.IGNORECASE
        )
        if func_on_col:
            issues.append(SQLIssue(
                type="function_on_indexed_column",
                severity=IssueSeverity.WARNING,
                position="WHERE",
                description="函数作用于列上可能导致索引失效，建议改写为范围查询",
            ))

        return issues

    # ── 建议生成 ──

    def _generate_suggestions(
        self, sql: str, metrics: SQLComplexityMetrics, issues: List[SQLIssue]
    ) -> List[SQLSuggestion]:
        suggestions: List[SQLSuggestion] = []

        issue_types = {i.type for i in issues}

        if "select_star" in issue_types:
            suggestions.append(SQLSuggestion(
                action="replace_select_star",
                field="SELECT",
                description="将 SELECT * 替换为具体需要的列名",
            ))

        if "no_where_clause" in issue_types:
            suggestions.append(SQLSuggestion(
                action="add_where",
                field="WHERE",
                description="添加 WHERE 条件限制数据范围，避免全表扫描",
            ))

        if "or_in_where" in issue_types:
            # 检查是否可以转为 IN
            or_equal = re.search(r'(\w+)\s*=\s*[\'"]?\w+[\'"]?\s+OR\s+\1\s*=', sql, re.IGNORECASE)
            if or_equal:
                suggestions.append(SQLSuggestion(
                    action="or_to_in",
                    field=or_equal.group(1),
                    description=f"将 {or_equal.group(1)} 上的 OR 条件改写为 IN 子句",
                ))
            else:
                suggestions.append(SQLSuggestion(
                    action="or_to_union",
                    field="WHERE",
                    description="将 OR 条件改写为 UNION ALL 提升性能",
                ))

        if "deep_subquery" in issue_types:
            suggestions.append(SQLSuggestion(
                action="subquery_to_cte",
                field="WITH",
                description="使用 WITH (CTE) 替代嵌套子查询，提升可读性和性能",
            ))

        if "too_many_joins" in issue_types:
            suggestions.append(SQLSuggestion(
                action="reduce_joins",
                field="JOIN",
                description="考虑拆分为多个查询或使用临时表减少 JOIN 数量",
            ))

        if "function_on_indexed_column" in issue_types:
            suggestions.append(SQLSuggestion(
                action="avoid_function_on_column",
                field="WHERE",
                description="避免在 WHERE 条件的列上使用函数，改用范围查询（如 DATE(col) = '2025-01-01' → col >= '2025-01-01' AND col < '2025-01-02'）",
            ))

        if "distinct_usage" in issue_types:
            suggestions.append(SQLSuggestion(
                action="check_join_conditions",
                field="JOIN",
                description="检查 JOIN 条件是否遗漏，消除数据重复根因",
            ))

        if "union_without_all" in issue_types:
            suggestions.append(SQLSuggestion(
                action="use_union_all",
                field="UNION",
                description="如无需去重，将 UNION 改为 UNION ALL 避免排序开销",
            ))

        # 通用建议：GROUP BY 列数过多
        if metrics.group_by_count > 10:
            suggestions.append(SQLSuggestion(
                action="reduce_group_by",
                field="GROUP BY",
                description=f"GROUP BY 包含 {metrics.group_by_count} 个字段，考虑预聚合或减少维度",
            ))

        return suggestions

    # ── 预估耗时 ──

    def _estimate_time(self, score: int, metrics: SQLComplexityMetrics) -> Optional[int]:
        """粗略预估执行时间 (ms)，基于复杂度评分"""
        # 基础时间：简单查询 ~100ms
        base_ms = 100
        # 复杂度线性增长
        estimated = base_ms + score * 50
        # JOIN 对数增长
        if metrics.join_count > 0:
            estimated += metrics.join_count * 200
        # 子查询指数增长
        if metrics.subquery_depth > 0:
            estimated += (2 ** metrics.subquery_depth) * 100
        # 无 WHERE 大幅增加
        if metrics.where_condition_count == 0:
            estimated *= 3

        return min(estimated, 300000)  # 上限 5 分钟

    # ── 辅助方法 ──

    @staticmethod
    def _is_ddl(sql: str) -> bool:
        """判断是否为 DDL 语句"""
        return bool(re.match(r'^\s*(CREATE|ALTER|DROP|TRUNCATE)\b', sql, re.IGNORECASE))

    @staticmethod
    def _split_top_level(s: str, delimiter: str = ',') -> List[str]:
        """按分隔符分割字符串，忽略括号内的内容"""
        parts = []
        depth = 0
        current = []
        for ch in s:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth = max(0, depth - 1)
            elif ch == delimiter and depth == 0:
                parts.append(''.join(current).strip())
                current = []
                continue
            current.append(ch)
        if current:
            parts.append(''.join(current).strip())
        return [p for p in parts if p]

    @staticmethod
    def _issue_to_dict(issue: SQLIssue) -> Dict[str, str]:
        return {
            "type": issue.type,
            "severity": issue.severity if isinstance(issue.severity, str) else issue.severity.value,
            "position": issue.position,
            "description": issue.description,
        }

    @staticmethod
    def _suggestion_to_dict(suggestion: SQLSuggestion) -> Dict[str, str]:
        return {
            "action": suggestion.action,
            "field": suggestion.field,
            "description": suggestion.description,
        }

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {
            "sql_hash": "",
            "complexity_score": 0,
            "complexity_level": "low",
            "metrics": {
                "select_column_count": 0,
                "join_count": 0,
                "subquery_depth": 0,
                "group_by_count": 0,
                "order_by_count": 0,
                "function_call_count": 0,
                "where_condition_count": 0,
                "table_count": 0,
                "has_select_star": False,
                "has_or_in_where": False,
                "has_distinct": False,
                "has_union": False,
            },
            "issues": [],
            "suggestions": [],
            "estimated_time_ms": None,
            "has_full_table_scan_risk": "no",
            "missing_where_clause": "no",
        }


# 单例
sql_analyzer = SQLAnalyzer()
