# backend/app/services/nl2sql_service.py
import json
import logging
import os
from pathlib import Path
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
        logger.info("=" * 60)
        logger.info("[NL2SQL] 🔵 ========== 新的 NL2SQL 请求 ==========")
        logger.info(f"[NL2SQL] ├─ 用户ID: {user_id}")
        logger.info(f"[NL2SQL] ├─ 数据源ID: {request.data_source_id}")
        logger.info(f"[NL2SQL] ├─ 问题: {request.question}")
        logger.info(f"[NL2SQL] └─ 请求时间: {__import__('datetime').datetime.now().isoformat()}")
        
        sql = None
        confidence = 0.0
        explanation = ""
        used_llm = False

        # 1. 尝试使用 LLM 生成 SQL
        chart_config = None  # LLM 推荐的图表配置
        logger.info("[NL2SQL] 📌 步骤1: 尝试使用 LLM 生成 SQL...")
        try:
            llm_client = self._get_llm_client()
            logger.info(f"[NL2SQL] ├─ LLM 客户端初始化完成, timeout={llm_client.timeout}")
            
            sql, confidence, explanation, chart_config = self._generate_sql_with_llm(
                llm_client, request.question, request.data_source_id
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
        
        # 【新增】校验并修复 SQL 中的表名（确保带库名前缀）
        sql = self._fix_sql_table_names(sql, request.data_source_id)
        
        query_request = SQLQueryRequest(
            data_source_id=request.data_source_id,
            sql=sql,
            params={}
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
        logger.info("[NL2SQL] ═══════════════════════════════════════════")
        logger.info("[NL2SQL] 🔧 _generate_sql_with_llm 方法开始执行")
        
        # 1. 构建 schema prompt
        logger.info("[NL2SQL] ├─ 步骤1: 构建 Schema prompt...")
        schema_prompt = self.build_schema_prompt(data_source_id)
        logger.info(f"[NL2SQL] │   └─ Schema 长度: {len(schema_prompt)} 字符")

        # 2. 构建系统提示词
        print(f"[NL2SQL] ├─ 步骤2: 构建系统提示词...", flush=True)
        
        # 使用 print 输出完整的 system prompt，方便调试
        system_prompt = f"""你是一个数据分析专家，擅长将自然语言问题转换为 SQL 查询，并推荐合适的可视化图表。

## 数据源信息
{schema_prompt}

## 规则
1. 只生成 SELECT 查询，禁止生成 UPDATE/DELETE/DROP 等操作
2. 【重要】所有表名必须带库名前缀，如 `库名.表名`（例如 `ads_cockpit_freedom.store_sales`），否则跨库查询会失败！
3. 使用精确的表名和列名
4. 条件要准确匹配问题中的语义
5. 日期格式使用 YYYYMMDD（如 20260508）
6. 【重要】必须包含 ORDER BY 子句以支持分页，没有 ORDER BY 会导致查询失败！
7. 不要使用 SQL 注释（-- 或 /* */）
8. 不要在 SQL 末尾添加分号
9. 根据查询结果判断合适的图表类型：
   - 柱状图(bar)：适合对比分类数据的大小
   - 折线图(line)：适合展示趋势变化
   - 饼图(pie)：适合展示占比关系
   - 散点图(scatter)：适合展示相关性
10. X轴选择维度/分类字段，Y轴选择数值/指标字段
11. 【重要】日期函数注意：
    - Doris/StarRocks 不支持 `CURRENT_DATE`，请使用 `CURRENT_DATE()` (带括号)
    - 昨日: `DATE_SUB(CURDATE(), INTERVAL 1 DAY)` 或 `DATE_ADD(CURDATE(), INTERVAL -1 DAY)`
    - 日期格式: `YYYYMMDD`（如 20260510）
    - dt 字段是日期分区，格式为 `yyyymmdd`（字符串或整数）
12. 【强制】SQL 中所有表名**必须**带库名前缀，格式为 `库名.表名`：
    - 正确: `SELECT * FROM ads_cockpit_freedom.ads_cockpit_fd_store_ware_d`
    - 错误: `SELECT * FROM ads_cockpit_fd_store_ware_d` （漏掉库名！）
    - 如果你不想使用带库名的表名，直接返回空 SQL 并在 explanation 中说明原因

## 输出格式
请返回以下 JSON 格式（不要添加任何其他文字）：
{{
  "sql": "生成的 SQL 语句",
  "confidence": 0.0-1.0,
  "explanation": "SQL 生成逻辑的简要说明",
  "chart_config": {{
    "chart_type": "bar|line|pie|scatter",
    "x_axis": "X轴字段名（维度/分类）",
    "y_axis": "Y轴字段名（数值/指标）",
    "reason": "选择该图表配置的原因"
  }}
}}
"""
        print(f"[NL2SQL] │   └─ System prompt 长度: {len(system_prompt)} 字符", flush=True)
        print(f"[NL2SQL] │   └─ Schema preview: {schema_prompt[:200]}...", flush=True)

        # 3. 调用 LLM
        print(f"[NL2SQL] ├─ 步骤3: 调用 LLM 生成 SQL", flush=True)
        print(f"[NL2SQL] │   ├─ Question: {question}", flush=True)
        print(f"[NL2SQL] │   ├─ DataSourceID: {data_source_id}", flush=True)
        print(f"[NL2SQL] │   ├─ LLM Client Timeout: {llm_client.timeout}s", flush=True)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"问题: {question}"}
        ]
        
        print(f"[NL2SQL] │   ├─ Messages prepared", flush=True)
        
        print(f"[NL2SQL] │   └─ 正在等待 LLM 响应...", flush=True)
        response = llm_client.chat(messages, temperature=0.0)
        
        print(f"[NL2SQL] │       └─ LLM 响应长度: {len(response)} 字符", flush=True)
        print(f"[NL2SQL] │           └─ LLM 响应(前200字符): {response[:200]}...", flush=True)

        # 4. 解析 JSON 响应
        print(f"[NL2SQL] ├─ 步骤4: 解析 LLM JSON 响应", flush=True)
        result = self._parse_llm_response(response)

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
        
        # 【新增】详细日志：提取 SQL 中使用的所有表名
        import re
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
            # 尝试匹配不带库名的表名（可能存在问题）
            simple_table_pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            simple_tables = re.findall(simple_table_pattern, sql, re.IGNORECASE)
            if simple_tables:
                print(f"[NL2SQL] │   ⚠️ SQL 中有表未带库名: {simple_tables}", flush=True)
                logger.warning(f"[NL2SQL] │   ⚠️ SQL 中有表未带库名前缀: {simple_tables}")

        if not sql:
            print(f"[NL2SQL] │   └─ ❌ LLM 返回的 SQL 为空", flush=True)
            raise ValueError("LLM 未返回有效的 SQL")

        logger.info("[NL2SQL] └─ ✅ _generate_sql_with_llm 执行完成")
        
        return sql, confidence, explanation, chart_config

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

        优先使用语义层文档，次之动态查询数据库结构

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
            proxy = db.query(ProxyServer).filter(ProxyServer.id == ds.proxy_server_id).first()
            if proxy and proxy.is_active:
                proxy_auth = ""
                if proxy.username and proxy.password_encrypted:
                    proxy_auth = f"{proxy.username}:{decrypt_proxy_pwd(proxy.password_encrypted)}@"
                proxy_url = f"{proxy.proxy_type}://{proxy_auth}{proxy.host}:{proxy.port}"
        
        # 构建连接参数
        connect_args = {}
        if proxy_url:
            if ds_type == "MYSQL" or ds_type == "DORIS":
                connect_args = {"proxy": proxy_url}
            elif ds_type == "POSTGRESQL":
                import os
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

    def _fix_sql_table_names(self, sql: str, data_source_id: int) -> str:
        """
        校验并修复 SQL 中的表名，确保带库名前缀
        
        Args:
            sql: 原始 SQL
            data_source_id: 数据源 ID
            
        Returns:
            修复后的 SQL
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
        
        # 查找 SQL 中所有不带库名的表名（FROM/JOIN 后面只有表名，没有点号）
        # 匹配: FROM table_name 或 JOIN table_name (不含点号)
        pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
        
        def replace_func(match):
            prefix = match.group(1)
            # 跳过已带库名的表名（如已有 ads_cockpit_freedom.）
            if '.' in prefix:
                return match.group(0)
            # 跳过 MySQL 关键字和函数
            skip_words = {'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS', 
                         'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS', 'JOIN',
                         'GROUP', 'ORDER', 'BY', 'HAVING', 'LIMIT', 'OFFSET', 'UNION',
                         'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'NULL', 'TRUE', 'FALSE',
                         'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'COALESCE', 'IFNULL', 'IF'}
            if prefix.upper() in skip_words:
                return match.group(0)
            # 添加库名前缀
            fixed = f"{db_name}.{prefix}"
            logger.info(f"[NL2SQL] 🔧 修复表名: {prefix} -> {fixed}")
            return match.group(0).replace(prefix, fixed)
        
        # 检查是否有需要修复的表名
        tables_without_db = re.findall(pattern, sql, re.IGNORECASE)
        if not tables_without_db:
            return sql
        
        # 只修复真正需要修复的表名
        fixed_sql = sql
        for table in set(tables_without_db):
            # 跳过关键字
            if table.upper() in {'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS',
                                 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'GROUP', 'ORDER', 'BY',
                                 'HAVING', 'LIMIT', 'OFFSET', 'UNION', 'CASE', 'WHEN', 'THEN',
                                 'ELSE', 'END', 'NULL', 'TRUE', 'FALSE', 'COUNT', 'SUM', 
                                 'AVG', 'MAX', 'MIN', 'COALESCE', 'IFNULL', 'IF', 'FROM', 'JOIN'}:
                continue
            # 替换 FROM table / JOIN table
            fixed_sql = re.sub(
                rf'(?:FROM|JOIN)\s+{table}\b',
                lambda m: m.group(0).replace(table, f"{db_name}.{table}"),
                fixed_sql,
                flags=re.IGNORECASE
            )
        
        if fixed_sql != sql:
            logger.info(f"[NL2SQL] 🔧 SQL 表名已修复:\n  原SQL: {sql[:100]}...\n  新SQL: {fixed_sql[:100]}...")
        
        return fixed_sql
