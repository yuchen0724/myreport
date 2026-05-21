# backend/app/services/nl2sql_service.py
# pyright: reportGeneralTypeIssues=false, reportArgumentType=false, reportOptionalMemberAccess=false
import json
import hashlib
import logging
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import get_settings
from app.schemas.nl2sql import GeneratedSQLResult, NL2SQLRequest, NL2SQLResponse, SQLSuggestion
from app.utils.nl2sql_rules import NL2SQLRuleEngine
from app.utils.llm_client import LLMClient, LLMError, get_llm_client
from app.utils.nl2sql_cache import get_nl2sql_cache
from app.utils.sql_validator import SQLValidator
from app.services.query_service import QueryService
from app.schemas.query import SQLQueryRequest
from app.repositories.data_source_repository import DataSourceRepository
from app.core.security import decrypt_password

logger = logging.getLogger(__name__)

NL2SQL_PROMPT_VERSION = "nl2sql-langchain-structured-v1"


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
        logger.info("=" * 60)
        logger.info("[NL2SQL] 🔵 ========== 新的 NL2SQL 请求 ==========")
        logger.info(f"[NL2SQL] ├─ 用户ID: {user_id}")
        logger.info(f"[NL2SQL] ├─ 数据源ID: {request.data_source_id}")
        logger.info(f"[NL2SQL] ├─ 问题: {request.question}")
        if request.group_id:
            logger.info(f"[NL2SQL] ├─ 集团ID: {request.group_id}")
        logger.info(f"[NL2SQL] └─ 请求时间: {__import__('datetime').datetime.now().isoformat()}")
        
        sql = None
        confidence = 0.0
        explanation = ""
        used_llm = False
        llm_client_for_repair = None

        # 1. 尝试使用 LLM 生成 SQL
        chart_config = None  # LLM 推荐的图表配置
        logger.info("[NL2SQL] 📌 步骤1: 尝试使用 LLM 生成 SQL...")
        try:
            llm_client = self._get_llm_client()
            llm_client_for_repair = llm_client
            logger.info(f"[NL2SQL] ├─ LLM 客户端初始化完成, timeout={llm_client.timeout}")
            
            sql, confidence, explanation, chart_config = self._generate_sql_with_llm(
                llm_client, request.question, request.data_source_id, group_id=request.group_id, context=request.context
            )
            used_llm = True
            logger.info(f"[NL2SQL] ✅ LLM 生成 SQL 成功:")
            logger.info(f"[NL2SQL] │   ├─ SQL: {sql[:150]}..." if len(sql) > 150 else f"[NL2SQL] │   ├─ SQL: {sql}")
            logger.info(f"[NL2SQL] │   ├─ 置信度: {confidence:.2%}")
            logger.info(f"[NL2SQL] │   ├─ 解释: {explanation[:100]}..." if len(explanation) > 100 else f"[NL2SQL] │   ├─ 解释: {explanation}")
            logger.info(f"[NL2SQL] │   └─ 图表配置: {chart_config}")
        except LLMError as e:
            logger.warning(f"[NL2SQL] ⚠️ LLM 调用失败: {e}，回退到规则���擎")
        except Exception as e:
            logger.warning(f"[NL2SQL] ⚠️ LLM 生成 SQL 失败: {e}，回退到规则引擎")

        # 2. LLM 失败时，使用规则引擎作为 fallback
        if not sql:
            logger.info("[NL2SQL] 📌 步骤2: LLM 未成功，使用规则引擎作为 fallback...")
            sql, confidence = self.rule_engine.parse_question(request.question)
            explanation = f"基于规则引擎生成，置信度：{confidence:.2%}"
            logger.info(f"[NL2SQL] ✅ 规则引擎生成 SQL:")
            logger.info(f"[NL2SQL] │   ├─ SQL: {sql}")
            logger.info(f"[NL2SQL] │   └─ 置信度: {confidence:.2%}")
        else:
            logger.info("[NL2SQL] 📌 步骤2: 跳过规则引擎（LLM 成功）")

        # 3. 验证 SQL 安全性
        logger.info("[NL2SQL] 📌 步骤3: 验证 SQL 安全性...")
        is_valid, validation_msg = SQLValidator.validate(sql)
        if not is_valid:
            logger.error(f"[NL2SQL] ❌ SQL 验证失败: {validation_msg}")
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
        logger.info(f"[NL2SQL] ✅ SQL 验证通过: {validation_msg}")

        # 4. 创建 SQL 建议
        suggestion = SQLSuggestion(
            sql=sql,
            confidence=confidence,
            explanation=explanation,
            chart_config=chart_config
        )

        # 5. 执行 SQL 查询
        logger.info("[NL2SQL] 📌 步骤4: 执行 SQL 查询...")
        
        sql = self._prepare_sql_for_execution(sql, request.data_source_id, group_id=request.group_id)
        
        query_request = SQLQueryRequest(
            data_source_id=request.data_source_id,
            sql=sql,
            params={},
            skip_deep_pagination_check=True  # NL2SQL 查询跳过深度分页检查
        )

        try:
            result = self.query_service.execute_sql(query_request, user_id)

            logger.info("[NL2SQL] ✅ 查询执行成功:")
            logger.info(f"[NL2SQL] │   ├─ 列数: {len(result.columns)}")
            logger.info(f"[NL2SQL] │   ├─ 行数: {len(result.rows)}")
            logger.info(f"[NL2SQL] │   ├─ 总数: {result.total}")
            logger.info(f"[NL2SQL] │   └─ 执行时间: {result.execution_time_ms}ms")

            # 构建建议，包含 LLM 推荐的图表配置
            suggestion = SQLSuggestion(
                sql=sql,
                confidence=confidence,
                explanation=explanation,
                chart_config=chart_config
            )

            return NL2SQLResponse(
                suggestions=[suggestion],
                selected_sql=sql,
                query_result={
                    "columns": result.columns,
                    "rows": result.rows,
                    "total": result.total
                },
                execution_time_ms=result.execution_time_ms,
                recommended_chart=chart_config  # 返回推荐的图表配置
            )
        except Exception as e:
            # 查询失败，返回建议但不返回结果
            error_msg = str(e) if str(e) else f"{type(e).__name__}"
            logger.error(f"[NL2SQL] ❌ 查询执行失败: {error_msg}")

            if used_llm and llm_client_for_repair:
                repaired = self._try_repair_and_execute_sql(
                    llm_client=llm_client_for_repair,
                    question=request.question,
                    failed_sql=sql,
                    error_msg=error_msg,
                    request=request,
                    user_id=user_id,
                    original_confidence=confidence,
                    original_explanation=explanation,
                    original_chart_config=chart_config,
                )
                if repaired:
                    return repaired
            
            suggestion = SQLSuggestion(
                sql=sql,
                confidence=confidence,
                explanation=error_msg,
                chart_config=chart_config
            )
            
            return NL2SQLResponse(
                suggestions=[suggestion],
                selected_sql=sql,
                query_result=None,
                execution_time_ms=None,
                recommended_chart=chart_config
            )

    def _prepare_sql_for_execution(
        self,
        sql: str,
        data_source_id: int,
        group_id: Optional[int] = None
    ) -> str:
        """执行前应用已有的 NL2SQL SQL 修复规则"""
        logger.info("[NL2SQL] 跳过 _fix_sql_table_names，表名修正由 LLM 负责")
        sql = self._fix_sql_aggregate_orderby(sql)
        sql = self._fix_dim_date_column(sql)
        return sql

    def _try_repair_and_execute_sql(
        self,
        llm_client: LLMClient,
        question: str,
        failed_sql: str,
        error_msg: str,
        request: NL2SQLRequest,
        user_id: int,
        original_confidence: float,
        original_explanation: str,
        original_chart_config: Optional[Dict[str, Any]],
    ) -> Optional[NL2SQLResponse]:
        """查询执行失败后，尝试一次受控 SQL 修复并执行"""
        logger.info("[NL2SQL] 📌 步骤5: 尝试 LLM 自动修复 SQL...")
        try:
            repaired_sql, repaired_confidence, repaired_explanation, repaired_chart_config = self._repair_sql_with_llm(
                llm_client=llm_client,
                question=question,
                failed_sql=failed_sql,
                error_msg=error_msg,
                data_source_id=request.data_source_id,
                group_id=request.group_id,
                context=request.context,
            )
        except Exception as repair_error:
            logger.warning(f"[NL2SQL] ⚠️ SQL 自动修复失败: {repair_error}")
            return None

        is_valid, validation_msg = SQLValidator.validate(repaired_sql)
        if not is_valid:
            logger.warning(f"[NL2SQL] ⚠️ 修复 SQL 未通过安全校验: {validation_msg}")
            return None
        logger.info("[NL2SQL] 修复 SQL 安全校验通过")

        repaired_sql = self._prepare_sql_for_execution(
            repaired_sql,
            request.data_source_id,
            group_id=request.group_id,
        )
        repaired_request = SQLQueryRequest(
            data_source_id=request.data_source_id,
            sql=repaired_sql,
            params={},
            skip_deep_pagination_check=True,
        )

        try:
            result = self.query_service.execute_sql(repaired_request, user_id)
        except Exception as execute_error:
            logger.warning(f"[NL2SQL] ⚠️ 修复 SQL 执行仍失败: {execute_error}")
            return None

        explanation = (
            f"{original_explanation}\n自动修复: {repaired_explanation}"
            if original_explanation
            else f"自动修复: {repaired_explanation}"
        )
        chart_config = repaired_chart_config or original_chart_config
        suggestion = SQLSuggestion(
            sql=repaired_sql,
            confidence=repaired_confidence or original_confidence,
            explanation=explanation,
            chart_config=chart_config,
        )

        logger.info("[NL2SQL] ✅ 修复 SQL 执行成功")
        return NL2SQLResponse(
            suggestions=[suggestion],
            selected_sql=repaired_sql,
            query_result={
                "columns": result.columns,
                "rows": result.rows,
                "total": result.total,
            },
            execution_time_ms=result.execution_time_ms,
            recommended_chart=chart_config,
        )

    def _generate_sql_with_llm(
        self, llm_client: LLMClient, question: str, data_source_id: int,
        group_id: Optional[int] = None,
        context: Optional[str] = None
    ) -> Tuple[str, float, str, Optional[Dict[str, Any]]]:
        """
        使用 LLM 生成 SQL

        Args:
            llm_client: LLM 客户端
            question: 自然语言问题
            data_source_id: 数据源 ID
            group_id: 用户所属集团ID（用于分表选择和WHERE条件）
            context: 上下文信息（前一轮查询的结果摘要，用于多轮修正）

        Returns:
            (sql, confidence, explanation): 生成的 SQL、置信度和解释
        """
        logger.info("[NL2SQL] ═══════════════════════════════════════════")
        logger.info("[NL2SQL] 🔧 _generate_sql_with_llm 方法开始执行")
        
        # 0. 获取数据源信息（数据库类型）
        ds = self.ds_repo.get_by_id(data_source_id) if self.ds_repo else None
        db_type = ds.type.upper() if ds and ds.type else "DORIS"
        db_name = ds.database if ds and ds.database else "unknown"
        
        # 构建数据库类型相关的限制提示
        db_limitations = self._get_db_limitations(db_type)
        
        # 1. 构建 schema prompt
        logger.info("[NL2SQL] ├─ 步骤1: 构建 Schema prompt...")
        schema_prompt = self.build_schema_prompt(data_source_id)
        schema_prompt = self._select_relevant_schema_prompt(question, schema_prompt)
        logger.info(f"[NL2SQL] │   └─ Schema 长度: {len(schema_prompt)} 字符")

        cache_context = self._build_generation_cache_context(
            llm_client=llm_client,
            group_id=group_id,
            context=context,
            schema_prompt=schema_prompt,
        )
        cached_generation = self._get_cached_generation(question, data_source_id, cache_context)
        if cached_generation:
            logger.info("[NL2SQL] ✅ 命中 NL2SQL 生成缓存")
            print(f"[NL2SQL] │   └─ 命中 NL2SQL 生成缓存", flush=True)
            return cached_generation

        # 2. 构建系统提示词
        print(f"[NL2SQL] ├─ 步骤2: 构建系统提示词...", flush=True)
        system_prompt = self._build_system_prompt(
            db_type=db_type,
            db_limitations=db_limitations,
            schema_prompt=schema_prompt,
            group_id=group_id,
        )
        print(f"[NL2SQL] │   └─ System prompt 长度: {len(system_prompt)} 字符", flush=True)
        print(f"[NL2SQL] │   └─ Schema preview: {schema_prompt[:200]}...", flush=True)

        # 3. 调用 LLM
        print(f"[NL2SQL] ├─ 步骤3: 调用 LLM 生成 SQL", flush=True)
        print(f"[NL2SQL] │   ├─ Question: {question}", flush=True)
        print(f"[NL2SQL] │   ├─ DataSourceID: {data_source_id}", flush=True)
        print(f"[NL2SQL] │   ├─ LLM Client Timeout: {llm_client.timeout}s", flush=True)
        if context:
            print(f"[NL2SQL] │   ├─ Context provided: {context[:200]}...", flush=True)
        
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        if context:
            messages.append({"role": "system", "content": "## 多轮对话上下文\n以下是上一轮查询的结果摘要，请基于此修正或扩展你的回答：\n" + context})
        
        messages.append({"role": "user", "content": f"问题: {question}"})
        
        print(f"[NL2SQL] │   ├─ Messages prepared", flush=True)
        
        print(f"[NL2SQL] │   └─ 正在等待 LLM 响应...", flush=True)
        result = None
        if getattr(llm_client, "supports_structured_output", False):
            try:
                result = llm_client.chat_structured(messages, GeneratedSQLResult, temperature=0.0)
                print(f"[NL2SQL] │       └─ LLM 结构化响应获取成功", flush=True)
            except Exception as e:
                logger.warning(f"[NL2SQL] 结构化输出失败，回退到文本解析: {e}")
                print(f"[NL2SQL] │       └─ 结构化输出失败，回退到文本解析: {e}", flush=True)

        if result is None:
            response = llm_client.chat(messages, temperature=0.0)
            
            print(f"[NL2SQL] │       └─ LLM 响应长度: {len(response)} 字符", flush=True)
            print(f"[NL2SQL] │           └─ LLM 响应(前200字符): {response[:200]}...", flush=True)

            # 4. 解析 JSON 响应
            print(f"[NL2SQL] ├─ 步骤4: 解析 LLM JSON 响应", flush=True)
            result = self._parse_llm_response(response)
        else:
            print(f"[NL2SQL] ├─ 步骤4: 使用 LLM 结构化响应", flush=True)

        if not result:
            print(f"[NL2SQL] │   └─ ❌ 无法解析 LLM 响应为 JSON", flush=True)
            raise ValueError("无法解析 LLM 响应")

        sql = result.get("sql", "").strip()
        confidence = float(result.get("confidence", 0.0))
        explanation = result.get("explanation", "")
        # 提取图表配置
        chart_config_raw = result.get("chart_config")
        chart_config = None
        if chart_config_raw and isinstance(chart_config_raw, dict):
            chart_config = {
                "chart_type": chart_config_raw.get("chart_type", "bar"),
                "x_axis": chart_config_raw.get("x_axis", ""),
                "y_axis": chart_config_raw.get("y_axis", ""),
                "reason": chart_config_raw.get("reason", "")
            }
            print(f"[NL2SQL] │   ├─ 图表配置: {chart_config}", flush=True)

        print(f"[NL2SQL] │   ├─ 解析成功:", flush=True)
        print(f"[NL2SQL] │   │   ├─ SQL: {sql[:100]}..." if len(sql) > 100 else f"[NL2SQL] │   │   ├─ SQL: {sql}", flush=True)
        print(f"[NL2SQL] │   │   ├─ Confidence: {confidence:.2%}", flush=True)
        print(f"[NL2SQL] │   │   ├─ Explanation: {explanation[:80]}..." if len(explanation) > 80 else f"[NL2SQL] │   │   ├─ Explanation: {explanation}", flush=True)
        print(f"[NL2SQL] │   │   └─ Chart Config: {chart_config}", flush=True)
        
        # 详细日志：提取 SQL 中使用的所有表名
        import re
        # 提取 WITH 定义的 CTE 名称（别名不需要库名前缀）
        cte_names = set()
        cte_section_match = re.search(r'WITH\s+(.*?)\s+(?:SELECT|INSERT|UPDATE|DELETE)', sql, re.IGNORECASE | re.DOTALL)
        if cte_section_match:
            cte_section = cte_section_match.group(1)
            cte_names = set(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s+AS', cte_section, re.IGNORECASE))
        # 匹配 FROM/JOIN 后面的表名，支持: 库名.表名, 别名, 库名.表名 AS 别名
        table_pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)'
        tables_used = re.findall(table_pattern, sql, re.IGNORECASE)
        if tables_used:
            # 去重并按出现顺序排列
            unique_tables = list(dict.fromkeys(tables_used))
            table_list = [f"{db}.{tbl}" for db, tbl in unique_tables]
            print(f"[NL2SQL] │   ├─ SQL 使用的表: {table_list}", flush=True)
            logger.info(f"[NL2SQL] │   ├─ SQL 使用了 {len(unique_tables)} 个表: {table_list}")
        else:
            # 尝试匹配不带库名的表名（可能存在问题），过滤掉 DUAL 和 SQL 关键字
            simple_table_pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            simple_tables = re.findall(simple_table_pattern, sql, re.IGNORECASE)
            # 过滤掉 DUAL 和 SQL 关键字
            skip_words = {'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS',
                         'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS', 'JOIN',
                         'GROUP', 'ORDER', 'BY', 'HAVING', 'LIMIT', 'OFFSET', 'UNION',
                         'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'NULL', 'TRUE', 'FALSE',
                         'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'COALESCE', 'IFNULL', 'IF',
                         'FROM', 'JOIN', 'SET', 'VALUES', 'INTO', 'TABLE', 'DATABASE',
                         'SCHEMA', 'INDEX', 'VIEW', 'TRIGGER', 'FUNCTION', 'PROCEDURE',
                         'DUAL', 'WITH', 'RECURSIVE', 'UNION', 'ALL', 'DISTINCT'}
            simple_tables = [t for t in simple_tables if t.upper() not in skip_words]
            # 过滤掉 CTE 名称（虚拟表不需要库名前缀）
            if cte_names:
                orig_len = len(simple_tables)
                simple_tables = [t for t in simple_tables if t.upper() not in {n.upper() for n in cte_names}]
                if len(simple_tables) < orig_len:
                    print(f"[NL2SQL] │   ├─ 过滤掉 CTE 别名: {cte_names}", flush=True)
            # 过滤掉短别名（1~2个字符，通常是子查询别名如 t, t1, tt, x 等）
            aliases = [t for t in simple_tables if len(t) <= 2]
            if aliases:
                print(f"[NL2SQL] │   ├─ 过滤掉短别名: {aliases}", flush=True)
                simple_tables = [t for t in simple_tables if len(t) > 2]
            if simple_tables:
                print(f"[NL2SQL] │   ⚠️ SQL 中有表未带库名: {simple_tables}", flush=True)
                logger.warning(f"[NL2SQL] │   ⚠️ SQL 中有表未带库名前缀: {simple_tables}")

        if not sql:
            print(f"[NL2SQL] │   └─ ❌ LLM 返回的 SQL 为空", flush=True)
            raise ValueError("LLM 未返回有效的 SQL")

        self._cache_generation(
            question=question,
            data_source_id=data_source_id,
            sql=sql,
            confidence=confidence,
            explanation=explanation,
            chart_config=chart_config,
            cache_context=cache_context,
        )

        logger.info("[NL2SQL] └─ ✅ _generate_sql_with_llm 执行完成")
        
        return sql, confidence, explanation, chart_config

    def _select_relevant_schema_prompt(self, question: str, schema_prompt: str) -> str:
        """
        从长语义层文档中选择相关章节。

        保守策略：短文本、未命中、压缩收益不明显时返回原文。
        """
        settings = get_settings()
        if not getattr(settings, "nl2sql_schema_retrieval_enabled", True):
            logger.debug("[NL2SQL] Schema 检索已关闭，使用完整 schema prompt")
            return schema_prompt

        min_chars = getattr(settings, "nl2sql_schema_retrieval_min_chars", 12000)
        if len(schema_prompt) < min_chars:
            logger.debug(
                "[NL2SQL] Schema prompt 长度 %s 小于检索阈值 %s，使用完整 schema prompt",
                len(schema_prompt),
                min_chars,
            )
            return schema_prompt

        sections = self._split_schema_sections(schema_prompt)
        if len(sections) <= 2:
            logger.debug("[NL2SQL] Schema prompt 章节数不足，使用完整 schema prompt")
            return schema_prompt

        terms = self._extract_retrieval_terms(question)
        if not terms:
            logger.debug("[NL2SQL] 未提取到 schema 检索关键词，使用完整 schema prompt")
            return schema_prompt

        preamble = sections[0][1] if sections[0][0] == "__preamble__" else ""
        scored_sections = []
        for heading, content in sections:
            if heading == "__preamble__":
                continue
            score = self._score_schema_section(content, terms)
            if score > 0:
                scored_sections.append((score, content))

        if not scored_sections:
            logger.info("[NL2SQL] Schema 检索未命中相关章节，使用完整 schema prompt")
            return schema_prompt

        max_sections = getattr(settings, "nl2sql_schema_retrieval_max_sections", 8)
        selected = sorted(scored_sections, key=lambda item: item[0], reverse=True)[:max_sections]
        selected_contents = [
            content
            for _, content in sorted(selected, key=lambda item: schema_prompt.find(item[1]))
        ]
        compact_prompt = (
            f"{preamble.rstrip()}\n\n"
            "## 已筛选的相关语义层片段\n"
            f"以下内容基于用户问题筛选，prompt 版本: {NL2SQL_PROMPT_VERSION}。\n\n"
            + "\n\n".join(content.strip() for content in selected_contents)
        ).strip()

        if len(compact_prompt) >= len(schema_prompt) * 0.9:
            logger.info("[NL2SQL] Schema 检索压缩收益不足，使用完整 schema prompt")
            return schema_prompt

        logger.info(
            "[NL2SQL] Schema prompt 已压缩: %s -> %s 字符，章节数=%s",
            len(schema_prompt),
            len(compact_prompt),
            len(selected_contents),
        )
        return compact_prompt

    def _split_schema_sections(self, schema_prompt: str) -> List[Tuple[str, str]]:
        """按 markdown 标题切分 schema prompt"""
        matches = list(re.finditer(r"(?m)^(#{2,4}\s+.+)$", schema_prompt))
        if not matches:
            return [("__preamble__", schema_prompt)]

        sections: List[Tuple[str, str]] = []
        if matches[0].start() > 0:
            sections.append(("__preamble__", schema_prompt[:matches[0].start()].strip()))

        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(schema_prompt)
            sections.append((match.group(1).strip(), schema_prompt[start:end].strip()))
        return sections

    def _extract_retrieval_terms(self, question: str) -> List[str]:
        """提取用于 schema 章节检索的轻量关键词"""
        terms = set()
        normalized = question.lower()

        for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{1,}", normalized):
            terms.add(token)

        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", question):
            terms.add(chunk)
            for size in (2, 3, 4):
                if len(chunk) >= size:
                    for i in range(len(chunk) - size + 1):
                        terms.add(chunk[i:i + size])

        stop_terms = {
            "查询", "统计", "分析", "显示", "获取", "一下", "多少", "哪些",
            "今天", "昨日", "昨天", "本周", "本月", "去年", "今年",
        }
        return sorted((term for term in terms if term not in stop_terms), key=len, reverse=True)

    def _score_schema_section(self, section: str, terms: List[str]) -> int:
        """计算 schema 章节与问题关键词的匹配分"""
        normalized = section.lower()
        score = 0
        for term in terms:
            if term in normalized:
                score += max(1, len(term))
        return score

    def _build_system_prompt(
        self,
        db_type: str,
        db_limitations: str,
        schema_prompt: str,
        group_id: Optional[int] = None
    ) -> str:
        """构建 NL2SQL 系统提示词"""
        group_context = (
            f"**{group_id}**（已确认，该用户的查询应基于此集团的数据）"
            if group_id
            else "未知（未指定，按全局数据查询）"
        )
        return f"""你是一个数据分析专家，擅长将自然语言问题转换为 SQL 查询，并推荐合适的可视化图表。

## 数据库类型
当前数据源类型: **{db_type}**
{db_limitations}

## 数据源信息
{schema_prompt}

## 当前用户上下文
- 当前用户集团ID：{group_context}

## 规则
1. 只生成 SELECT 查询，禁止生成 UPDATE/DELETE/DROP 等操作
2. 【重要】所有表名必须带库名前缀，如 `库名.表名`（例如 `ads_cockpit_freedom.store_sales`），否则跨库查询会失败！
3. 【关键】必须严格使用下方语义层文档中定义的字段名，**禁止使用文档中不存在的字段**！
   - **【必须】在生成 SQL 前，必须逐一核对每个字段是否在该表的语义层文档中有定义**
   - **【严重】禁止使用其他表的字段混到当前表中，即使字段名相同也不行！每个表有自己独立的字段列表**
   - **【警告】文档中记录的字段可能与实际表结构有差异！如果 SQL 执行报错字段不存在，必须立即改用文档中明确存在的其他字段，禁止使用任何未经验证的字段！**
   - 字段名必须完全匹配（如 `store_code` 不能写成 `store_name` 或 `store`）
   - 如果需要的字段在文档中不存在，请在 explanation 中说明，并使用文档中存在的相似字段
4. 条件要准确匹配问题中的语义
5. 日期格式使用 YYYYMMDD（如 20260508）
6. 【重要】必须包含 ORDER BY 子句以支持分页，没有 ORDER BY 会导致查询失败！如果查询是聚合查询（SUM/COUNT/AVG等），**ORDER BY 的列必须在 SELECT 中或 GROUP BY 子句中**，且必须包含 GROUP BY！
7. 【重要】关于 group_id 和分表选择规则（ads_cockpit_fd_store_ware_d 系列表按集团分表）：
   - 【核心规则】ads_cockpit_fd_store_ware_d 表是按集团分表的！！！不同集团的数据存不同后缀的表中。**必须根据「当前用户上下文」中的集团ID使用对应的分表名，不能使用无后缀的基础表名！**
   - 【分表规则】分表后缀 = group_id，例如 group_id=812 时表名应为 ads_cockpit_fd_store_ware_d_812
   - 已知分表映射：
     - group_id=57362 → `ads_cockpit_fd_store_ware_d_57362`
     - group_id=812 → `ads_cockpit_fd_store_ware_d_812`
     - group_id=其他 → `ads_cockpit_fd_store_ware_d_其他`
   - 【重要】基础表名 `ads_cockpit_fd_store_ware_d`（无后缀）是除已列举集团以外的其他集团数据，**不要使用它**，除非「当前用户上下文」明确说集团ID未知
   - 【必须】如果「当前用户上下文」中给出了集团ID，必须在 SQL 中使用对应的分表名，并且在 WHERE 条件中添加 `group_id = xxx`
   - 注意：此规则同样适用于同结构的 ads_fd_dim_store_ware 维度表
8. 不要使用 SQL 注释（-- 或 /* */）
9. 不要在 SQL 末尾添加分号
10. 根据查询结果判断合适的图表类型：
   - 柱状图(bar)：适合对比分类数据的大小
   - 折线图(line)：适合展示趋势变化
   - 饼图(pie)：适合展示占比关系
   - 散点图(scatter)：适合展示相关性
11. X轴选择维度/分类字段，Y轴选择数值/指标字段
12. 【推荐】使用中文作为字段别名，例如 `SUM(sale_amt) AS `销售额``，方便非技术人员理解，注意用反引号包裹中文别名
13. 【重要】金额和数量类指标必须保留2位小数，使用 `ROUND(字段, 2)` 或 `CAST(字段 AS DECIMAL(18,2))`

## 输出格式
请返回以下 JSON 格式（不要添加任何其他文字）：
{{
  "sql": "生成的 SQL 语句",
  "confidence": 0.0-1.0,
  "explanation": "SQL 生成逻辑的简要说明（必须说明使用了哪些字段，这些字段在文档中是否存在）",
  "chart_config": {{
    "chart_type": "bar|line|pie|scatter",
    "x_axis": "X轴字段名（维度/分类）",
    "y_axis": "Y轴字段名（数值/指标）",
    "reason": "选择该图表配置的原因"
  }}
}}
"""

    def _repair_sql_with_llm(
        self,
        llm_client: LLMClient,
        question: str,
        failed_sql: str,
        error_msg: str,
        data_source_id: int,
        group_id: Optional[int] = None,
        context: Optional[str] = None,
    ) -> Tuple[str, float, str, Optional[Dict[str, Any]]]:
        """基于执行错误让 LLM 修复 SQL，返回候选 SQL"""
        ds = self.ds_repo.get_by_id(data_source_id) if self.ds_repo else None
        db_type = ds.type.upper() if ds and ds.type else "DORIS"
        db_limitations = self._get_db_limitations(db_type)
        schema_prompt = self.build_schema_prompt(data_source_id)
        schema_prompt = self._select_relevant_schema_prompt(
            f"{question}\n{failed_sql}\n{error_msg}",
            schema_prompt,
        )
        system_prompt = self._build_system_prompt(
            db_type=db_type,
            db_limitations=db_limitations,
            schema_prompt=schema_prompt,
            group_id=group_id,
        )
        repair_prompt = f"""## SQL 修复模式
你需要修复上一条 SQL，使其能正确执行。

要求：
1. 只返回修复后的 SELECT SQL 和说明，不要改变用户原始问题的查询意图。
2. 优先根据错误信息修正表名、字段名、聚合/GROUP BY、日期字段、函数兼容性。
3. 不要引入语义层文档中不存在的字段。

原始问题:
{question}

执行失败 SQL:
{failed_sql}

执行错误:
{error_msg}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": repair_prompt},
        ]
        if context:
            messages.insert(1, {"role": "system", "content": "## 多轮对话上下文\n" + context})

        result = None
        if getattr(llm_client, "supports_structured_output", False):
            try:
                result = llm_client.chat_structured(messages, GeneratedSQLResult, temperature=0.0)
            except Exception as e:
                logger.warning(f"[NL2SQL] 修复结构化输出失败，回退文本解析: {e}")

        if result is None:
            response = llm_client.chat(messages, temperature=0.0)
            result = self._parse_llm_response(response)

        if not result:
            raise ValueError("无法解析修复 SQL 响应")

        sql = result.get("sql", "").strip()
        if not sql:
            raise ValueError("LLM 未返回有效的修复 SQL")

        confidence = float(result.get("confidence", 0.0))
        explanation = result.get("explanation", "")
        chart_config_raw = result.get("chart_config")
        chart_config = None
        if chart_config_raw and isinstance(chart_config_raw, dict):
            chart_config = {
                "chart_type": chart_config_raw.get("chart_type", "bar"),
                "x_axis": chart_config_raw.get("x_axis", ""),
                "y_axis": chart_config_raw.get("y_axis", ""),
                "reason": chart_config_raw.get("reason", ""),
            }
        return sql, confidence, explanation, chart_config

    def _build_generation_cache_context(
        self,
        llm_client: LLMClient,
        group_id: Optional[int],
        context: Optional[str],
        schema_prompt: str
    ) -> Dict[str, Any]:
        """构建 NL2SQL 生成缓存上下文"""
        settings = getattr(llm_client, "settings", None)
        schema_fingerprint = hashlib.sha256(schema_prompt.encode("utf-8")).hexdigest()[:16]
        llm_fingerprint_data = {
            "adapter": getattr(llm_client, "adapter", ""),
            "provider": getattr(llm_client, "provider", ""),
            "api_mode": getattr(llm_client, "api_mode", ""),
            "model": getattr(settings, "llm_model", "") if settings else "",
        }
        llm_fingerprint = hashlib.sha256(
            json.dumps(llm_fingerprint_data, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "group_id": group_id,
            "context": context,
            "schema_fingerprint": schema_fingerprint,
            "llm_fingerprint": llm_fingerprint,
            "prompt_version": NL2SQL_PROMPT_VERSION,
        }

    def _get_cached_generation(
        self,
        question: str,
        data_source_id: int,
        cache_context: Dict[str, Any]
    ) -> Optional[Tuple[str, float, str, Optional[Dict[str, Any]]]]:
        """读取 NL2SQL 生成缓存"""
        try:
            cached = get_nl2sql_cache().get(
                question,
                data_source_id,
                group_id=cache_context["group_id"],
                context=cache_context["context"],
                schema_fingerprint=cache_context["schema_fingerprint"],
                llm_fingerprint=cache_context["llm_fingerprint"],
                prompt_version=cache_context["prompt_version"],
            )
            if not cached or not cached.get("sql"):
                return None
            return (
                cached["sql"],
                float(cached.get("confidence", 0.0)),
                cached.get("explanation") or "基于缓存的 NL2SQL 生成结果",
                cached.get("chart_config"),
            )
        except Exception as e:
            logger.warning(f"[NL2SQL] 读取生成缓存失败，继续调用 LLM: {e}")
            return None

    def _cache_generation(
        self,
        question: str,
        data_source_id: int,
        sql: str,
        confidence: float,
        explanation: str,
        chart_config: Optional[Dict[str, Any]],
        cache_context: Dict[str, Any]
    ) -> None:
        """写入 NL2SQL 生成缓存，失败不影响主流程"""
        try:
            cached = get_nl2sql_cache().set(
                question=question,
                data_source_id=data_source_id,
                sql=sql,
                explanation=explanation,
                confidence=confidence,
                chart_config=chart_config,
                group_id=cache_context["group_id"],
                context=cache_context["context"],
                schema_fingerprint=cache_context["schema_fingerprint"],
                llm_fingerprint=cache_context["llm_fingerprint"],
                prompt_version=cache_context["prompt_version"],
            )
            if cached:
                logger.info("[NL2SQL] 生成结果已写入缓存")
        except Exception as e:
            logger.warning(f"[NL2SQL] 写入生成缓存失败: {e}")

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

    def _get_db_limitations(self, db_type: str) -> str:
        """
        根据数据库类型返回不支持的函数和语法限制

        Args:
            db_type: 数据库类型 (DORIS, MYSQL, POSTGRESQL 等)

        Returns:
            数据库限制说明文本
        """
        limitations = {
            "DORIS": """
