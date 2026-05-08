import re
from typing import List, Tuple


class SQLValidator:
    """SQL 验证器，防止 SQL 注入和危险操作"""

    # 危险关键字 — 使用 \b 词边界匹配避免误判
    DANGER_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER",
        "CREATE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK", "EXEC", "EXECUTE"
    ]
    
    # 危险函数（可能用于信息泄露或攻击）
    DANGER_FUNCTIONS = [
        "LOAD_FILE", "INTO OUTFILE", "INTO DUMPFILE", "BENCHMARK", 
        "SLEEP", "WAITFOR", "DELAY", "UUID", "VERSION", "DATABASE",
        "USER", "CURRENT_USER", "LOAD_CONCATENATED_FILE", "READFILE"
    ]

    # 常见注入模式
    INJECTION_PATTERNS = [
        r"OR\s+1\s*=\s*1",           # OR 1=1
        r"OR\s+'[^']*'\s*=\s*'[^']*'",  # OR ''=''
        r"OR\s+\d+\s*=\s*\d+",        # OR 1=1 数字
        r"UNION\s+SELECT",            # UNION 注入
        r"UNION\s+ALL\s+SELECT",      # UNION ALL 注入
        r"-\s*-",                     # SQL 注释注入
        r"#\s*\w+",                  # MySQL 注释注入
        r"/\*.*\*/",                 # 注释块注入
        r"EXEC\s*\(",                 # 存储过程注入
        r"0x[0-9a-fA-F]+",           # 十六进制编码注入
    ]

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
        
        sql_upper = sql.upper()
        
        # 1. 检查危险关键字
        for kw, pattern in zip(cls.DANGER_KEYWORDS, cls._danger_patterns):
            if pattern.search(sql):
                return False, f"不允许使用 {kw} 语句"
        
        # 2. 检查危险函数
        for func, pattern in zip(cls.DANGER_FUNCTIONS, cls._danger_func_patterns):
            if pattern.search(sql_upper):
                return False, f"不允许使用函数 {func}"
        
        # 3. 检查常见注入模式
        for pattern in cls._injection_patterns:
            if pattern.search(sql):
                return False, "检测到可能的 SQL 注入攻击"
        
        # 4. 检查是否以 SELECT 开头（或 WITH 公共表表达式）
        if not sql_upper.strip().startswith("SELECT") and not sql_upper.strip().startswith("WITH"):
            return False, "只允许 SELECT 查询"
        
        # 5. 检查是否包含注释（防止注释注入）
        if "--" in sql or "/*" in sql or "*/" in sql:
            return False, "不允许使用注释"
        
        # 6. 检查是否包含分号（防止多语句注入）
        if ";" in sql:
            return False, "不允许使用分号"
        
        # 7. 检查括号匹配（防止语法错误）
        if sql.count("(") != sql.count(")"):
            return False, "括号不匹配"
        
        # 8. 检查 SQL 长度（防止过长的恶意查询）
        if len(sql) > 10000:
            return False, "SQL 语句过长"
        
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
    
    @classmethod
    def validate_where_clause(cls, where: str) -> Tuple[bool, str]:
        """验证 WHERE 子句（更严格的检查）"""
        # 检查等号两边是否有数字或字符串直接比较
        if re.search(r"\d+\s*=\s*\d+", where):
            return False, "不允许数字直接比较"
        
        # 检查是否有危险的比较
        if re.search(r"['\"]\s*=\s*['\"]", where):
            return False, "不允许空字符串比较"
        
        return True, "验证通过"