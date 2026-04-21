import re
from typing import List


class SQLValidator:
    """SQL 验证器，防止 SQL 注入和危险操作"""

    # 危险关键字
    DANGER_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER",
        "CREATE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK"
    ]

    @classmethod
    def validate(cls, sql: str) -> tuple[bool, str]:
        """验证 SQL 是否安全"""
        sql_upper = sql.upper()

        # 检查危险关键字
        for keyword in cls.DANGER_KEYWORDS:
            if keyword in sql_upper:
                return False, f"不允许使用 {keyword} 语句"

        # 检查是否以 SELECT 开头
        if not sql_upper.strip().startswith("SELECT"):
            return False, "只允许 SELECT 查询"

        # 检查是否包含注释（防止注释注入）
        if "--" in sql or "/*" in sql or "*/" in sql:
            return False, "不允许使用注释"

        # 检查是否包含分号（防止多语句注入）
        if ";" in sql:
            return False, "不允许使用分号"

        return True, "验证通过"

    @classmethod
    def extract_tables(cls, sql: str) -> List[str]:
        """从 SQL 中提取表名"""
        # 简单实现，实际应该使用 SQL 解析器
        pattern = r"FROM\s+([^\s,]+)|JOIN\s+([^\s,]+)"
        matches = re.findall(pattern, sql.upper(), re.IGNORECASE)
        tables = []
        for match in matches:
            for table in match:
                if table and table not in tables:
                    tables.append(table)
        return tables