【重要】Doris/StarRocks 数据库特定限制：
1. 日期函数限制：
   - ❌ 不支持 `CURRENT_DATE`（不带括号），必须使用 `CURRENT_DATE()` 
   - ❌ 不支持 `NOW()`（不带括号），必须使用 `NOW()`
   - 【禁止】涉及 dt 字段时，禁止使用日期函数（如 DATE_SUB、CURDATE() 等）！dt 字段是字符串格式 yyyymmdd（如 '20260512'），日期函数返回的是日期类型格式（如 2026-05-11），两者不匹配会导致查询失败！
   - 【必须】涉及 dt 字段时，必须使用字符串格式的日期值，例如：
     - 昨日: `dt = '20260511'` 或 `dt = 20260511`
     - 今日: `dt = '20260512'` 或 `dt = 20260512`
     - 直接写死日期值，禁止使用日期函数转换！

   - 【重要】`ads_cockpit_qck.dim_date` 表**没有 `dt` 列**！该表的日期字段是 `date_id`（VARCHAR 类型，YYYYMMDD 格式，如 `'20260512'`）。查询 dim_date 表时必须使用 `date_id` 列，不要使用 `dt`！

2. 字符串函数限制：
   - ❌ 不支持 `GROUP_CONCAT`（MySQL 特有），使用 `GROUP_CONCAT_DISTINCT` 或 `STRING_AGG`
   - ❌ 不支持 `FIND_IN_SET`，使用 `array_contains` 或 `IN`

