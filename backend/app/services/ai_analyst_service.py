# backend/app/services/ai_analyst_service.py
"""
AI 数据分析师服务 - 基于 LangChain Agent 架构

工具集:
- execute_sql: 执行 SQL 查询
- generate_chart: 生成图表配置
- analyze_data: 数据分析洞察
- get_schema: 获取表结构
"""
import json
import uuid
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.utils.llm_client import LLMClient, LLMError, get_llm_client
from app.services.query_service import QueryService
from app.repositories.data_source_repository import DataSourceRepository
from app.utils.sql_validator import SQLValidator
from app.schemas.query import SQLQueryRequest
from app.schemas.ai_analyst import AIAnalystChatResponse, AIAnalystMessage, AIAnalystToolCall

logger = logging.getLogger(__name__)

# 简单内存缓存（对话历史）
_conversation_store: Dict[str, List[Dict[str, str]]] = {}
MAX_HISTORY = 20  # 保留最近 N 轮对话


class AIAnalystService:
    """AI 数据分析师服务"""

    SYSTEM_PROMPT = """你是一个专业的 AI 数据分析师。你的职责是帮助用户分析数据、生成查询、创建可视化图表。

你可以使用以下工具来完成任务：

1. **execute_sql** - 执行 SQL 查询
   - 当你需要查询数据时使用此工具
   - 只能执行 SELECT 查询（只读）
   - SQL 必须使用完整的 库名.表名 格式

2. **get_schema** - 获取数据库表结构
   - 当你不确定表名或字段名时，先使用此工具查看可用的表和列
   - 可以查看所有表或指定表的结构

3. **generate_chart** - 生成图表配置
   - 当查询结果需要可视化时，使用此工具生成 ECharts 图表配置
   - 支持: bar（柱状图）, line（折线图）, pie（饼图）, scatter（散点图）, area（面积图）

4. **analyze_data** - 数据分析洞察
   - 当用户需要对查询结果进行统计分析、趋势分析、异常检测等时使用
   - 会自动对已有数据进行分析并给出洞察

工作流程建议：
1. 如果用户的问题模糊，先用 get_schema 了解可用数据
2. 根据问题编写 SQL 并用 execute_sql 执行
3. 如果结果需要可视化，用 generate_chart 生成图表
4. 如果需要深入分析，用 analyze_data 进行分析
5. 综合以上结果，用自然语言给用户清晰的结论和建议

重要规则：
- 只执行 SELECT 查询，绝不执行 INSERT/UPDATE/DELETE/DROP 等修改操作
- SQL 表名必须带库名前缀
- 当不确定数据结构时，先查看 schema
- 回答要简洁清晰，重点突出
"""

    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.query_service = QueryService(db)

    def _get_llm_client(self) -> LLMClient:
        """获取 LLM 客户端"""
        return get_llm_client()

    def _get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """获取对话历史"""
        return _conversation_store.get(conversation_id, [])

    def _save_conversation_history(self, conversation_id: str, history: List[Dict[str, str]]):
        """保存对话历史"""
        _conversation_store[conversation_id] = history[-MAX_HISTORY * 2:]

    def _build_tools_prompt(self, data_source_id: int) -> str:
        """构建可用工具描述（告知 LLM 可用工具和参数格式）"""
        return f"""
当前可用工具（以 JSON 格式调用）：

1. get_schema - 获取数据库表结构
   输入: {{"tool": "get_schema", "input": {{"data_source_id": {data_source_id}}}}}

2. execute_sql - 执行 SQL 查询
   输入: {{"tool": "execute_sql", "input": {{"sql": "SELECT ...", "data_source_id": {data_source_id}}}}}

3. generate_chart - 生成图表配置
   输入: {{"tool": "generate_chart", "input": {{"chart_type": "bar|line|pie|scatter|area", "data": [...], "x_axis_field": "字段名", "y_axis_field": "字段名", "title": "图表标题"}}}}

4. analyze_data - 数据分析洞察
   输入: {{"tool": "analyze_data", "input": {{"data": [...], "columns": [...], "question": "用户问题"}}}}

当你需要使用工具时，请输出如下格式（一行 JSON）：
ACTION: {{"tool": "工具名", "input": {{参数}}}}

当你不需要使用工具，直接回答用户问题时，正常输出文字即可。
"""

    # ── 工具执行 ──────────────────────────────────────────────────

    def execute_sql_tool(self, sql: str, data_source_id: int) -> Dict[str, Any]:
        """执行 SQL 查询工具"""
        # 验证 SQL 安全
        is_valid, msg = SQLValidator.validate(sql)
        if not is_valid:
            return {"success": False, "error": f"SQL 验证失败: {msg}", "columns": [], "rows": [], "total": 0}

        # 获取数据源
        ds = self.ds_repo.get_by_id(data_source_id)
        if not ds:
            return {"success": False, "error": "数据源不存在", "columns": [], "rows": [], "total": 0}

        try:
            from app.utils.db_executor import execute_query
            rows, columns = execute_query(ds, sql)
            total = len(rows)
            # 限制返回数据量避免 token 爆炸
            preview_rows = rows[:100]
            return {
                "success": True,
                "columns": columns,
                "rows": preview_rows,
                "total": total,
                "preview_truncated": total > 100,
            }
        except Exception as e:
            logger.error(f"[AI-Analyst] SQL 执行失败: {e}")
            return {"success": False, "error": str(e), "columns": [], "rows": [], "total": 0}

    def get_schema_tool(self, data_source_id: int, table_name: Optional[str] = None) -> Dict[str, Any]:
        """获取表结构工具"""
        ds = self.ds_repo.get_by_id(data_source_id)
        if not ds:
            return {"success": False, "error": "数据源不存在", "tables": []}

        try:
            from app.utils.db_executor import execute_query

            db_type = ds.type.upper() if ds.type else "DORIS"

            if db_type in ("POSTGRES", "POSTGRESQL", "PG"):
                sql = """
                    SELECT table_name, column_name, data_type, is_nullable, 
                           column_default, 
                           col_description((quote_ident(table_schema)||'.'||quote_ident(table_name))::regclass, ordinal_position) as comment
                    FROM information_schema.columns 
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                """
            else:
                # MySQL / Doris / 其他
                sql = f"""
                    SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
                           COLUMN_DEFAULT, COLUMN_COMMENT
                    FROM information_schema.columns 
                    WHERE TABLE_SCHEMA = '{ds.database}'
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                """
                if table_name:
                    sql = sql.replace("WHERE", f"WHERE TABLE_NAME = '{table_name}' AND")

            rows, columns = execute_query(ds, sql)

            # 按表分组
            tables: Dict[str, List[Dict[str, str]]] = {}
            for row in rows:
                tbl = row[0]
                if tbl not in tables:
                    tables[tbl] = []
                tables[tbl].append({
                    "column": row[1],
                    "type": row[2],
                    "nullable": row[3],
                    "default": str(row[4]) if row[4] else None,
                    "comment": str(row[5]) if row[5] else None,
                })

            result_tables = []
            for tbl_name, cols in sorted(tables.items()):
                result_tables.append({
                    "table_name": tbl_name,
                    "columns": cols,
                    "column_count": len(cols),
                })

            return {
                "success": True,
                "tables": result_tables,
                "total_count": len(result_tables),
            }
        except Exception as e:
            logger.error(f"[AI-Analyst] 获取 schema 失败: {e}")
            return {"success": False, "error": str(e), "tables": []}

    def generate_chart_tool(
        self,
        chart_type: str,
        data: List[Any],
        x_axis_field: str,
        y_axis_field: str,
        title: str = "",
    ) -> Dict[str, Any]:
        """生成 ECharts 图表配置"""
        if not data:
            return {"success": False, "error": "无数据", "chart_config": None}

        # 从第一行数据推断列名（如果 data 是 list of dict）
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
        else:
            columns = [f"col_{i}" for i in range(len(data[0])) if isinstance(data[0], (list, tuple))]

        x_data = [row.get(x_axis_field) if isinstance(row, dict) else row[columns.index(x_axis_field)] for row in data]
        y_data = [row.get(y_axis_field) if isinstance(row, dict) else row[columns.index(y_axis_field)] for row in data]

        # 转数值
        try:
            y_data = [float(v) if v is not None else 0 for v in y_data]
        except (ValueError, TypeError):
            pass

        series_name = y_axis_field
        chart_config = {
            "title": {"text": title or f"{y_axis_field} by {x_axis_field}"},
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [series_name]},
            "xAxis": {"type": "category", "data": [str(v) for v in x_data]},
            "yAxis": {"type": "value"},
            "series": [
                {
                    "name": series_name,
                    "type": chart_type if chart_type in ("bar", "line", "scatter") else "bar",
                    "data": y_data,
                }
            ],
        }

        # 饼图特殊处理
        if chart_type == "pie":
            pie_data = [{"name": str(x), "value": y} for x, y in zip(x_data, y_data)]
            chart_config = {
                "title": {"text": title or y_axis_field},
                "tooltip": {"trigger": "item"},
                "series": [
                    {
                        "type": "pie",
                        "data": pie_data,
                    }
                ],
            }

        return {
            "success": True,
            "chart_config": chart_config,
            "chart_type": chart_type,
        }

    def analyze_data_tool(
        self,
        data: List[Any],
        columns: List[str],
        question: str = "",
    ) -> Dict[str, Any]:
        """数据分析洞察工具"""
        if not data or not columns:
            return {"success": False, "error": "无数据可分析", "insights": []}

        insights = []
        row_count = len(data)

        # 基础统计
        insights.append(f"数据共 {row_count} 行，{len(columns)} 列")

        # 数值列统计
        numeric_cols = []
        for col_idx, col_name in enumerate(columns):
            values = []
            for row in data:
                val = row[col_idx] if isinstance(row, (list, tuple)) else row.get(col_name)
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    continue

            if len(values) > row_count * 0.5:  # 超过50%是数值
                numeric_cols.append(col_name)
                avg_val = sum(values) / len(values) if values else 0
                min_val = min(values) if values else 0
                max_val = max(values) if values else 0
                insights.append(f"【{col_name}】均值={avg_val:.2f}, 最小={min_val}, 最大={max_val}, 非空数={len(values)}/{row_count}")

        # 分类列 top 值
        for col_idx, col_name in enumerate(columns):
            if col_name in numeric_cols:
                continue
            values = []
            for row in data:
                val = row[col_idx] if isinstance(row, (list, tuple)) else row.get(col_name)
                if val is not None:
                    values.append(str(val))

            if len(set(values)) <= 20 and len(values) > 0:
                from collections import Counter
                counter = Counter(values)
                top3 = counter.most_common(3)
                top_str = ", ".join(f"{k}({v})" for k, v in top3)
                insights.append(f"【{col_name}】Top值: {top_str}")

        # 使用 LLM 生成更高级的分析（可选）
        llm_analysis = None
        if question and len(data) > 0:
            try:
                llm_client = self._get_llm_client()
                # 构造数据摘要
                data_preview = json.dumps(data[:50], ensure_ascii=False, default=str)
                analysis_prompt = f"""作为数据分析师，分析以下数据并给出洞察。

用户问题: {question}

数据概要（前50行）:
列: {columns}
数据: {data_preview}

请从以下角度分析:
1. 数据整体趋势
2. 关键发现
3. 异常值或异常模式
4. 行动建议

请用中文简洁回答，使用 markdown 格式。"""
                messages = [
                    {"role": "system", "content": "你是一个专业的数据分析师，请基于数据给出分析洞察。"},
                    {"role": "user", "content": analysis_prompt},
                ]
                llm_analysis = llm_client.chat(messages, temperature=0.3)
            except Exception as e:
                logger.warning(f"[AI-Analyst] LLM 分析失败: {e}")

        return {
            "success": True,
            "insights": insights,
            "llm_analysis": llm_analysis,
            "numeric_columns": numeric_cols,
            "row_count": row_count,
            "column_count": len(columns),
        }

    # ── Agent 核心 ──────────────────────────────────────────────

    def _parse_action(self, text: str) -> Optional[Dict[str, Any]]:
        """从 LLM 输出中解析 ACTION: {...} 指令"""
        import re
        # 匹配 ACTION: {json} 或 ```json ... ```
        match = re.search(r'ACTION:\s*(\{.*?\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None

        # 也匹配 ```json\n{...}\n``` 格式
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None

        return None

    def _execute_tool(self, action: Dict[str, Any], data_source_id: int) -> Dict[str, Any]:
        """执行工具调用"""
        tool_name = action.get("tool", "")
        tool_input = action.get("input", {})

        if tool_name == "execute_sql":
            return self.execute_sql_tool(
                sql=tool_input.get("sql", ""),
                data_source_id=tool_input.get("data_source_id", data_source_id),
            )
        elif tool_name == "get_schema":
            return self.get_schema_tool(
                data_source_id=tool_input.get("data_source_id", data_source_id),
                table_name=tool_input.get("table_name"),
            )
        elif tool_name == "generate_chart":
            return self.generate_chart_tool(
                chart_type=tool_input.get("chart_type", "bar"),
                data=tool_input.get("data", []),
                x_axis_field=tool_input.get("x_axis_field", ""),
                y_axis_field=tool_input.get("y_axis_field", ""),
                title=tool_input.get("title", ""),
            )
        elif tool_name == "analyze_data":
            return self.analyze_data_tool(
                data=tool_input.get("data", []),
                columns=tool_input.get("columns", []),
                question=tool_input.get("question", ""),
            )
        else:
            return {"success": False, "error": f"未知工具: {tool_name}"}

    def chat(
        self,
        message: str,
        data_source_id: int,
        conversation_id: Optional[str] = None,
        group_id: Optional[int] = None,
    ) -> AIAnalystChatResponse:
        """
        同步聊天接口（非流式）

        Args:
            message: 用户消息
            data_source_id: 数据源 ID
            conversation_id: 对话 ID
            group_id: 集团 ID
        """
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        history = self._get_conversation_history(conversation_id)
        tools_prompt = self._build_tools_prompt(data_source_id)

        # 构建完整对话
        system_msg = self.SYSTEM_PROMPT + "\n\n" + tools_prompt
        if group_id:
            system_msg += f"\n\n当前用户集团ID: {group_id}（查询时需过滤此集团数据）"

        messages = [{"role": "system", "content": system_msg}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        # Agent 循环（最多 5 轮工具调用）
        chart_config = None
        tool_calls = []
        all_text = []
        for step in range(5):
            llm_client = self._get_llm_client()
            try:
                response_text = llm_client.chat(messages, temperature=0.0)
            except LLMError as e:
                return AIAnalystChatResponse(
                    conversation_id=conversation_id,
                    message=AIAnalystMessage(
                        role="assistant",
                        content=f"抱歉，AI 服务暂时不可用: {e}",
                    ),
                )

            # 检查是否有工具调用
            action = self._parse_action(response_text)
            if action is None:
                # 没有工具调用，直接返回
                all_text.append(response_text)
                self._save_conversation_history(conversation_id, [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response_text},
                ])
                return AIAnalystChatResponse(
                    conversation_id=conversation_id,
                    message=AIAnalystMessage(
                        role="assistant",
                        content=response_text,
                        tool_calls=tool_calls if tool_calls else None,
                        chart_config=chart_config,
                    ),
                )

            # 执行工具
            tool_name = action.get("tool", "unknown")
            tool_result = self._execute_tool(action, data_source_id)

            tool_calls.append(AIAnalystToolCall(
                tool_name=tool_name,
                tool_input=action.get("input", {}),
                tool_output=json.dumps(tool_result, ensure_ascii=False)[:2000],
            ))

            # 提取图表配置
            if tool_name == "generate_chart" and tool_result.get("success"):
                chart_config = tool_result.get("chart_config")

            # 将工具结果反馈给 LLM
            tool_feedback = f"工具 [{tool_name}] 执行结果:\n{json.dumps(tool_result, ensure_ascii=False, default=str)[:3000]}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": tool_feedback})

        # 达到最大轮次
        final_content = all_text[-1] if all_text else "已完成分析。"
        return AIAnalystChatResponse(
            conversation_id=conversation_id,
            message=AIAnalystMessage(
                role="assistant",
                content=final_content,
                tool_calls=tool_calls if tool_calls else None,
                chart_config=chart_config,
            ),
        )

    async def chat_stream(
        self,
        message: str,
        data_source_id: int,
        conversation_id: Optional[str] = None,
        group_id: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天接口（SSE）

        Yields dict with 'type' key: token / tool_call / tool_result / chart / done / error
        """
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        history = self._get_conversation_history(conversation_id)
        tools_prompt = self._build_tools_prompt(data_source_id)

        system_msg = self.SYSTEM_PROMPT + "\n\n" + tools_prompt
        if group_id:
            system_msg += f"\n\n当前用户集团ID: {group_id}（查询时需过滤此集团数据）"

        messages = [{"role": "system", "content": system_msg}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        chart_config = None
        all_tool_calls = []
        all_text = []

        for step in range(5):
            llm_client = self._get_llm_client()

            try:
                # 尝试流式调用
                response_text = await self._stream_llm_call(llm_client, messages)
            except Exception as e:
                logger.error(f"[AI-Analyst] LLM 调用失败: {e}")
                yield {"type": "error", "error": str(e)}
                return

            # 检查是否有工具调用
            action = self._parse_action(response_text)
            if action is None:
                # 直接输出最终回复
                all_text.append(response_text)
                # 逐 token 发送（这里非流式，一次性发送）
                yield {"type": "token", "content": response_text}

                self._save_conversation_history(conversation_id, [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response_text},
                ])
                yield {"type": "done", "conversation_id": conversation_id}
                return

            # 执行工具
            tool_name = action.get("tool", "unknown")
            yield {"type": "tool_call", "tool_name": tool_name, "tool_input": action.get("input", {})}

            tool_result = self._execute_tool(action, data_source_id)
            yield {"type": "tool_result", "tool_name": tool_name, "tool_output": json.dumps(tool_result, ensure_ascii=False)[:2000]}

            tool_calls_record = {
                "tool_name": tool_name,
                "tool_input": action.get("input", {}),
                "tool_output": json.dumps(tool_result, ensure_ascii=False)[:2000],
            }
            all_tool_calls.append(tool_calls_record)

            if tool_name == "generate_chart" and tool_result.get("success"):
                chart_config = tool_result.get("chart_config")
                yield {"type": "chart", "chart_config": chart_config}

            # 反馈给 LLM
            tool_feedback = f"工具 [{tool_name}] 执行结果:\n{json.dumps(tool_result, ensure_ascii=False, default=str)[:3000]}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": tool_feedback})

        yield {"type": "done", "conversation_id": conversation_id}

    async def _stream_llm_call(self, llm_client: LLMClient, messages: List[Dict[str, str]]) -> str:
        """
        调用 LLM（尽量使用流式）
        如果 LangChain adapter 可用则流式调用，否则回退到同步调用
        """
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

            # 尝试使用 LangChain 流式
            if hasattr(llm_client, '_build_langchain_chat_model'):
                model = llm_client._build_langchain_chat_model(temperature=0.0)
                lc_messages = llm_client._build_langchain_messages(messages)

                full_text = ""
                async for chunk in model.astream(lc_messages):
                    chunk_text = llm_client._extract_langchain_content(chunk)
                    if chunk_text:
                        full_text += chunk_text
                return full_text
        except Exception as e:
            logger.debug(f"[AI-Analyst] 流式调用失败，回退同步: {e}")

        # 回退到同步调用
        return llm_client.chat(messages, temperature=0.0)

    # ── Schema 查询 ──────────────────────────────────────────────

    def get_schema(self, data_source_id: int, table_name: Optional[str] = None) -> Dict[str, Any]:
        """获取表结构"""
        return self.get_schema_tool(data_source_id, table_name)
