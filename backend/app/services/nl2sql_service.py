# backend/app/services/nl2sql_service.py
from typing import List, Dict, Any, Optional
from app.schemas.nl2sql import NL2SQLRequest, NL2SQLResponse, SQLSuggestion
from app.utils.nl2sql_rules import NL2SQLRuleEngine
from app.services.query_service import QueryService
from app.schemas.query import SQLQueryRequest

class NL2SQLService:
    """NL2SQL 服务"""

    def __init__(self, query_service: QueryService):
        self.query_service = query_service
        self.rule_engine = NL2SQLRuleEngine()

    def parse_question(self, request: NL2SQLRequest, user_id: int) -> NL2SQLResponse:
        """
        解析自然语言问题并执行查询

        Args:
            request: NL2SQL 请求
            user_id: 用户 ID

        Returns:
            NL2SQL 响应
        """
        # 1. 使用规则引擎生成 SQL
        sql, confidence = self.rule_engine.parse_question(request.question)

        # 2. 创建 SQL 建议
        suggestion = SQLSuggestion(
            sql=sql,
            confidence=confidence,
            explanation=f"基于规则引擎生成，置信度：{confidence:.2%}"
        )

        # 3. 执行查询
        query_request = SQLQueryRequest(
            data_source_id=request.data_source_id,
            sql=sql,
            params={}
        )

        try:
            result = self.query_service.execute_sql(query_request, user_id)

            return NL2SQLResponse(
                suggestions=[suggestion],
                selected_sql=sql,
                query_result={
                    "columns": result.columns,
                    "rows": result.rows,
                    "total": result.total
                },
                execution_time_ms=result.execution_time_ms
            )
        except Exception as e:
            # 查询失败，返回建议但不返回结果
            return NL2SQLResponse(
                suggestions=[suggestion],
                selected_sql=sql,
                query_result=None,
                execution_time_ms=None
            )

    def validate_sql(self, sql: str) -> bool:
        """
        验证 SQL 语法

        Args:
            sql: SQL 语句

        Returns:
            是否有效
        """
        # 简单实现：检查危险关键字
        danger_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"]
        sql_upper = sql.upper()
        for keyword in danger_keywords:
            if keyword in sql_upper:
                return False
        return True
