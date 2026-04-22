# backend/app/utils/query_optimizer.py
import re
from typing import List, Tuple

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
        """验证 SQL 查询"""
        # 检查是否包含危险操作
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', sql, re.IGNORECASE):
                return False, f"不允许使用 {keyword} 操作"

        # 检查是否包含注释
        if '--' in sql or '/*' in sql:
            return False, "不允许使用 SQL 注释"

        # 检查是否包含分号（防止多语句）
        if ';' in sql:
            return False, "不允许使用多语句"

        return True, "验证通过"

    @staticmethod
    def estimate_query_cost(sql: str) -> int:
        """估算查询成本（简单实现）"""
        cost = 0

        # 根据关键字估算
        if 'JOIN' in sql.upper():
            cost += 100
        if 'GROUP BY' in sql.upper():
            cost += 50
        if 'ORDER BY' in sql.upper():
            cost += 30
        if 'HAVING' in sql.upper():
            cost += 20

        # 根据表数量估算
        from_count = sql.upper().count('FROM')
        cost += from_count * 10

        return cost