3. 数值精度限制：
   - 【重要】金额和数量类指标必须保留2位小数，使用 `ROUND(字段, 2)` 或 `CAST(字段 AS DECIMAL(18,2))`

4. 其他限制：
   - ❌ 不支持 `information_schema.TABLES`
   - ✅ 支持 `DUAL` 虚拟表（如 `SELECT 1 FROM DUAL`）
   - ✅ 支持窗口函数 (ROW_NUMBER, RANK, DENSE_RANK 等)
   - ✅ 支持 CTEs (WITH 子句)
""",
            "MYSQL": """
【重要】MySQL 数据库特定限制：
1. 日期函数：推荐使用 `CURRENT_DATE()`, `DATE_SUB(CURDATE(), INTERVAL 1 DAY)`
2. 字符串函数：支持 `GROUP_CONCAT`, `FIND_IN_SET`
3. 其他：注意版本兼容性
""",
            "POSTGRESQL": """
【重要】PostgreSQL 数据库特定限制：
1. 日期函数：使用 `CURRENT_DATE`, `NOW()`
2. 字符串函数：使用 `STRING_AGG` 替代 `GROUP_CONCAT`
3. 其他：支持丰富的 JSON/数组函数
""",
        }
        
        return limitations.get(db_type, """
【注意】未知数据库类型，请使用标准 SQL 语法。
""")

    def build_schema_prompt(self, data_source_id: int) -> str:
        """
        构建 Schema 描述 prompt

        优先使用语义层文档次之动态查询数据库结构

        Args:
            data_source_id: 数据源 ID

        Returns:
            Schema 描述字符串
        """
        # 1. 优先尝试读取语义层文档
        logger.info(f"[NL2SQL] 🔍 ========== 开始构建 Schema Prompt ==========")
        logger.info(f"[NL2SQL] ├─ 数据源ID: {data_source_id}")
        semantic_doc = self._load_semantic_doc(data_source_id)
        if semantic_doc:
            logger.info(f"[NL2SQL] │   ├─ 语义层文档: 找到, 长度={len(semantic_doc)} 字符")
            logger.info(f"[NL2SQL] │   │   ├─ 加载的文档: {self._get_loaded_doc_names(data_source_id)}")
            # 获取数据库名
            ds = self.ds_repo.get_by_id(data_source_id) if self.ds_repo else None
            db_name = ds.database if ds and ds.database else "数据库名"
            logger.info(f"[NL2SQL] │   │   └─ 数据库名: {db_name}")
            # 【重要】语义层文档中的表名已包含库名前缀，告诉 LLM 不要重复添加
            prefix_hint = f"\n## 重要提示\n【注意】本文档中的表名**已经包含库名前缀**（如 `ads_cockpit_qck.dim_store`），请直接使用文档中的表名，**不要再添加其他库名**！\n"
            return prefix_hint + semantic_doc

        # 2. 回退到动态查询
        logger.info(f"[NL2SQL] │   ├─ 语义层文档: 未找到, 改用动态查询获取表结构")
        if not self.ds_repo:
            logger.warning(f"[NL2SQL] │   └─ 数据源仓库不可用")
            return "数据源信息不可用"

        ds = self.ds_repo.get_by_id(data_source_id)
        if not ds:
            logger.warning(f"[NL2SQL] │   └─ 数据源 ID {data_source_id} 不存在")
            return f"数据源 ID {data_source_id} 不存在"

        try:
            tables_info = self._fetch_schema_from_datasource(ds)
            logger.info(f"[NL2SQL] │   └─ 动态获取表结构: {len(tables_info)} 个表")

            if not tables_info:
                logger.warning(f"[NL2SQL] │       └─ 未获取到任何表结构")
                return f"数据源: {ds.name} ({ds.type})\n表结构信息不可用"

            # 构建格式化的 schema 描述
            db_name = ds.database or ""
            prompt_parts = [
                f"数据源: {ds.name} ({ds.type})",
                f"数据库: {db_name}",
                f"【重要】SQL中所有表名必须使用 `{db_name}.表名` 格式，例如 `{db_name}.{next(iter(tables_info), 'table')}`",
                "",
                "## 表结构信息",
                ""
            ]

            for table_name, columns in tables_info.items():
                full_table_name = f"{db_name}.{table_name}" if db_name else table_name
                prompt_parts.append(f"### 表: {full_table_name}")
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
        ds_type = ds.type.upper() if ds.type else ""
        
        # 获取代理配置
        proxy_url = None
        if ds.use_proxy and ds.proxy_server_id:
            from app.core.security import decrypt_password as decrypt_proxy_pwd
            from app.models.proxy_server import ProxyServer
            # 使用传入的 db session
            if self.db:
                proxy = self.db.query(ProxyServer).filter(ProxyServer.id == ds.proxy_server_id).first()
            else:
                proxy = None
            if proxy and proxy.is_active:
                proxy_auth = ""
                if proxy.username and proxy.password_encrypted:
                    proxy_auth = f"{proxy.username}:{decrypt_proxy_pwd(proxy.password_encrypted)}@"
                proxy_url = f"{proxy.proxy_type}://{proxy_auth}{proxy.host}:{proxy.port}"
        
        # 构建连接参数
        connect_args = {}
        env_proxy_set = False
        old_http_proxy = None
        old_https_proxy = None
        if proxy_url:
            if ds_type == "MYSQL" or ds_type == "DORIS":
                connect_args = {"proxy": proxy_url}
            elif ds_type == "POSTGRESQL":
                env_proxy_set = True
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                os.environ['HTTP_PROXY'] = proxy_url
                os.environ['HTTPS_PROXY'] = proxy_url
        
        if ds_type == "MYSQL":
            conn_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        elif ds_type == "POSTGRESQL":
            conn_url = f"postgresql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        elif ds_type == "DORIS":
            # Doris 使用 MySQL 协议
            conn_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
        else:
            raise ValueError(f"不支持的数据源类型: {ds.type}")

        engine = create_engine(conn_url, pool_pre_ping=True, connect_args=connect_args)

        tables_info = {}

        try:
            try:
                with engine.connect() as conn:
                    # 获取表列表（含库名）
                    if ds.type in ["MYSQL", "DORIS"]:
                        # 从 information_schema 获取表及其所属库
                        tables_result = conn.execute(text("""
                            SELECT TABLE_SCHEMA, TABLE_NAME
                            FROM information_schema.TABLES
                            WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                            ORDER BY TABLE_SCHEMA, TABLE_NAME
                        """))
                        tables_with_schema = [(row[0], row[1]) for row in tables_result.fetchall()][:50]

                        # 获取每个表的列信息
                        for db_name, table_name in tables_with_schema:
                            try:
                                desc_result = conn.execute(text(f"DESCRIBE `{db_name}`.`{table_name}`"))
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
                                # 键名使用 "库名.表名" 格式
                                tables_info[f"{db_name}.{table_name}"] = columns
                            except Exception as e:
                                logger.warning(f"获取表 {db_name}.{table_name} 结构失败: {e}")
                                continue

                    elif ds_type == "POSTGRESQL":
                        # PostgreSQL 使用 information_schema，获取 schema（相当于库）
                        tables_result = conn.execute(text(f"""
                        SELECT table_schema, table_name
                            FROM information_schema.tables
                            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                            ORDER BY table_schema, table_name
                        """))
                        tables_with_schema = [(row[0], row[1]) for row in tables_result.fetchall()][:50]

                        for db_name, table_name in tables_with_schema:
                            try:
                                desc_result = conn.execute(text(f"""
                                    SELECT
                                        column_name,
                                        data_type,
                                        is_nullable,
                                        column_default
                                    FROM information_schema.columns
                                    WHERE table_schema = :schema_name AND table_name = :table_name
                                    ORDER BY ordinal_position
                                """), {"schema_name": db_name, "table_name": table_name})

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
                                tables_info[f"{db_name}.{table_name}"] = columns
                            except Exception as e:
                                logger.warning(f"获取表 {db_name}.{table_name} 结构失败: {e}")
                                continue
            finally:
                engine.dispose()
            return tables_info
        finally:
            if env_proxy_set:
                import os
                if old_http_proxy is None:
                    os.environ.pop('HTTP_PROXY', None)
                else:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy is None:
                    os.environ.pop('HTTPS_PROXY', None)
                else:
                    os.environ['HTTPS_PROXY'] = old_https_proxy

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

    def _load_semantic_doc(self, data_source_id: int) -> Optional[str]:
        """
        加载语义层文档 - 动态扫描，按数据源名+数据库名查找

        查找规则（按优先级）:
        1. 加载 semantic/{数据源名}/*.md (合并所有 .md 文件)
        2. 加载 semantic/{数据源名}/{数据库名}.md (单个文件)
        3. 加载 semantic/{数据源名}/{数据库名}/README.md
        4. 加载 semantic/{数据源名}/{数据库名}/*.md (合并目录下的所有 .md 文件)

        Args:
            data_source_id: 数据源 ID

        Returns:
            语义层文档内容，如果不存在则返回 None
        """
        if not self.ds_repo:
            return None

        try:
            ds = self.ds_repo.get_by_id(data_source_id)
            if not ds or not ds.database:
                return None

            ds_name = ds.name.lower() if ds.name else ""
            db_name = ds.database.lower()
            semantic_dir = self._get_semantic_dir()

            if not semantic_dir or not semantic_dir.exists():
                logger.warning(f"语义层目录不存在: {semantic_dir}")
                return None

            # 优先加载该数据源下所有的 .md 文件
            ds_dir = semantic_dir / ds_name
            if ds_dir.exists() and ds_dir.is_dir():
                md_files = sorted(ds_dir.glob("*.md"))
                # 过滤掉 README.md（作为单独策略）
                md_files = [f for f in md_files if f.name.upper() != "README.MD"]
                
                if md_files:
                    contents = []
                    for md_file in md_files:
                        file_content = md_file.read_text(encoding="utf-8")
                        # 使用文件名（不含扩展名）作为章节标题
                        contents.append(f"## {md_file.stem}\n\n{file_content}")
                    
                    content = "\n\n".join(contents)
                    logger.info(f"加载语义层文档(合并 {len(md_files)} 个文件): {ds_dir}")
                    return content

            # 回退策略：按数据库名单个文件查找
            single_file = semantic_dir / ds_name / f"{db_name}.md"
            if single_file.exists():
                content = single_file.read_text(encoding="utf-8")
                logger.info(f"加载语义层文档(单文件): {single_file}")
                return content

            # 策略3: semantic/{数据源名}/{数据库名}/README.md
            db_dir = semantic_dir / ds_name / db_name
            readme_file = db_dir / "README.md"
            if db_dir.exists() and db_dir.is_dir() and readme_file.exists():
                content = readme_file.read_text(encoding="utf-8")
                logger.info(f"加载语义层文档(目录): {readme_file}")
                return content

            # 策略4: semantic/{数据源名}/{数据库名}/*.md 合并
            if db_dir.exists() and db_dir.is_dir():
                md_files = sorted(db_dir.glob("*.md"))
                if md_files:
                    contents = []
                    for md_file in md_files:
                        contents.append(f"## {md_file.stem}\n\n{md_file.read_text(encoding='utf-8')}")
                    content = "\n\n".join(contents)
                    logger.info(f"加载语义层文档(合并 {len(md_files)} 个文件): {db_dir}")
                    return content

            # 兼容策略: 找不到时回退到根目录查找
            return self._load_semantic_doc_fallback(semantic_dir, db_name)

        except Exception as e:
            logger.error(f"加载语义层文档失败: {e}")
            return None

    def _load_semantic_doc_fallback(self, semantic_dir: Path, db_name: str) -> Optional[str]:
        """回退到根目录查找（兼容旧结构）"""
        # 策略1: semantic/{database}.md
        single_file = semantic_dir / f"{db_name}.md"
        if single_file.exists():
            content = single_file.read_text(encoding="utf-8")
            logger.info(f"加载语义层文档(兼容模式-单文件): {single_file}")
            return content

        # 策略2: semantic/{database}/README.md
        db_dir = semantic_dir / db_name
        readme_file = db_dir / "README.md"
        if db_dir.exists() and db_dir.is_dir() and readme_file.exists():
            content = readme_file.read_text(encoding="utf-8")
            logger.info(f"加载语义层文档(兼容模式-目录): {readme_file}")
            return content

        logger.warning(f"回退查找也未找到数据库 {db_name} 对应的语义层文档")
        return None

    def _get_loaded_doc_names(self, data_source_id: int) -> List[str]:
        """
        获取已加载的语义层文档文件名列表
        
        Args:
            data_source_id: 数据源 ID
            
        Returns:
            文档文件名列表
        """
        if not self.ds_repo:
            return []
        
        try:
            ds = self.ds_repo.get_by_id(data_source_id)
            if not ds or not ds.database:
                return []
            
            ds_name = ds.name.lower() if ds.name else ""
            semantic_dir = self._get_semantic_dir()
            
            if not semantic_dir or not semantic_dir.exists():
                return []
            
            ds_dir = semantic_dir / ds_name
            if ds_dir.exists() and ds_dir.is_dir():
                md_files = sorted(ds_dir.glob("*.md"))
                md_files = [f for f in md_files if f.name.upper() != "README.MD"]
                return [f.name for f in md_files]
            
            # 回退到单个文件
            db_name = ds.database.lower()
            single_file = semantic_dir / ds_name / f"{db_name}.md"
            if single_file.exists():
                return [single_file.name]
                
            return []
        except Exception as e:
            logger.warning(f"获取加载的文档名失败: {e}")
            return []

    def _get_semantic_dir(self) -> Optional[Path]:
        """获取语义层目录路径"""
        possible_dirs = [
            Path("/home/zhou/myreport/semantic"),
            Path(__file__).parent.parent.parent / "semantic",
            Path(__file__).parent.parent / "semantic",
        ]
        for d in possible_dirs:
            if d.exists():
                return d
        # 返回第一个可能的目录（用于创建）
        return possible_dirs[0]

    def _fix_sql_aggregate_orderby(self, sql: str) -> str:
        """
        自动修复聚合查询 + ORDER BY 但无 GROUP BY 的问题
        
        场景：LLM 生成了 SELECT SUM(...) AS `别名` FROM ... ORDER BY dt
        Doris 要求 ORDER BY 的列必须在 SELECT 中或 GROUP BY 中
        修复：如果检测到聚合函数 + ORDER BY + 无 GROUP BY，移除 ORDER BY
        """
        import re
        
        # 检查是否有聚合函数
        has_aggregate = bool(re.search(
            r'\b(SUM|COUNT|AVG|MAX|MIN|GROUP_CONCAT|STRING_AGG|COUNT_DISTINCT)\s*\(',
            sql, re.IGNORECASE
        ))
        if not has_aggregate:
            return sql
        
        # 检查是否有 GROUP BY
        has_groupby = bool(re.search(r'\bGROUP\s+BY\b', sql, re.IGNORECASE))
        if has_groupby:
            return sql
        
        # 检查是否有 ORDER BY
        orderby_match = re.search(r'\bORDER\s+BY\s+.+', sql, re.IGNORECASE | re.DOTALL)
        if not orderby_match:
            return sql
        
        orderby_clause = orderby_match.group(0)
        
        # 尝试从 ORDER BY 中提取列名作为 GROUP BY 的候选
        # 匹配 ORDER BY 后到 LIMIT/OFFSET/结束 之间的字段
        orderby_cols = re.findall(
            r'ORDER\s+BY\s+(.+?)(?:\s+(?:ASC|DESC))?(?:\s*,\s*)?',
            sql, re.IGNORECASE
        )
        
        logger.warning(f"[NL2SQL] ⚠️ 检测到聚合查询有 ORDER BY 但无 GROUP BY，移除 ORDER BY 子句")
        logger.warning(f"[NL2SQL] ⚠️ 移除的 ORDER BY: {orderby_clause}")
        
        # 移除 ORDER BY 子句（保留其后的 LIMIT/OFFSET）
        fixed_sql = re.sub(
            r'\s+ORDER\s+BY\s+.+?(?=\s*(?:LIMIT|OFFSET|$))',
            '',
            sql,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        logger.info(f"[NL2SQL] 🔧 已修复聚合查询 ORDER BY 问题")
        return fixed_sql

    def _fix_dim_date_column(self, sql: str) -> str:
        """
        自动修复 dim_date 表中 dt 列的引用为 date_id

        dim_date 表没有 dt 列，日期字段名为 date_id。
        修复模式：
        1. `dim_date.dt` → `dim_date.date_id`
        2. `ads_cockpit_qck.dim_date.dt` → `ads_cockpit_qck.dim_date.date_id`
        3. 纯 `dt` 引用在 WHERE 中——只替换 FROM/JOIN 了 dim_date 的查询中的 dt
        """
        import re

        # 如果 SQL 中没有 dim_date 关键词，无需处理
        if 'dim_date' not in sql.lower():
            return sql

        # 替换 ads_cockpit_qck.dim_date.dt → ads_cockpit_qck.dim_date.date_id
        sql = re.sub(
            r'(ads_cockpit_qck\.dim_date)\.dt\b',
            r'\1.date_id',
            sql,
            flags=re.IGNORECASE
        )

        # 替换 dim_date.xxxx.dt → dim_date.xxxx.date_id（仅当前面出现了 dim_date 表时）
        # 正则：查找 dim_date 后跟 .dt 但 dt 不是独立单词部分的情况
        sql = re.sub(
            r'(?<!\w)(dim_date)\.dt\b',
            r'\1.date_id',
            sql,
            flags=re.IGNORECASE
        )

        return sql

    def _fix_sql_table_names(self, sql: str, data_source_id: int, group_id: Optional[int] = None) -> str:
        """
        校验并修复 SQL 中的表名，确保带库名前缀
        
        逻辑：
        1. 匹配 FROM/JOIN 后的完整表名（如 ads_cockpit_freedom.table_name 或 table_name）
        2. 如果已带库名（有点号），跳过
        3. 如果没有库名，添加数据源的默认库名
        4. 跳过 WITH 定义的 CTE（虚拟表）
        5. 分表替换：优先使用 SQL 中 group_id WHERE 条件，其次使用传入的 group_id 参数
        """
        import re
        
        # 获取数据源的默认数据库名
        db_name = None
        if self.ds_repo:
            ds = self.ds_repo.get_by_id(data_source_id)
            if ds and ds.database:
                db_name = ds.database
        
        if not db_name:
            logger.warning(f"[NL2SQL] ⚠️ 无法获取数据源 {data_source_id} 的数据库名")
            return sql
        
        # 提取 WITH 定义的 CTE 名称（虚拟表名不添加库名）
        cte_names = set()
        # 匹配 WITH 后到 SELECT 之间的所有 CTE 名称
        # 格式: WITH cte1 AS (...), cte2 AS (...), cte3 AS (...) SELECT ...
        cte_section_match = re.search(r'WITH\s+(.*?)\s+(?:SELECT|INSERT|UPDATE|DELETE)', sql, re.IGNORECASE | re.DOTALL)
        if cte_section_match:
            cte_section = cte_section_match.group(1)
            # 提取所有 CTE 名称（AS 之前的标识符）
            cte_names = set(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s+AS', cte_section, re.IGNORECASE))
        
        if cte_names:
            logger.info(f"[NL2SQL] ℹ️ 跳过 WITH 定义的 CTE: {cte_names}")
        
        # 提取 FROM/JOIN 中显式声明的别名（避免后续把别名误当表名加库前缀）
        alias_pattern = (
            r'(?:FROM|JOIN)\s+'
            r'[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?'
            r'\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)'
        )
        aliases = {
            alias.upper()
            for alias in re.findall(alias_pattern, sql, re.IGNORECASE)
        }
        if aliases:
            logger.info(f"[NL2SQL] ℹ️ 检测到 SQL 表别名: {aliases}")

        # 匹配 FROM/JOIN 后的表名，支持两种格式：
        # 1. db.table_name (带库名)
        # 2. table_name (不带库名)
        pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*(?:AS\s+\w+)?'
        
        matches = re.findall(pattern, sql, re.IGNORECASE)
        
        fixed_sql = sql
        for full_table in set(matches):
            # 跳过 WITH 定义的 CTE（虚拟表）
            if full_table.upper() in {t.upper() for t in cte_names}:
                logger.info(f"[NL2SQL] ✓ 跳过 CTE: {full_table}")
                continue
            
            # 跳过已带库名的表名（已包含点号）
            if '.' in full_table:
                logger.info(f"[NL2SQL] ✓ 表名已带库名，跳过: {full_table}")
                continue
            
            # 跳过 SQL 关键字和虚拟表
            skip_words = {'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS', 
                         'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS', 'JOIN',
                         'GROUP', 'ORDER', 'BY', 'HAVING', 'LIMIT', 'OFFSET', 'UNION',
                         'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'NULL', 'TRUE', 'FALSE',
                         'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'COALESCE', 'IFNULL', 'IF',
                         'FROM', 'JOIN', 'SET', 'VALUES', 'INTO', 'TABLE', 'DATABASE',
                         'SCHEMA', 'INDEX', 'VIEW', 'TRIGGER', 'FUNCTION', 'PROCEDURE',
                         'DUAL'}
            if full_table.upper() in skip_words:
                continue

            # 跳过已定义的表别名（别名不是实际物理表，不能加库名前缀）
            if full_table.upper() in aliases:
                logger.info(f"[NL2SQL] ✓ 跳过表别名: {full_table}")
                continue
            
            # 添加库名前缀
            fixed_name = f"{db_name}.{full_table}"
            fixed_sql = re.sub(
                rf'(?:FROM|JOIN)\s+{re.escape(full_table)}\b',
                lambda m: m.group(0).replace(full_table, fixed_name),
                fixed_sql,
                flags=re.IGNORECASE
            )
            logger.info(f"[NL2SQL] 🔧 修复表名: {full_table} -> {fixed_name}")
        
        # 【分表替换】从 SQL 中提取 group_id 条件值，匹配分表后缀
        # 对 ads_cockpit_fd_store_ware_d 系列表，按 group_id 分表
        base_shard_tables = ['ads_cockpit_fd_store_ware_d', 'ads_fd_dim_store_ware']
        
        for base_table_name in base_shard_tables:
            # 检查 SQL 中是否包含该基础表名（可能带库名或不带）
            full_base_table = f"{db_name}.{base_table_name}"
            has_table = full_base_table in fixed_sql or base_table_name in fixed_sql
            
            if not has_table:
                continue
            
            # 尝试提取 group_id 值（支持 group_id = X 或 group_id = 'X' 或 group_id IN (X)）
            sql_group_id_match = re.search(
                r'group_id\s*=\s*(\d+)',
                fixed_sql, re.IGNORECASE
            )
            
            effective_group_id = None
            if sql_group_id_match:
                effective_group_id = int(sql_group_id_match.group(1))
                logger.info(f"[NL2SQL] 🔍 从 SQL WHERE 条件检测到 group_id={effective_group_id}")
            elif group_id is not None:
                effective_group_id = group_id
                logger.info(f"[NL2SQL] 🔍 使用调用方传入的 group_id={effective_group_id}")
            
            if effective_group_id is not None:
                gid = effective_group_id
                logger.info(f"[NL2SQL] 🔧 检查是否需要分表替换（group_id={gid}）")
                
                # 构建分表名：原表名 + _ + group_id
                shard_table = f"{base_table_name}_{gid}"
                
                # 替换 SQL 中的表名（先替换带库名的，再替换不带库名的）
                db_shard_table = f"{db_name}.{shard_table}"
                
                # 替换带库名的表名（使用词边界，避免 ads_cockpit_fd_store_ware_d 错误匹配 ads_cockpit_fd_store_ware_d_812）
                if full_base_table in fixed_sql:
                    # 用 regex 做完整词边界替换：库名.表名 后跟空格/逗号/结束/换行
                    fixed_sql = re.sub(
                        re.escape(full_base_table) + r'(?=[\s,)]|$)',
                        db_shard_table,
                        fixed_sql
                    )
                    logger.info(f"[NL2SQL] 🔧 分表替换: {full_base_table} -> {db_shard_table} (group_id={gid})")
                else:
                    # 替换不带库名的表名（同样词边界）
                    fixed_sql = re.sub(
                        re.escape(base_table_name) + r'(?=[\s,.)]|$)',
                        shard_table,
                        fixed_sql
                    )
                    logger.info(f"[NL2SQL] 🔧 分表替换: {base_table_name} -> {shard_table} (group_id={gid})")
        
        if fixed_sql != sql:
            logger.info(f"[NL2SQL] 🔧 SQL 表名已修复:\\n  原SQL: {sql[:150]}...\\n  新SQL: {fixed_sql[:150]}...")
        
        return fixed_sql

    def get_groups(self, data_source_id: int) -> list:
        """从 dim_store 查询集团列表（优先从 Redis 缓存读取）"""
        logger.info(f"[NL2SQL] 🔍 查询集团列表, 数据源ID: {data_source_id}")

        # 1. 优先从 Redis 读取
        cache_key = f"nl2sql:groups:{data_source_id}"
        try:
            from app.core.redis import redis_client
            if redis_client:
                cached = redis_client.get(cache_key)
                if cached:
                    rows = json.loads(cached)
                    logger.info(f"[NL2SQL] ├─ Redis 缓存命中, 集团数: {len(rows)}")
                    return rows
        except Exception as e:
            logger.warning(f"[NL2SQL] ⚠️ Redis 读取失败, 回退 DB 查询: {e}")

        # 2. Redis 未命中, 从 Doris 查询
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import QueuePool

        ds = self.ds_repo.get_by_id(data_source_id)
        if not ds:
            raise ValueError("数据源不存在")

        password = decrypt_password(ds.password_encrypted)
        conn_url = f"mysql+pymysql://{ds.username}:***@{ds.host}:{ds.port}/{ds.database}"
        engine = create_engine(conn_url.replace('***', password), poolclass=QueuePool, pool_size=2, max_overflow=2, pool_pre_ping=True, connect_args={"connect_timeout": 5})

        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT DISTINCT group_id, group_name FROM ads_cockpit_qck.dim_store ORDER BY group_id"))
                rows = [{"group_id": row[0], "group_name": row[1]} for row in result.fetchall()]
                logger.info(f"[NL2SQL] └─ Doris 查询成功, 集团数: {len(rows)}")
        except Exception as e:
            logger.error(f"[NL2SQL] ❌ 查询集团列表失败: {e}")
            raise
        finally:
            engine.dispose()

        # 3. 写入 Redis 缓存（TTL=1小时）
        try:
            from app.core.redis import redis_client
            if redis_client:
                redis_client.setex(cache_key, 86400, json.dumps(rows, ensure_ascii=False))
            logger.info(f"[NL2SQL] ├─ 集团数据已写入 Redis 缓存（TTL=86400s）")
        except Exception as e:
            logger.warning(f"[NL2SQL] ⚠️ Redis 写入失败: {e}")

        return rows
