# backend/app/utils/nl2sql_rules.py
from typing import List, Tuple, Optional
import re

class NL2SQLRuleEngine:
    """NL2SQL 规则引擎"""

    # 关键词映射
    KEYWORD_MAP = {
        "查询": "SELECT",
        "选择": "SELECT",
        "显示": "SELECT",
        "获取": "SELECT",
        "统计": "SELECT COUNT",
        "计数": "SELECT COUNT",
        "求和": "SELECT SUM",
        "平均": "SELECT AVG",
        "最大": "SELECT MAX",
        "最小": "SELECT MIN",
        "排序": "ORDER BY",
        "升序": "ASC",
        "降序": "DESC",
        "限制": "LIMIT",
        "前": "LIMIT",
        "条": "",
        "个": "",
        "从": "FROM",
        "在": "FROM",
        "表": "",
        "字段": "",
        "列": "",
        "等于": "=",
        "大于": ">",
        "小于": "<",
        "大于等于": ">=",
        "小于等于": "<=",
        "不等于": "!=",
        "包含": "LIKE",
        "以...开头": "LIKE",
        "以...结尾": "LIKE",
        "在...之间": "BETWEEN",
        "和": "AND",
        "或": "OR",
        "不": "NOT",
        "为": "=",
        "是": "=",
    }

    # 表名提取模式
    TABLE_PATTERNS = [
        r"从\s+(\w+)\s*(?:表)?",
        r"在\s+(\w+)\s*(?:表)?",
        r"(\w+)\s*表",
    ]

    # 字段名提取模式
    COLUMN_PATTERNS = [
        r"(\w+)\s*(?:字段|列)",
        r"显示\s+(\w+)",
        r"查询\s+(\w+)",
    ]

    # 数值提取模式
    NUMBER_PATTERNS = [
        r"(\d+)",
        r"(\d+\.\d+)",
    ]

    @classmethod
    def parse_question(cls, question: str) -> Tuple[str, float]:
        """
        解析自然语言问题，生成 SQL

        Args:
            question: 自然语言问题

        Returns:
            (sql, confidence): 生成的 SQL 和置信度
        """
        question = question.strip()
        sql_parts = []
        confidence = 0.0

        # 1. 提取表名
        table_name = cls._extract_table_name(question)
        if table_name:
            sql_parts.append(f"FROM {table_name}")
            confidence += 0.3

        # 2. 提取字段
        columns = cls._extract_columns(question)
        if columns:
            column_list = ", ".join(columns)
            sql_parts.insert(0, f"SELECT {column_list}")
            confidence += 0.3
        else:
            sql_parts.insert(0, "SELECT *")

        # 3. 提取条件
        conditions = cls._extract_conditions(question)
        if conditions:
            where_clause = " AND ".join(conditions)
            sql_parts.append(f"WHERE {where_clause}")
            confidence += 0.2

        # 4. 提取排序
        order_by = cls._extract_order_by(question)
        if order_by:
            sql_parts.append(order_by)
            confidence += 0.1

        # 5. 提取限制
        limit = cls._extract_limit(question)
        if limit:
            sql_parts.append(limit)
            confidence += 0.1

        sql = " ".join(sql_parts)
        return sql, min(confidence, 1.0)

    @classmethod
    def _extract_table_name(cls, question: str) -> Optional[str]:
        """提取表名"""
        for pattern in cls.TABLE_PATTERNS:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    @classmethod
    def _extract_columns(cls, question: str) -> List[str]:
        """提取字段名"""
        columns = []
        for pattern in cls.COLUMN_PATTERNS:
            matches = re.findall(pattern, question, re.IGNORECASE)
            columns.extend(matches)
        return list(set(columns))

    @classmethod
    def _extract_conditions(cls, question: str) -> List[str]:
        """提取条件"""
        conditions = []
        # 简单实现：提取 "字段 = 值" 模式
        # 实际实现需要更复杂的解析
        return conditions

    @classmethod
    def _extract_order_by(cls, question: str) -> Optional[str]:
        """提取排序"""
        if "排序" in question or "升序" in question or "降序" in question:
            # 简单实现
            return "ORDER BY id DESC"
        return None

    @classmethod
    def _extract_limit(cls, question: str) -> Optional[str]:
        """提取限制"""
        match = re.search(r"前\s*(\d+)", question)
        if match:
            return f"LIMIT {match.group(1)}"
        return None
