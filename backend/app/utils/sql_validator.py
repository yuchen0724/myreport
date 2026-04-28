import re
from typing import List


class SQLValidator:
    """SQL 验证器，防止 SQL 注入和危险操作"""

    # 危险关键字 — 使用 \b 词边界匹配避免误判（如 SELECT * FROM DROP_TABLE）
    DANGER_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER",
        "CREATE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK"
    ]

    # 预编译正则
    _danger_patterns = [
        re.compile(rf"\b{kw}\b", re.IGNORECASE) for kw in DANGER_KEYWORDS
    ]

    @classmethod
    def validate(cls, sql: str) -> tuple[bool, str]:
        """验证 SQL 是否安全

        使用词边界 \b 进行关键字匹配，避免将 'DELETE' 误判在 'DELETE_LOG' 中。
        """
        sql_upper = sql.upper()

        # 检查危险关键字（词边界匹配）
        for kw, pattern in zip(cls.DANGER_KEYWORDS, cls._danger_patterns):
            if pattern.search(sql):
                return False, f"不允许使用 {kw} 语句"

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
        pattern = r"FROM\s+([^\s,]+)|JOIN\s+([^\s,]+)"
        matches = re.findall(pattern, sql, re.IGNORECASE)
        tables = []
        for match in matches:
            for table in match:
                if table and table not in tables:
                    tables.append(table)
        return tables
