# backend/app/services/nl2sql_service.py
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.schemas.nl2sql import NL2SQLRequest, NL2SQLResponse, SQLSuggestion
from app.utils.nl2sql_rules import NL2SQLRuleEngine
from app.utils.llm_client import LLMClient, LLMError, get_llm_client
from app.utils.sql_validator import SQLValidator
from app.services.query_service import QueryService
from app.schemas.query import SQLQueryRequest
from app.repositories.data_source_repository import DataSourceRepository
from app.core.security import decrypt_password

logger = logging.getLogger(__name__)


class NL2SQLService:
    """NL2SQL 服务 - 集成 LLM 和规则引擎"""

    def __init__(self, query_service: QueryService, db: Session = None):
        self.query_service = query_service
        self.rule_engine = NL2SQLRuleEngine()
        self.db = db
        self.ds_repo = DataSourceRepository(db) if db else None
        self.llm_client: Optional[LLMClient] = None

    def _get_llm_client(self) -> LLMClient:
        """获取 LLM 客户端（惰性初始化）"""
        if self.llm_client is None:
            self.llm_client = get_llm_client()
        return self.llm_client

    def parse_question(self, request: NL2SQLRequest, user_id: int) -> NL2SQLResponse:
        """
        解析自然语言问题并执行查询

        Args:
            request: NL2SQL 请求
            user_id: 用户 ID

        Returns:
            NL2SQL 响应
        """
        sql = None
        confidence = 0.0
        explanation = ""
        used_llm = False

        # 1. 尝试使用 LLM 生成 SQL
        try:
            llm_client = self._get_llm_client()
            sql, confidence, explanation = self._generate_sql_with_llm(
                llm_client, request.question, request.data_source_id
            )
            used_llm = True
            logger.info(f"LLM 生成 SQL 成功: {sql[:100]}...")
        except LLMError as e:
            logger.warning(f"LLM 调用失败: {e}，回退到规则引擎")
        except Exception as e:
            logger.warning(f"LLM 生成 SQL 失败: {e}，回退到规则引擎")

        # 2. LLM 失败时，使用规则引擎作为 fallback
        if not sql:
            sql, confidence = self.rule_engine.parse_question(request.question)
            explanation = f"基于规则引擎生成，置信度：{confidence:.2%}"
            logger.info(f"规则引擎生成 SQL: {sql}")

        # 3. 验证 SQL 安全性
        is_valid, validation_msg = SQLValidator.validate(sql)
        if not is_valid:
            logger.error(f"SQL 验证失败: {validation_msg}")
            return NL2SQLResponse(
                suggestions=[
                    SQLSuggestion(
                        sql=sql,
                        confidence=confidence,
                        explanation=f"SQL 验证失败: {validation_msg}"
                    )
                ],
                selected_sql=sql,
                query_result=None,
                execution_time_ms=None
            )

        # 4. 创建 SQL 建议
        suggestion = SQLSuggestion(
            sql=sql,
            confidence=confidence,
            explanation=explanation
        )

        # 5. 执行查询
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
            error_msg = str(e) if str(e) else f"{type(e).__name__}"
            logger.error(f"查询执行失败: {error_msg}")
            return NL2SQLResponse(
                suggestions=[suggestion],
                selected_sql=sql,
                query_result=None,
                execution_time_ms=None
            )

    def _generate_sql_with_llm(
        self, llm_client: LLMClient, question: str, data_source_id: int
    ) -> Tuple[str, float, str]:
        """
        使用 LLM 生成 SQL

        Args:
            llm_client: LLM 客户端
            question: 自然语言问题
            data_source_id: 数据源 ID

        Returns:
            (sql, confidence, explanation): 生成的 SQL、置信度和解释
        """
        # 1. 构建 schema prompt
        schema_prompt = self.build_schema_prompt(data_source_id)

        # 2. 构建系统提示词
        system_prompt = f"""你是一个数据分析专家，擅长将自然语言问题转换为 SQL 查询。

## 数据源信息
{schema_prompt}

## 规则
1. 只生成 SELECT 查询，禁止生成 UPDATE/DELETE/DROP 等操作
2. 使用精确的表名和列名
3. 条件要准确匹配问题中的语义
4. 日期格式使用 YYYYMMDD（如 20260508）
5. 必须包含 ORDER BY 子句以支持分页
6. 不要使用 SQL 注释（-- 或 /* */）
7. 不要在 SQL 末尾添加分号

## 输出格式
请返回以下 JSON 格式（不要添加任何其他文字）：
{{
  "sql": "生成的 SQL 语句",
  "confidence": 0.0-1.0,
  "explanation": "SQL 生成逻辑的简要说明"
}}
"""

        # 3. 调用 LLM
        logger.info(f"LLM 开始生成 SQL, question={question[:30]}, client_timeout={llm_client.timeout}")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"问题: {question}"}
        ]
        
        logger.info(f"LLM messages prepared, system_prompt length={len(system_prompt)}")
        
        response = llm_client.chat(messages, temperature=0.0)
        
        logger.info(f"LLM response received, length={len(response)}")

        # 4. 解析 JSON 响应
        result = self._parse_llm_response(response)

        if not result:
            raise ValueError("无法解析 LLM 响应")

        sql = result.get("sql", "").strip()
        confidence = float(result.get("confidence", 0.0))
        explanation = result.get("explanation", "")

        if not sql:
            raise ValueError("LLM 未返回有效的 SQL")

        return sql, confidence, explanation

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析 LLM 响应，提取 JSON

        Args:
            response: LLM 原始响应

        Returns:
            解析后的字典，失败返回 None
        """
        if not response:
            return None

        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块
        import re

        # 尝试匹配 ```json ... ``` 格式
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试匹配 { ... } 格式
        brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def build_schema_prompt(self, data_source_id: int) -> str:
        """
        构建 Schema 描述 prompt

        通过数据源 ID 获取连接信息，查询表结构，生成结构化的 schema 描述

        Args:
            data_source_id: 数据源 ID

        Returns:
            Schema 描述字符串
        """
        if not self.ds_repo:
            return "数据源信息不可用"

        # 获取数据源信息
        ds = self.ds_repo.get_by_id(data_source_id)
        if not ds:
            return f"数据源 ID {data_source_id} 不存在"

        # 连接数据源获取表结构
        try:
            tables_info = self._fetch_schema_from_datasource(ds)
            if not tables_info:
                return f"数据源: {ds.name} ({ds.type})\n表结构信息不可用"

            # 构建格式化的 schema 描述
            prompt_parts = [
                f"数据源: {ds.name} ({ds.type})",
                f"数据库: {ds.database}",
                "",
                "## 表结构信息",
                ""
            ]

            for table_name, columns in tables_info.items():
                prompt_parts.append(f"### 表: {table_name}")
                prompt_parts.append("| 列名 | 类型 | 是否为空 | 键 | 默认值 | 注释 |")
                prompt_parts.append("|------|------|----------|-----|--------|------|")

                for col in columns:
                    col_name = col.get("name", "")
                    col_type = col.get("type", "")
                    is_nullable = col.get("nullable", "YES")
                    key = col.get("key", "")
                    default = col.get("default", "")
                    comment = col.get("comment", "")

                    prompt_parts.append(
                        f"| {col_name} | {col_type} | {is_nullable} | {key} | {default} | {comment} |"
                    )

                prompt_parts.append("")

            return "\n".join(prompt_parts)

        except Exception as e:
            logger.error(f"获取数据源 Schema 失败: {e}")
            return f"数据源: {ds.name} ({ds.type})\n获取表结构失败: {str(e)}"

    def _fetch_schema_from_datasource(self, ds) -> Dict[str, List[Dict[str, Any]]]:
        """
        从数据源获取表结构

        Args:
            ds: 数据源模型对象

        Returns:
            {表名: [列信息字典]} 格式的字典
        """
        import pymysql
        import psycopg2
        from sqlalchemy import create_engine, text

        # 解密密码
        password = decrypt_password(ds.password_encrypted)

        # 构建连接 URL（使用解密后的密码）
        if ds.type == "MYSQL":
            conn_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        elif ds.type == "POSTGRESQL":
            conn_url = f"postgresql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        elif ds.type == "DORIS":
            # Doris 使用 MySQL 协议
            conn_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        else:
            raise ValueError(f"不支持的数据源类型: {ds.type}")

        engine = create_engine(conn_url, pool_pre_ping=True)

        tables_info = {}

        try:
            with engine.connect() as conn:
                # 获取表列表
                if ds.type in ["MYSQL", "DORIS"]:
                    tables_result = conn.execute(text("SHOW TABLES"))
                    table_names = [row[0] for row in tables_result.fetchall()]

                    # 获取每个表的列信息
                    for table_name in table_names[:50]:  # 限制最多 50 个表
                        try:
                            desc_result = conn.execute(text(f"DESCRIBE `{table_name}`"))
                            columns = []
                            for row in desc_result.fetchall():
                                columns.append({
                                    "name": row[0],
                                    "type": row[1],
                                    "nullable": row[2],
                                    "key": row[3] if len(row) > 3 else "",
                                    "default": str(row[4]) if len(row) > 4 and row[4] is not None else "",
                                    "comment": row[5] if len(row) > 5 else ""
                                })
                            tables_info[table_name] = columns
                        except Exception as e:
                            logger.warning(f"获取表 {table_name} 结构失败: {e}")
                            continue

                elif ds.type == "POSTGRESQL":
                    # PostgreSQL 使用 information_schema
                    tables_result = conn.execute(text("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """))
                    table_names = [row[0] for row in tables_result.fetchall()]

                    for table_name in table_names[:50]:
                        try:
                            desc_result = conn.execute(text(f"""
                                SELECT 
                                    column_name,
                                    data_type,
                                    is_nullable,
                                    column_default
                                FROM information_schema.columns
                                WHERE table_schema = 'public' AND table_name = :table_name
                                ORDER BY ordinal_position
                            """), {"table_name": table_name})

                            columns = []
                            for row in desc_result.fetchall():
                                columns.append({
                                    "name": row[0],
                                    "type": row[1],
                                    "nullable": row[2],
                                    "key": "",
                                    "default": str(row[3]) if row[3] else "",
                                    "comment": ""
                                })
                            tables_info[table_name] = columns
                        except Exception as e:
                            logger.warning(f"获取表 {table_name} 结构失败: {e}")
                            continue

        finally:
            engine.dispose()

        return tables_info

    def validate_sql(self, sql: str) -> bool:
        """
        验证 SQL 安全性

        Args:
            sql: SQL 语句

        Returns:
            是否有效
        """
        is_valid, _ = SQLValidator.validate(sql)
        return is_valid
