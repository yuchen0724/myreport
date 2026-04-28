# backend/app/utils/query_optimizer.py
import re
from typing import Tuple
from app.utils.sql_validator import SQLValidator


class QueryOptimizer:
    """SQL 查询优化器"""

    @staticmethod
    def optimize_query(sql: str) -> str:
        """优化 SQL 查询"""
        optimized = sql

        # 1. 添加 LIMIT 子句（如果没有）
        if not re.search(r'\bLIMIT\b', optimized, re.IGNORECASE):
            optimized += " LIMIT 100000"

        # 2. 移除不必要的空格
        optimized = re.sub(r'\s+', ' ', optimized)

        # 3. 移除注释
        optimized = re.sub(r'--.*?\n', '\n', optimized)
        optimized = re.sub(r'/\*.*?\*/', '', optimized, flags=re.DOTALL)

        # 4. 标准化关键字
        keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT']
        for keyword in keywords:
            optimized = re.sub(
                rf'\b{keyword}\b',
                keyword,
                optimized,
                flags=re.IGNORECASE
            )

        return optimized.strip()

    @staticmethod
    def validate_query(sql: str) -> Tuple[bool, str]:
        """验证 SQL 查询安全（委托给 SQLValidator）"""
        return SQLValidator.validate(sql)

    @staticmethod
    def estimate_query_cost(sql: str) -> int:
        """估算查询成本（简单实现）"""
        cost = 0

        if 'JOIN' in sql.upper():
            cost += 100
        if 'GROUP BY' in sql.upper():
            cost += 50
        if 'ORDER BY' in sql.upper():
            cost += 30
        if 'HAVING' in sql.upper():
            cost += 20

        from_count = sql.upper().count('FROM')
        cost += from_count * 10

        return cost
