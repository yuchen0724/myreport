import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class SQLValidator:
    """SQL 验证器，防止 SQL 注入和危险操作"""

    # 危险关键字 — 使用 \b 词边界匹配避免误判
    DANGER_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER",
        "CREATE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK", "EXEC", "EXECUTE",
        # 新增：之前遗漏的危险语句
        "RENAME", "ANALYZE", "EXPLAIN", "SHOW", "SET",
        "LOAD DATA", "CALL", "DO", "HANDLER",
        "FLUSH", "INSTALL", "UNINSTALL", "KILL", "LOCK", "UNLOCK",
        "PURGE", "RESET", "SHUTDOWN", "XA", "PREPARE", "DEALLOCATE",
    ]

    # 仅禁止会产生“写入语义”的 REPLACE 形式，而放行 REPLACE() 函数。
    # 以常见的写入语法 REPLACE INTO 为准；同时保留对 REPLACE TABLE 的防御。
    _danger_replace_patterns = [
        re.compile(r"\bREPLACE\s+INTO\b", re.IGNORECASE),
        re.compile(r"\bREPLACE\s+TABLE\b", re.IGNORECASE),
    ]

    # 危险函数（可能用于信息泄露或攻击）
    DANGER_FUNCTIONS = [
        "LOAD_FILE", "INTO OUTFILE", "INTO DUMPFILE", "BENCHMARK",
        "SLEEP", "WAITFOR", "DELAY", "UUID", "VERSION", "DATABASE",
        "USER", "CURRENT_USER", "LOAD_CONCATENATED_FILE", "READFILE",
        # 新增
        "CONCAT", "GROUP_CONCAT",
    ]

    # 常见注入模式
    INJECTION_PATTERNS = [
        r"OR\s+1\s*=\s*1",                # OR 1=1 永真式
        r"OR\s+'[^']*'\s*=\s*'[^']*'",   # OR ''='' 永真式
        r"OR\s+\d+\s*=\s*\d+",           # OR 1=1 数字
        r'OR\s+"[^"]*"\s*=\s*"[^"]*"',   # OR ""="" 双引号
        r"OR\s+TRUE\b",                   # OR TRUE
        r"--\s*\w+",                      # 行尾注释注入（-- 后有内容）
        r"#\s*\w+",                       # MySQL 注释注入
        r"EXEC\s*\(",                     # 存储过程注入
        r"0x[0-9a-fA-F]{4,}",            # 十六进制编码注入（4位以上）
        r";\s*DROP",                      # 多语句 DROP
        r";\s*DELETE",                    # 多语句 DELETE
        r";\s*UPDATE",                    # 多语句 UPDATE
        r";\s*INSERT",                    # 多语句 INSERT
        r";\s*TRUNCATE",                  # 多语句 TRUNCATE
        r";\s*ALTER",                     # 多语句 ALTER
        r";\s*CREATE",                    # 多语句 CREATE
        r"/\*!\d*",                       # MySQL 条件注释 /*! ... */
        r"\bUNION\s+ALL\s+SELECT\b",      # UNION ALL SELECT 注入
    ]

    # SQL 最大长度限制
    MAX_SQL_LENGTH = 50000  # 50KB

    # 预编译正则
    _danger_patterns = [
        re.compile(rf"\b{kw}\b", re.IGNORECASE) for kw in DANGER_KEYWORDS
    ]
    _danger_func_patterns = [
        re.compile(rf"\b{func}\b", re.IGNORECASE) for func in DANGER_FUNCTIONS
    ]
    _injection_patterns = [
        re.compile(pattern, re.IGNORECASE) for pattern in INJECTION_PATTERNS
    ]

    # 允许的 SQL 关键字（白名单）
    ALLOWED_KEYWORDS = [
        "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "BETWEEN",
        "LIKE", "IS", "NULL", "ORDER", "BY", "ASC", "DESC", "LIMIT",
        "OFFSET", "GROUP", "HAVING", "JOIN", "LEFT", "RIGHT", "INNER",
        "OUTER", "FULL", "CROSS", "ON", "AS", "DISTINCT", "ALL",
        "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END", "UNION",
        "INTERSECT", "EXCEPT", "WITH", "RECURSIVE"
    ]

    @classmethod
    def validate(cls, sql: str) -> Tuple[bool, str]:
        """验证 SQL 是否安全

        使用词边界 \b 进行关键字匹配，避免误判。
        """
        if not sql or not sql.strip():
            return False, "SQL 不能为空"

        # 0. 长度检查（放在最前面，防止过长的恶意查询消耗资源）
        if len(sql) > cls.MAX_SQL_LENGTH:
            return False, f"SQL 语句过长（最大 {cls.MAX_SQL_LENGTH} 字符）"

        sql_upper = sql.upper().strip()

        # 1. 检查危险关键字
        for kw, pattern in zip(cls.DANGER_KEYWORDS, cls._danger_patterns):
            if pattern.search(sql):
                return False, f"不允许使用 {kw} 语句"

        # 1.5 检查 REPLACE 写入语义（避免误伤 replace() 函数）
        for p in cls._danger_replace_patterns:
            if p.search(sql):
                return False, "不允许使用 REPLACE 写入语句"

        # 2. 检查危险函数
        for func, pattern in zip(cls.DANGER_FUNCTIONS, cls._danger_func_patterns):
            if pattern.search(sql_upper):
                return False, f"不允许使用函数 {func}"

        # 3. 检查常见注入模式
        for pattern in cls._injection_patterns:
            if pattern.search(sql):
                return False, "检测到可能的 SQL 注入攻击"

        # 4. 检查是否以 SELECT 开头（或 WITH 公共表表达式）
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            return False, "只允许 SELECT 查询"

        # 5. 检查是否包含分号（防止多语句注入）
        if ";" in sql:
            return False, "不允许使用分号"

        # 6. 检查括号匹配（防止语法错误）
        if sql.count("(") != sql.count(")"):
            return False, "括号不匹配"

        return True, "验证通过"


# 辅助函数：生成安全的 LIMIT/OFFSET
def safe_limit_offset(page: int, page_size: int, max_page_size: int = 1000) -> Tuple[int, int]:
    """生成安全的分页参数"""
    page = max(1, page)
    page_size = min(max(1, page_size), max_page_size)
    offset = (page - 1) * page_size
    return offset, page_size

# 辅助函数：校验列名是否安全
def safe_column_name(col: str, max_length: int = 64) -> bool:
    """校验列名是否安全

    Args:
        col: 列名
        max_length: 最大长度

    Returns:
        True 如果列名安全
    """
    if not col or len(col) > max_length:
        return False
    if not col.isidentifier():
        return False
    # 额外检查：不能包含 SQL 关键字特征
    col_upper = col.upper()
    if col_upper in ("SELECT", "FROM", "WHERE", "DROP", "DELETE", "UPDATE", "INSERT"):
        return False
    return True
