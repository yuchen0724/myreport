"""
SQL 方言适配器 — 支持 Hive, Doris, ClickHouse, MySQL, PostgreSQL

每个方言定义：
- name / label: 标识
- description: 方言说明
- allowed_keywords: 允许的额外关键字（在基类白名单之上）
- extra_functions: 允许的额外函数
- extra_injection_patterns: 额外注入检测规则
- disabled_checks: 基类检查中禁用的项（如 Hive 允许分号用于多语句）
- max_sql_length: SQL 最大长度
"""

import re
import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DialectConfig:
    """SQL 方言配置"""
    name: str
    label: str
    description: str
    # 在基类白名单之上的额外允许关键字
    allowed_keywords: List[str] = field(default_factory=list)
    # 额外允许的函数
    extra_functions: List[str] = field(default_factory=list)
    # 额外的注入检测模式
    extra_injection_patterns: List[str] = field(default_factory=list)
    # 从基类中禁用的检查项
    disabled_checks: Set[str] = field(default_factory=set)
    # SQL 最大长度（None 表示使用基类默认值）
    max_sql_length: Optional[int] = None
    # 是否允许多语句（分号分隔）
    allow_multistatement: bool = False
    # 是否以 SELECT / WITH 开头的限制
    require_select_start: bool = True
    # 反引号作为标识符包裹符（MySQL/Doris）
    backtick_quoted: bool = False
    # 双引号作为标识符包裹符（PostgreSQL/ClickHouse）
    double_quote_quoted: bool = False
    # 方言特定的注释注入检测
    comment_injection_patterns: List[str] = field(default_factory=list)


# ============================================================
# 预定义方言
# ============================================================

DIALECTS: List[DialectConfig] = [
    # ---------- MySQL ----------
    DialectConfig(
        name="mysql",
        label="MySQL",
        description="MySQL 方言，支持反引号标识符、条件注释 /*！...*/ 等",
        allowed_keywords=[
            "IFNULL", "IF", "LIMIT", "AUTO_INCREMENT",
            "ENGINE", "CHARSET", "COLLATE", "FORCE", "INDEX",
        ],
        extra_functions=[
            "IFNULL", "DATE_FORMAT", "STR_TO_DATE", "UNIX_TIMESTAMP",
            "FROM_UNIXTIME", "NOW", "CURDATE", "CURTIME",
            "GROUP_CONCAT", "FIND_IN_SET", "ELT", "FIELD",
            "SUBSTRING_INDEX", "LPAD", "RPAD",
        ],
        backtick_quoted=True,
        comment_injection_patterns=[
            r"/\*!\d+",  # MySQL 条件注释
        ],
    ),

    # ---------- PostgreSQL ----------
    DialectConfig(
        name="postgresql",
        label="PostgreSQL",
        description="PostgreSQL 方言，支持双引号标识符、数组操作、窗口函数等",
        allowed_keywords=[
            "ILIKE", "SIMILAR", "ANY", "ALL", "SOME",
            "CONFLICT", "RETURNING", "ON", "LATERAL",
            "GENERATED", "IDENTITY", "WINDOW", "OVER",
            "PARTITION", "RANGE", "ROWS", "GROUPS",
        ],
        extra_functions=[
            "EXTRACT", "TO_CHAR", "TO_DATE", "TO_NUMBER",
            "AGE", "DATE_TRUNC", "NOW", "CURRENT_TIMESTAMP",
            "STRING_AGG", "ARRAY_AGG", "JSON_AGG",
            "COALESCE", "NULLIF", "GREATEST", "LEAST",
            "REGEXP_REPLACE", "REGEXP_MATCHES",
            "UNNEST", "GENERATE_SERIES", "WITH ORDINALITY",
        ],
        double_quote_quoted=True,
        # PostgreSQL 允许 WITH RECURSIVE CTE
        extra_injection_patterns=[
            # PostgreSQL 的注入风险模式
        ],
        comment_injection_patterns=[],
    ),

    # ---------- Hive ----------
    DialectConfig(
        name="hive",
        label="Apache Hive",
        description="Hive SQL 方言，支持 LATERAL VIEW、EXPLODE、分区表语法等",
        allowed_keywords=[
            "LATERAL", "VIEW", "EXPLODE", "LATERAL_VIEW",
            "PARTITION", "PARTITIONED", "OVERWRITE",
            "CLUSTERED", "SORTED", "BUCKETED",
            "TBLPROPERTIES", "STORED", "AS", "ORC", "PARQUET",
            "TEXTFILE", "SEQUENCEFILE", "RCFILE",
            "DISTRIBUTE", "SORT", "MAP", "REDUCE",
            "SET", "RESET",
        ],
        extra_functions=[
            "EXPLODE", "PARSE_URL", "URL_EXTRACT",
            "GET_JSON_OBJECT", "JSON_TUPLE", "LATERAL_VIEW",
            "COALESCE", "NVL", "IF", "CASE",
            "UNIX_TIMESTAMP", "FROM_UNIXTIME",
            "DATE_FORMAT", "DATE_ADD", "DATE_SUB",
            "TO_DATE", "YEAR", "MONTH", "DAY",
            "REGEXP_EXTRACT", "REGEXP_REPLACE",
            "SIZE", "MAP_KEYS", "MAP_VALUES",
            "ARRAY", "STRUCT", "CREATE_TUPLE",
        ],
        # Hive 允许多语句（SET 语句 + SELECT）
        allow_multistatement=True,
        disabled_checks={"semicolon"},  # 禁用分号检查
        backtick_quoted=True,
        comment_injection_patterns=[],
    ),

    # ---------- Doris (Apache Doris / StarRocks) ----------
    DialectConfig(
        name="doris",
        label="Apache Doris",
        description="Apache Doris / StarRocks 方言，兼容 MySQL 协议，支持物化视图、Bitmap 等",
        allowed_keywords=[
            "IFNULL", "IF", "LIMIT", "AUTO_INCREMENT",
            "ENGINE", "DUPLICATE", "AGGREGATE", "UNIQUE",
            "KEY", "VALUE", "DISTRIBUTED", "BUCKETS",
            "PROPERTIES", "ROLLUP", "MATERIALIZED",
            "BROKER", "S3", "HDFS", "HIVE",
            "bitmap", "hll",
        ],
        extra_functions=[
            "IFNULL", "DATE_FORMAT", "STR_TO_DATE",
            "NOW", "CURDATE", "UNIX_TIMESTAMP",
            "FROM_UNIXTIME", "GROUP_CONCAT",
            "COUNT_IF", "SUM_IF", "IF", "IFNULL",
            "HLL_UNION", "BITMAP_UNION", "TO_BITMAP",
            "BITMAP_COUNT", "BITMAP_CONTAINS",
        ],
        backtick_quoted=True,
        comment_injection_patterns=[
            r"/\*!\d+",  # Doris 继承 MySQL 条件注释
        ],
    ),

    # ---------- ClickHouse ----------
    DialectConfig(
        name="clickhouse",
        label="ClickHouse",
        description="ClickHouse 方言，支持 MergeTree 引擎、数组/元组操作、特殊聚合函数等",
        allowed_keywords=[
            "FINAL", "PREWHERE", "SAMPLE", "SETTINGS",
            "ENGINE", "MergeTree", "ReplacingMergeTree",
            "SummingMergeTree", "AggregatingMergeTree",
            "ORDER", "PARTITION", "INDEX", "TTL",
            "CODEC", "GRANULARITY",
        ],
        extra_functions=[
            "arrayMap", "arrayFilter", "arrayJoin",
            "groupArray", "groupUniqArray",
            "uniq", "uniqExact", "avgWeighted",
            "quantile", "quantileExact",
            "topK", "topKWeighted",
            "dateDiff", "formatDateTime", "toYYYYMM",
            "toStartOfMonth", "toStartOfDay",
            "if", "multiIf", "coalesce",
            "substring", "length", "position",
            "splitByChar", "splitByString",
            "replaceOne", "replaceAll",
            "reinterpret", "cast", "toType",
            "blockNumber", "rowNumberInAllBlocks",
            "neighbor", "runningDifference",
        ],
        double_quote_quoted=True,
        # ClickHouse 允许分号分隔的多语句
        allow_multistatement=True,
        disabled_checks={"semicolon"},
        comment_injection_patterns=[],
    ),
]

# 按 name 建立快速查找表
DIALECT_MAP: Dict[str, DialectConfig] = {d.name: d for d in DIALECTS}

# 基类默认值
DEFAULT_MAX_SQL_LENGTH = 50000


class DialectAwareValidator:
    """方言感知的 SQL 验证器"""

    # 基类危险关键字 — 与原 SQLValidator 保持一致
    BASE_DANGER_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER",
        "CREATE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK", "EXEC", "EXECUTE",
        "RENAME", "ANALYZE", "EXPLAIN", "SHOW", "SET",
        "LOAD DATA", "REPLACE", "CALL", "DO", "HANDLER",
        "FLUSH", "INSTALL", "UNINSTALL", "KILL", "LOCK", "UNLOCK",
        "PURGE", "RESET", "SHUTDOWN", "XA", "PREPARE", "DEALLOCATE",
    ]

    # 基类危险函数
    BASE_DANGER_FUNCTIONS = [
        "LOAD_FILE", "INTO OUTFILE", "INTO DUMPFILE", "BENCHMARK",
        "SLEEP", "WAITFOR", "DELAY", "UUID", "VERSION", "DATABASE",
        "USER", "CURRENT_USER", "LOAD_CONCATENATED_FILE", "READFILE",
        "CHAR", "CONCAT", "GROUP_CONCAT", "INFORMATION_SCHEMA",
    ]

    # 基类注入模式
    BASE_INJECTION_PATTERNS = [
        r"OR\s+1\s*=\s*1",
        r"OR\s+'[^']*'\s*=\s*'[^']*'",
        r"OR\s+\d+\s*=\s*\d+",
        r'OR\s+"[^"]*"\s*=\s*"[^"]*"',
        r"OR\s+TRUE\b",
        r"--\s*\w+",
        r"#\s*\w+",
        r"EXEC\s*\(",
        r"0x[0-9a-fA-F]{4,}",
        r";\s*DROP",
        r";\s*DELETE",
        r";\s*UPDATE",
        r";\s*INSERT",
        r";\s*TRUNCATE",
        r";\s*ALTER",
        r";\s*CREATE",
        r"/\*!\d*",
        r";\s*\bUNION\s+ALL\s+SELECT\b",  # 仅在分号后匹配 UNION ALL SELECT（多语句注入）
    ]

    # 基类允许的关键字
    BASE_ALLOWED_KEYWORDS = [
        "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "BETWEEN",
        "LIKE", "IS", "NULL", "ORDER", "BY", "ASC", "DESC", "LIMIT",
        "OFFSET", "GROUP", "HAVING", "JOIN", "LEFT", "RIGHT", "INNER",
        "OUTER", "FULL", "CROSS", "ON", "AS", "DISTINCT", "ALL",
        "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END", "UNION",
        "INTERSECT", "EXCEPT", "WITH", "RECURSIVE",
    ]

    @classmethod
    def validate(cls, sql: str, dialect_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        验证 SQL 是否安全（方言感知）

        Args:
            sql: 待验证的 SQL 语句
            dialect_name: 方言名称，None 或 "auto" 使用默认规则

        Returns:
            (is_valid, message)
        """
        if not sql or not sql.strip():
            return False, "SQL 不能为空"

        # 获取方言配置
        dialect = DIALECT_MAP.get(dialect_name) if dialect_name else None

        # 长度限制
        max_len = cls._get_max_sql_length(dialect)
        if len(sql) > max_len:
            return False, f"SQL 语句过长（最大 {max_len} 字符）"

        sql_upper = sql.upper().strip()

        # 1. 检查危险关键字
        danger_keywords = cls._get_danger_keywords(dialect)
        danger_patterns = [
            re.compile(rf"\b{kw}\b", re.IGNORECASE) for kw in danger_keywords
        ]
        for kw, pattern in zip(danger_keywords, danger_patterns):
            # SET 在 Hive 方言中是允许的
            if dialect and "SET" in dialect.disabled_checks and kw == "SET":
                continue
            if pattern.search(sql):
                return False, f"不允许使用 {kw} 语句"

        # 2. 检查危险函数
        danger_functions = cls._get_danger_functions(dialect)
        danger_func_patterns = [
            re.compile(rf"\b{func}\b", re.IGNORECASE) for func in danger_functions
        ]
        for func, pattern in zip(danger_functions, danger_func_patterns):
            if pattern.search(sql_upper):
                return False, f"不允许使用函数 {func}"

        # 3. 检查注入模式
        injection_patterns = cls._get_injection_patterns(dialect)
        injection_compiled = [
            re.compile(pattern, re.IGNORECASE) for pattern in injection_patterns
        ]
        for pattern in injection_compiled:
            if pattern.search(sql):
                return False, "检测到可能的 SQL 注入攻击"

        # 4. 检查是否以 SELECT / WITH 开头
        if dialect and not dialect.require_select_start:
            pass  # 方言不要求
        else:
            if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
                return False, "只允许 SELECT 查询"

        # 5. 检查分号
        if ";" in sql:
            if dialect and dialect.allow_multistatement:
                # 多语句模式：只检查最后是否以分号结尾导致空语句
                # 但仍然阻止 DROP; SELECT 这种危险模式
                pass
            else:
                return False, "不允许使用分号"

        # 6. 检查括号匹配
        if sql.count("(") != sql.count(")"):
            return False, "括号不匹配"

        return True, "验证通过"

    @classmethod
    def _get_max_sql_length(cls, dialect: Optional[DialectConfig]) -> int:
        if dialect and dialect.max_sql_length is not None:
            return dialect.max_sql_length
        return DEFAULT_MAX_SQL_LENGTH

    @classmethod
    def _get_danger_keywords(cls, dialect: Optional[DialectConfig]) -> List[str]:
        """获取危险关键字列表（不排除方言允许的项）"""
        return cls.BASE_DANGER_KEYWORDS[:]

    @classmethod
    def _get_danger_functions(cls, dialect: Optional[DialectConfig]) -> List[str]:
        """获取危险函数列表"""
        return cls.BASE_DANGER_FUNCTIONS[:]

    @classmethod
    def _get_injection_patterns(cls, dialect: Optional[DialectConfig]) -> List[str]:
        """获取注入检测模式（含方言扩展）"""
        patterns = cls.BASE_INJECTION_PATTERNS[:]
        if dialect:
            patterns.extend(dialect.extra_injection_patterns)
        return patterns

    @classmethod
    def get_allowed_keywords(cls, dialect_name: Optional[str] = None) -> List[str]:
        """获取允许的关键字列表（基类 + 方言扩展）"""
        keywords = cls.BASE_ALLOWED_KEYWORDS[:]
        dialect = DIALECT_MAP.get(dialect_name) if dialect_name else None
        if dialect:
            keywords.extend(dialect.allowed_keywords)
        return sorted(set(keywords))

    @classmethod
    def get_allowed_functions(cls, dialect_name: Optional[str] = None) -> List[str]:
        """获取允许的函数列表（仅方言扩展）"""
        dialect = DIALECT_MAP.get(dialect_name) if dialect_name else None
        if dialect:
            return list(dialect.extra_functions)
        return []


def list_dialects() -> List[Dict]:
    """返回所有方言的概要信息（用于 API 响应）"""
    return [
        {
            "name": d.name,
            "label": d.label,
            "description": d.description,
        }
        for d in DIALECTS
    ]


def get_dialect(name: str) -> Optional[Dict]:
    """获取单个方言的详细信息"""
    d = DIALECT_MAP.get(name)
    if not d:
        return None
    return {
        "name": d.name,
        "label": d.label,
        "description": d.description,
        "allowed_keywords": d.allowed_keywords,
        "extra_functions": d.extra_functions,
        "allow_multistatement": d.allow_multistatement,
        "backtick_quoted": d.backtick_quoted,
        "double_quote_quoted": d.double_quote_quoted,
        "require_select_start": d.require_select_start,
    }
