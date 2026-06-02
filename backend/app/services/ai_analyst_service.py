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
from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.utils.sql_validator import SQLValidator
from app.utils.sql_normalizer import strip_trailing_semicolon, has_multi_level_table_reference, has_foreign_schema_reference, has_forbidden_sql_tokens
from app.schemas.query import SQLQueryRequest
from app.schemas.ai_analyst import AIAnalystChatResponse, AIAnalystMessage, AIAnalystToolCall
from pydantic import BaseModel, Field
from app.schemas.semantic_metric import SemanticMetricQueryRequest
from app.services.semantic_metric_query_service import SemanticMetricQueryService
from app.utils.semantic_runtime_context import build_semantic_runtime_context
import hashlib
from app.utils.chart_axis_inference import infer_chart_axes
from app.models.user import User
from app.core.redis import get_redis
from app.services.nl2sql.prompt_utils import PromptManager

logger = logging.getLogger(__name__)

# 对话历史持久化存储（Redis）
MAX_HISTORY = 20  # 保留最近 N 轮对话
_REDIS_CONVERSATION_PREFIX = "ai_analyst:conversation:"


class AgentAction(BaseModel):
    """结构化输出：LLM 工具调用或最终回答"""
    thought: str = Field(description="思考过程")
    tool: Optional[str] = Field(None, description="要调用的工具名，无工具调用时为 null")
    tool_input: Optional[Dict[str, Any]] = Field(None, description="工具参数")
    final_answer: Optional[str] = Field(None, description="最终回复，无工具调用时提供")


class AIAnalystService:
    """AI 数据分析师服务"""

    # 系统提示词将从外部 prompt 文件加载（支持热更新）
    SYSTEM_PROMPT = None  # 将在 _load_system_prompt() 中惰性初始化
    MAX_AGENT_STEPS = 30  # Agent 循环最大步数（LLM 工具调用轮次）

    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.query_service = QueryService(db)
        self._prompt_mgr = PromptManager()
        self._system_prompt_cache: Optional[str] = None

    def _load_system_prompt(self) -> str:
        """从外部文件加载系统提示词（支持热更新）"""
        if self._system_prompt_cache:
            return self._system_prompt_cache
        settings = get_settings()
        prompt_path = getattr(settings, 'ai_analyst_system_prompt_path', None) or "../prompts/ai_analyst/system_prompt.md"
        template = self._prompt_mgr.load_template(prompt_path, "ai_analyst_system")
        if template:
            self._system_prompt_cache = template
            return template
        # Fallback 硬编码
        logger.warning("AI Analyst system prompt 文件未找到，使用硬编码 fallback")
        return "你是一个专业的 AI 数据分析师。请帮助用户分析数据。"

    def _build_schema_hint(self, data_source_id: int) -> str:
        """获取数据库表结构摘要（用于在 SQL 失败时注入帮助 LLM）"""
        try:
            ds = self.ds_repo.get_by_id(data_source_id)
            if not ds:
                return ""
            from app.utils.db_executor import execute_query
            # 获取所有表名（最多 20 个）
            rows, cols = execute_query(ds, "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() LIMIT 20")
            if not rows:
                return ""
            lines = ["可用表:"]
            for row in rows[:20]:
                name = row[0] if isinstance(row, (list, tuple)) else row.get("TABLE_NAME", "")
                comment = row[1] if isinstance(row, (list, tuple)) else row.get("TABLE_COMMENT", "")
                lines.append(f"  - {name}  ({comment or '无注释'})")
            return "\n".join(lines)
        except Exception:
            return ""

    def _get_llm_client(self) -> LLMClient:
        """获取 LLM 客户端"""
        return get_llm_client()

    @staticmethod
    def _cache_key(message: str, data_source_id: int, group_id: Optional[int] = None) -> str:
        """生成语义缓存 key（精确匹配）"""
        raw = f"{message}:{data_source_id}:{group_id or ''}"
        return f"ai_analyst:cache:{hashlib.md5(raw.encode()).hexdigest()}"

    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """读取缓存"""
        try:
            r = get_redis()
            raw = r.get(cache_key)
            return raw.decode() if raw else None
        except Exception:
            return None

    def _set_cached_response(self, cache_key: str, response_text: str, ttl: int = 300):
        """写入缓存（默认 5 分钟）"""
        try:
            r = get_redis()
            r.setex(cache_key, ttl, response_text)
        except Exception:
            pass

    def _get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """获取对话历史（Redis），超 20 条时对早期消息做摘要"""
        try:
            r = get_redis()
            key = f"{_REDIS_CONVERSATION_PREFIX}{conversation_id}"
            raw = r.get(key)
            if not raw:
                return []
            history = json.loads(raw)
            # 滑动窗口：保留最近 10 轮，对早期做摘要
            if len(history) > MAX_HISTORY:
                recent = history[-MAX_HISTORY:]
                early = history[:-MAX_HISTORY]
                # 摘要格式
                summary = f"[历史摘要: 用户进行了 {len(early)//2} 轮对话后继续当前话题]"
                return [{"role": "system", "content": summary}] + recent
            return history
        except Exception:
            return []

    def _save_conversation_history(self, conversation_id: str, history: List[Dict[str, str]]):
        """保存对话历史（Redis）"""
        try:
            r = get_redis()
            key = f"{_REDIS_CONVERSATION_PREFIX}{conversation_id}"
            trimmed = history[-MAX_HISTORY * 2:]
            # TTL 24h，避免无限增长
            r.setex(key, 24 * 3600, json.dumps(trimmed, ensure_ascii=False, default=str))
        except Exception:
            # Redis 不可用时：不报错，保持系统可用性
            return


    def _build_tools_prompt(self, data_source_id: int) -> str:
        """从外部文件加载工具描述 prompt（支持热更新）"""
        settings = get_settings()
        prompt_path = getattr(settings, 'ai_analyst_tools_prompt_path', None) or "../prompts/ai_analyst/tools.md"
        template = self._prompt_mgr.load_template(prompt_path, "ai_analyst_tools")
        if template:
            # 注入 data_source_id
            return template.replace("{data_source_id}", str(data_source_id))
        logger.warning("AI Analyst tools prompt 文件未找到，使用精简 fallback")
        return f"可用工具: execute_sql, get_schema, generate_chart, analyze_data, list_metrics, query_metric (data_source_id={data_source_id})"
    # ── 工具执行 ──────────────────────────────────────────────────

    def execute_sql_tool(self, sql: str, data_source_id: int) -> Dict[str, Any]:
        """执行 SQL 查询工具"""
        # 验证 SQL 安全
        sql = strip_trailing_semicolon(sql)
        if has_forbidden_sql_tokens(sql):
            return {"success": False, "error": "SQL 验证失败: 不允许使用 QUALIFY", "columns": [], "rows": [], "total": 0}
        # 禁止直接查询 information_schema（应使用 get_schema 工具）
        sql_upper = sql.upper()
        if "FROM INFORMATION_SCHEMA" in sql_upper or "JOIN INFORMATION_SCHEMA" in sql_upper:
            return {"success": False, "error": "禁止直接查询 information_schema。请使用 get_schema 工具来获取表结构。", "columns": [], "rows": [], "total": 0}
        is_valid, msg = SQLValidator.validate(sql)
        if not is_valid:
            return {"success": False, "error": f"SQL 验证失败: {msg}", "columns": [], "rows": [], "total": 0}

        # 获取数据源
        ds = self.ds_repo.get_by_id(data_source_id)
        if not ds:
            return {"success": False, "error": "数据源不存在", "columns": [], "rows": [], "total": 0}

        if has_multi_level_table_reference(sql):
            return {"success": False, "error": "SQL 表名格式错误：只允许 库名.表名，不允许多级前缀", "columns": [], "rows": [], "total": 0}
        if has_foreign_schema_reference(sql, ds.database or ""):
            return {"success": False, "error": "SQL 表名不属于当前数据源", "columns": [], "rows": [], "total": 0}

        try:
            from app.utils.db_executor import execute_query
            rows, columns = execute_query(ds, sql)
            total = len(rows)
            # 限制返回数据量避免 token 爆炸，并把行数据转成 dict，保证图表能按字段名读取
            preview_rows = rows[:100]
            if preview_rows and columns:
                if not isinstance(preview_rows[0], dict):
                    preview_rows = [dict(zip(columns, row)) if isinstance(row, (list, tuple)) else row for row in preview_rows]
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

    def _is_admin_user(self, user_id: Optional[int]) -> bool:
        if user_id is None:
            return False
        try:
            user = self.db.query(User).filter_by(id=user_id).first()
            return bool(user and user.role and user.role.name == "admin")
        except Exception:
            return False

    def list_metrics_tool(self, data_source_id: int, user_id: Optional[int]) -> Dict[str, Any]:
        """列出当前用户可用的语义指标。"""
        if user_id is None:
            return {"success": False, "error": "缺少用户上下文", "metrics": []}

        try:
            metrics = SemanticMetricRepository(self.db).list_visible_for_data_source(
                data_source_id=data_source_id,
                user_id=user_id,
                is_admin=self._is_admin_user(user_id),
                limit=50,
                active_only=True,
            )
            return {
                "success": True,
                "metrics": [
                    {
                        "metric_key": metric.metric_key,
                        "name": metric.name,
                        "description": metric.description,
                        "metric_expression": metric.metric_expression,
                        "dimensions": metric.dimensions or [],
                        "time_column": metric.time_column,
                    }
                    for metric in metrics
                ],
                "total": len(metrics),
            }
        except Exception as e:
            logger.error(f"[AI-Analyst] 获取语义指标失败: {e}")
            return {"success": False, "error": str(e), "metrics": []}

    def query_metric_tool(
        self,
        metric_key: str,
        data_source_id: int,
        user_id: Optional[int],
        dimensions: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """按语义指标统一口径查询数据。"""
        if user_id is None:
            return {"success": False, "error": "缺少用户上下文", "columns": [], "rows": [], "total": 0}

        try:
            is_admin = self._is_admin_user(user_id)
            visible_metric = SemanticMetricRepository(self.db).get_visible_by_key(
                metric_key,
                user_id=user_id,
                is_admin=is_admin,
                active_only=True,
            )
            if not visible_metric:
                return {"success": False, "error": "指标不存在或已禁用", "columns": [], "rows": [], "total": 0}
            if visible_metric.data_source_id != data_source_id:
                return {"success": False, "error": "指标不属于当前数据源", "columns": [], "rows": [], "total": 0}

            metric, result = SemanticMetricQueryService(self.db).execute(
                SemanticMetricQueryRequest(
                    metric_key=metric_key,
                    start_time=start_time,
                    end_time=end_time,
                    dimensions=dimensions or [],
                    filters=filters or {},
                    page=page,
                    page_size=page_size,
                ),
                user_id=user_id,
                is_admin=is_admin,
            )
            return {
                "success": True,
                "metric": {
                    "metric_key": metric.metric_key,
                    "name": metric.name,
                    "dimensions": metric.dimensions or [],
                    "time_column": metric.time_column,
                },
                "columns": result.columns,
                "rows": result.rows[:100],
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "execution_time_ms": result.execution_time_ms,
                "preview_truncated": len(result.rows) > 100,
            }
        except Exception as e:
            logger.error(f"[AI-Analyst] 查询语义指标失败: {e}")
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
        series_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """生成 ECharts 图表配置（支持单系列/多系列）"""
        if not data:
            return {"success": False, "error": "无数据", "chart_config": None}

        # 从第一行数据推断列名
        if isinstance(data[0], dict):
            columns = list(data[0].keys())
        else:
            columns = [f"col_{i}" for i in range(len(data[0])) if isinstance(data[0], (list, tuple))]

        def _safe_get(row, field, cols):
            if isinstance(row, dict):
                if field in row:
                    return row[field]
                try:
                    idx = int(field)
                    keys = list(row.keys())
                    if 0 <= idx < len(keys):
                        return row[keys[idx]]
                except (ValueError, TypeError):
                    pass
                return None
            if field in cols:
                return row[cols.index(field)]
            try:
                idx = int(field)
                if 0 <= idx < len(row):
                    return row[idx]
            except (ValueError, TypeError, IndexError):
                pass
            return None

        x_axis_field, y_axis_field = infer_chart_axes(columns, data, x_axis_field, y_axis_field)

        x_data = [_safe_get(row, x_axis_field, columns) for row in data]
        # 去重保持顺序
        seen = set()
        x_unique = []
        for v in x_data:
            sv = str(v)
            if sv not in seen:
                seen.add(sv)
                x_unique.append(sv)

        # 预设颜色（12色，足够区分门店/品类）
        colors = [
            "#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de",
            "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc", "#1ab1ff",
            "#ff9f7f", "#b6a2de",
        ]

        # ── 多系列模式 ──────────────────────────────────────────
        if series_fields and len(series_fields) > 1:
            series_list = []
            legend_data = []
            for idx, sf in enumerate(series_fields):
                sf = str(sf)
                sdata = [_safe_get(row, sf, columns) for row in data]
                try:
                    sdata = [float(v) if v is not None else 0 for v in sdata]
                except (ValueError, TypeError):
                    pass
                series_list.append({
                    "name": sf,
                    "type": chart_type if chart_type in ("bar", "line", "scatter") else "line",
                    "data": sdata,
                    "smooth": chart_type == "line",
                    "symbol": "circle",
                    "symbolSize": 4,
                    "lineStyle": {"width": 2},
                    "itemStyle": {"color": colors[idx % len(colors)]},
                })
                legend_data.append(sf)

            chart_config = {
                "title": {"text": title or "多系列趋势图"},
                "tooltip": {
                    "trigger": "axis",
                    "backgroundColor": "rgba(255,255,255,0.95)",
                    "borderColor": "#e4e7ed",
                    "borderWidth": 1,
                    "textStyle": {"color": "#303133", "fontSize": 13},
                },
                "legend": {
                    "data": legend_data,
                    "top": 8,
                    "textStyle": {"fontSize": 12},
                    "type": "scroll",
                },
                "grid": {"left": 72, "right": 32, "bottom": 60, "top": 52},
                "xAxis": {
                    "type": "category",
                    "data": x_unique,
                    "axisLabel": {"rotate": 30, "fontSize": 11},
                },
                "yAxis": {
                    "type": "value",
                    "name": title or "值",
                    "nameTextStyle": {"fontSize": 12},
                    "axisLabel": {"fontSize": 11},
                    "splitLine": {"lineStyle": {"type": "dashed", "color": "#f0f2f5"}},
                },
                "dataZoom": [
                    {"type": "inside", "start": 0, "end": 100},
                    {"type": "slider", "start": 0, "end": 100, "height": 20, "bottom": 8},
                ],
                "series": series_list,
            }
            return {
                "success": True,
                "chart_config": chart_config,
                "chart_type": chart_type,
                "series_count": len(series_fields),
            }

        # ── 单系列（单条线/柱） ─────────────────────────────────
        y_data = [_safe_get(row, y_axis_field, columns) for row in data]
        try:
            y_data = [float(v) if v is not None else 0 for v in y_data]
        except (ValueError, TypeError):
            pass

        series_name = y_axis_field

        chart_config = {
            "title": {"text": title or f"{y_axis_field} by {x_axis_field}"},
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [series_name]},
            "xAxis": {"type": "category", "data": ["未命名" if v is None else str(v) for v in x_data]},
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
                "series": [{"type": "pie", "data": pie_data}],
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

    @staticmethod
    def _extract_json_obj(text: str) -> Optional[Dict[str, Any]]:
        """提取文本中第一个包含 JSON 对象的完整内容"""
        brace_start = text.find("{")
        if brace_start == -1:
            return None
        depth = 0
        in_string = False
        escaped = False
        for idx in range(brace_start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped: escaped = False
                elif ch == "\\": escaped = True
                elif ch == '"': in_string = False
                continue
            if ch == '"': in_string = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:idx + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    def _extract_action_via_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """
        当 LLM 输出未包含合法 tool JSON 时，使用 LLM 自身提取工具调用。
        避免脆弱的正则匹配。
        """
        # 仅当文本包含明显的工具调用意图时才触发二次 LLM 调用
        tool_keywords = ["SELECT", "FROM", "DESCRIBE", "SHOW TABLES", "SHOW COLUMNS",
                         "execute_sql", "get_schema", "generate_chart", "data_source_id"]
        if not any(kw in text.upper() for kw in tool_keywords):
            logger.info("[AI-Analyst] LLM reformat: 文本无工具关键词，跳过")
            return None

        logger.info("[AI-Analyst] LLM reformat: 触发二次LLM调用，文本前200chars=%s", text[:200].replace("\n", " "))
        try:
            reformat_prompt = (
                "从以下文本中提取工具调用。如果有 SQL 查询意图，输出 JSON: "
                '{"tool": "execute_sql", "input": {"sql": "...", "data_source_id": N}}。'
                "如果有查看表结构意图，输出 JSON: "
                '{"tool": "get_schema", "input": {"data_source_id": N, "table_name": "..."}}。'
                "如果没有明显的工具调用意图，输出: {}。\n\n"
                f"文本:\n{text[:2000]}"
            )
            llm_client = self._get_llm_client()
            result = llm_client.chat(
                [{"role": "user", "content": reformat_prompt}],
                temperature=0.0,
            )
            import re as _re
            json_match = _re.search(r'\{.*\}', result, _re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                tool = parsed.get("tool")
                inp = parsed.get("input", {})
                if tool == "execute_sql" and inp.get("sql"):
                    logger.info("[AI-Analyst] LLM reformat ✅ 提取到 execute_sql")
                    return {"tool": "execute_sql", "input": inp,
                            "_smart_fallback": True, "_text_before": text.split("\n")[0].strip()}
                if tool == "get_schema" and inp.get("data_source_id"):
                    logger.info("[AI-Analyst] LLM reformat ✅ 提取到 get_schema")
                    return {"tool": "get_schema", "input": inp,
                            "_smart_fallback": True, "_text_before": text.split("\n")[0].strip()}
                if tool == "generate_chart" and inp.get("data"):
                    logger.info("[AI-Analyst] LLM reformat ✅ 提取到 generate_chart")
                    return {"tool": "generate_chart", "input": inp,
                            "_smart_fallback": True, "_text_before": ""}
            else:
                logger.info("[AI-Analyst] LLM reformat: 未提取到JSON或结果为{}")
        except Exception as e:
            logger.warning("[AI-Analyst] LLM reformat 失败: %s", e)
        return None

    def _parse_json_as_action(self, obj: Dict[str, Any], full_text: str) -> Optional[Dict[str, Any]]:
        """将 LLM 输出的 JSON 对象映射为工具调用 action"""
        # 标准格式: {"tool": "xxx", "input": {...}}
        if "tool" in obj and "input" in obj:
            return {"tool": obj["tool"], "input": obj["input"],
                    "_smart_fallback": False, "_text_before": ""}

        # 格式1: {"sql": "...", "data_source_id": N} → execute_sql
        if "sql" in obj and "data_source_id" in obj:
            sql = obj["sql"].strip()
            sql = sql.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            if sql.upper().startswith("SELECT") or sql.upper().startswith("WITH"):
                return {"tool": "execute_sql", "input": {"sql": sql, "data_source_id": obj["data_source_id"]},
                        "_smart_fallback": True, "_text_before": ""}

        # 格式2: {"table_name": "...", "data_source_id": N} → get_schema
        if "table_name" in obj and "data_source_id" in obj:
            return {"tool": "get_schema", "input": {"data_source_id": obj["data_source_id"], "table_name": obj["table_name"]},
                    "_smart_fallback": True, "_text_before": ""}

        return None

    def _parse_action(self, text: str) -> Optional[Dict[str, Any]]:
        """从 LLM 输出中解析 ACTION: {...} 指令"""
        import re

        def extract_balanced_json(source: str, start: int) -> Optional[str]:
            brace_start = source.find("{", start)
            if brace_start == -1:
                return None

            depth = 0
            in_string = False
            escaped = False
            for index in range(brace_start, len(source)):
                char = source[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        in_string = False
                    continue

                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return source[brace_start:index + 1]
            return None

        # 匹配 ACTION: 后面的完整 JSON 对象。不能用非贪婪正则截取，
        # 因为工具参数本身会包含嵌套对象，例如 {"input": {"data_source_id": 10}}。
        match = re.search(r'ACTION:\s*', text, re.DOTALL)
        if match:
            json_text = extract_balanced_json(text, match.end())
            if not json_text:
                return None
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                return None

        # 也匹配 ```json\n{...}\n``` 格式
        match = re.search(r'```json\s*', text, re.DOTALL)
        if match:
            json_text = extract_balanced_json(text, match.end())
            if not json_text:
                return None
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                return None

        # ── 智能回退：提取 JSON 或使用 LLM 自身提取工具调用（避免正则） ──
        json_obj = self._extract_json_obj(text)
        if json_obj:
            result = self._parse_json_as_action(json_obj, text)
            if result:
                return result

        # 以上均未匹配 → 用 LLM 自身提取工具调用
        return self._extract_action_via_llm(text)

    def _execute_tool(
        self,
        action: Dict[str, Any],
        data_source_id: int,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
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
                series_fields=tool_input.get("series_fields"),
            )
        elif tool_name == "analyze_data":
            return self.analyze_data_tool(
                data=tool_input.get("data", []),
                columns=tool_input.get("columns", []),
                question=tool_input.get("question", ""),
            )
        elif tool_name == "list_metrics":
            return self.list_metrics_tool(
                data_source_id=tool_input.get("data_source_id", data_source_id),
                user_id=user_id,
            )
        elif tool_name == "query_metric":
            return self.query_metric_tool(
                metric_key=tool_input.get("metric_key", ""),
                data_source_id=tool_input.get("data_source_id", data_source_id),
                user_id=user_id,
                dimensions=tool_input.get("dimensions") or [],
                start_time=tool_input.get("start_time"),
                end_time=tool_input.get("end_time"),
                filters=tool_input.get("filters") or {},
                page=tool_input.get("page", 1),
                page_size=tool_input.get("page_size", 50),
            )
        else:
            return {"success": False, "error": f"未知工具: {tool_name}"}

    def _compact_tool_result_for_llm(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """压缩工具结果，避免大 schema/结果集被硬截断后误导 LLM。"""
        if tool_name != "get_schema" or not result.get("success"):
            return result

        compact_tables = []
        for table in result.get("tables", []):
            columns = table.get("columns", [])
            preview_columns = [
                column.get("column")
                for column in columns[:100]
                if isinstance(column, dict) and column.get("column")
            ]
            compact_tables.append({
                "table_name": table.get("table_name"),
                "column_count": len(columns),  # 保留总数让 LLM 知道表规模
                "columns_preview": preview_columns,
                "columns_truncated": len(columns) > 100,
            })

        return {
            "success": True,
            "total_count": result.get("total_count", len(compact_tables)),
            "tables": compact_tables,
            "note": f"已展示前 100 个字段（共 {sum(t['column_count'] for t in compact_tables)} 个字段）。字段预览已足够判断可用列，请直接使用 execute_sql 查询数据，不要再重复调用 get_schema。如需进行门店名查询，请 JOIN dim_store 维表而非在事实表中查找门店名。",
        }

    def _format_tool_output(self, tool_name: str, result: Dict[str, Any], limit: int = 12000) -> str:
        compact_result = self._compact_tool_result_for_llm(tool_name, result)
        return json.dumps(compact_result, ensure_ascii=False, default=str)[:limit]

    def chat(
        self,
        message: str,
        data_source_id: int,
        conversation_id: Optional[str] = None,
        group_id: Optional[int] = None,
        user_id: Optional[int] = None,
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

        # 精确缓存检查
        cache_key = self._cache_key(message, data_source_id, group_id)
        cached = self._get_cached_response(cache_key)
        if cached:
            return AIAnalystChatResponse(
                conversation_id=conversation_id,
                message=AIAnalystMessage(
                    role="assistant",
                    content=cached,
                ),
            )

        history = self._get_conversation_history(conversation_id)
        tools_prompt = self._build_tools_prompt(data_source_id)
        semantic_context = build_semantic_runtime_context(self.db, data_source_id, message, max_chars=0)

        # 构建完整对话
        system_prompt = self._load_system_prompt()
        system_msg = (
            system_prompt + "\n\n"
            + tools_prompt + "\n\n"
            + "### 语义层文档（必须优先阅读，这是数据逻辑的唯一权威来源）\n\n"
            + semantic_context
        )
        if group_id:
            system_msg += f"\n\n当前集团ID: {group_id}"

        messages = [{"role": "system", "content": system_msg}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        # Agent 循环（最多 15 轮工具调用）
        chart_config = None
        tool_calls = []
        all_text = []
        last_successful_result = None
        for step in range(self.MAX_AGENT_STEPS):
            llm_client = self._get_llm_client()
            try:
                # 优先使用结构化输出（格式保证），不支持时回退文本解析
                action = None
                if llm_client.supports_structured_output:
                    try:
                        structured = llm_client.chat_structured(messages, AgentAction, temperature=0.0)
                        if structured.get("tool") and structured.get("tool_input"):
                            action = {"tool": structured["tool"], "input": structured["tool_input"]}
                        else:
                            response_text = structured.get("final_answer") or structured.get("thought", "")
                    except Exception:
                        # 结构化失败，回退文本
                        response_text = llm_client.chat(messages, temperature=0.0)
                        action = self._parse_action(response_text)
                else:
                    response_text = llm_client.chat(messages, temperature=0.0)
                    action = self._parse_action(response_text)
            except LLMError as e:
                return AIAnalystChatResponse(
                    conversation_id=conversation_id,
                    message=AIAnalystMessage(
                        role="assistant",
                        content=f"抱歉，AI 服务暂时不可用: {e}",
                    ),
                )

            # 没有工具调用则直接返回
            if action is None:
                # 没有工具调用，直接返回
                all_text.append(response_text)
                self._set_cached_response(cache_key, response_text)
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
            tool_result = self._execute_tool(action, data_source_id, user_id=user_id)

            tool_calls.append(AIAnalystToolCall(
                tool_name=tool_name,
                tool_input=action.get("input", {}),
                tool_output=self._format_tool_output(tool_name, tool_result, limit=4000),
            ))

            # 记录最后一次成功的 SQL 结果（用于 fallback）
            if tool_name == "execute_sql" and tool_result.get("success"):
                last_successful_result = tool_result

            # 提取图表配置
            if tool_name == "generate_chart" and tool_result.get("success"):
                chart_config = tool_result.get("chart_config")

            # 将工具结果反馈给 LLM
            tool_feedback = f"工具 [{tool_name}] 执行结果:\n{self._format_tool_output(tool_name, tool_result)}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": tool_feedback})

        # 达到最大轮次 — 尝试用最后一次结果生成总结
        if last_successful_result:
            rows = last_successful_result.get("rows", [])
            columns = last_successful_result.get("columns", [])
            if rows:
                preview = json.dumps(rows[:10], ensure_ascii=False, default=str)[:2000]
                final_content = f"查询完成，共 {last_successful_result.get('total', len(rows))} 条结果（仅显示前 {min(10, len(rows))} 条）：\n\n列: {columns}\n数据: {preview}"
            else:
                final_content = "查询完成，但结果为空。"
        else:
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
        user_id: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天接口（SSE）

        Yields dict with 'type' key: token / tool_call / tool_result / chart / done / error
        """
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        history = self._get_conversation_history(conversation_id)
        tools_prompt = self._build_tools_prompt(data_source_id)
        semantic_context = build_semantic_runtime_context(self.db, data_source_id, message, max_chars=0)

        system_prompt = self._load_system_prompt()
        system_msg = (
            system_prompt + "\n\n"
            + tools_prompt + "\n\n"
            + "### 语义层文档（必须优先阅读，这是数据逻辑的唯一权威来源）\n\n"
            + semantic_context
        )
        if group_id:
            system_msg += f"\n\n当前集团ID: {group_id}"

        messages = [{"role": "system", "content": system_msg}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        chart_config = None
        all_tool_calls = []
        all_text = []
        last_successful_result = None
        sql_fail_count = 0  # 连续 SQL 失败次数

        for step in range(self.MAX_AGENT_STEPS):
            llm_client = self._get_llm_client()

            # ── LLM 调用日志 ──
            msg_count = len(messages)
            total_chars = sum(len(m.get("content", "")) for m in messages)
            last_user = next((m["content"][:80] for m in reversed(messages) if m["role"] == "user"), "")
            logger.info("[AI-Analyst] ═══ LLM 调用 #%02d ═══ messages=%d total_chars=%d query=%s",
                         step + 1, msg_count, total_chars, last_user.replace("\n", " "))

            try:
                # 流式调用 LLM，逐 token yield 的同时累积完整文本
                stream_buffer = []
                token_count = 0
                async for token in self._stream_llm_call(llm_client, messages):
                    stream_buffer.append(token)
                    token_count += 1
                response_text = "".join(stream_buffer)
                logger.info("[AI-Analyst] 📥 LLM 响应 #%02d | tokens=%d chars=%d | preview=%s",
                             step + 1, token_count, len(response_text),
                             response_text[:150].replace("\n", " "))
            except Exception as e:
                logger.error("[AI-Analyst] ❌ LLM 调用 #%02d 失败: %s", step + 1, e)
                yield {"type": "error", "error": str(e)}
                return

            # 检查是否有工具调用
            action = self._parse_action(response_text)
            logger.info("[AI-Analyst] 🔧 step=%d/%d action=%s",
                         step + 1, self.MAX_AGENT_STEPS,
                         action.get("tool") if action else "NONE(最终回答)")

            # 智能回退时：先输出文字部分，再执行工具
            smart_fallback = False
            if action and action.get("_smart_fallback"):
                smart_fallback = True
                text_before = action.pop("_text_before", "")
                if text_before.strip():
                    # 先推送文字部分
                    all_text.append(text_before)
                    yield {"type": "token", "content": text_before}
                # 真正的 tool action 去掉回退标记
                clean_action = {"tool": action["tool"], "input": action["input"]}
                action = clean_action

            if action is None:
                logger.info("[AI-Analyst] ✅ 最终回答 step=%d, 共 %d tokens", step + 1, len(stream_buffer))
                # 真流式：逐 token 推送
                all_text.append(response_text)
                for token in stream_buffer:
                    yield {"type": "token", "content": token}

                self._save_conversation_history(conversation_id, [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response_text},
                ])
                yield {"type": "done", "conversation_id": conversation_id}
                return

            # 执行工具
            tool_name = action.get("tool", "unknown")
            tool_input = action.get("input", {})
            logger.info("[AI-Analyst] 🛠️  step=%d 调用工具: %s | input=%s",
                         step + 1, tool_name,
                         json.dumps(tool_input, ensure_ascii=False)[:200])
            yield {"type": "tool_call", "tool_name": tool_name, "tool_input": tool_input}

            tool_result = self._execute_tool(action, data_source_id, user_id=user_id)
            tool_status = "✅" if tool_result.get("success") else "❌"
            logger.info("[AI-Analyst] %s step=%d %s 结果 | success=%s rows=%d | error=%s",
                         tool_status, step + 1, tool_name,
                         tool_result.get("success"),
                         len(tool_result.get("rows", []) or []),
                         (tool_result.get("error", "") or "")[:120])
            tool_output = self._format_tool_output(tool_name, tool_result, limit=4000)
            yield {"type": "tool_result", "tool_name": tool_name, "tool_output": tool_output}

            tool_calls_record = {
                "tool_name": tool_name,
                "tool_input": action.get("input", {}),
                "tool_output": tool_output,
            }
            all_tool_calls.append(tool_calls_record)

            # SQL 失败处理：自动注入 schema + 指导
            if tool_name == "execute_sql":
                if tool_result.get("success"):
                    sql_fail_count = 0
                    last_successful_result = tool_result
                else:
                    error_msg = tool_result.get("error", "")
                    sql_fail_count += 1

                    # 首次失败：提取表名，自动注入该表 schema
                    if sql_fail_count <= 2:
                        import re as _re
                        table_in_error = _re.search(r'FROM\s+(\S+)', response_text, _re.IGNORECASE)
                        table_name = table_in_error.group(1).split(".")[-1].strip("`\"'") if table_in_error else None
                        if table_name:
                            schema_info = self.get_schema_tool(data_source_id, table_name=table_name)
                            if schema_info.get("success"):
                                schema_text = json.dumps(schema_info.get("tables", []), ensure_ascii=False, default=str)[:3000]
                                hint = f"表 `{table_name}` 的结构如下:\n{schema_text}\n\n注意: 门店名不在事实表中，需要 JOIN dim_store 维表获取。请基于此表结构重新编写 SQL。"
                                messages.append({"role": "system", "content": hint})
                                yield {"type": "tool_result", "tool_name": "system", "tool_output": f"已注入 `{table_name}` 表结构"}

                    # 第3次失败：注入完整数据库表列表
                    if sql_fail_count == 3:
                        schema_hint = self._build_schema_hint(data_source_id)
                        if schema_hint:
                            messages.append({"role": "system", "content": f"## 完整表结构参考\n{schema_hint}\n\n请基于以上表结构重新编写正确的 SQL。注意：1) SELECT 非聚合字段必须出现在 GROUP BY 中 2) 门店名需要 JOIN dim_store 获取"})
                            yield {"type": "tool_result", "tool_name": "system", "tool_output": "已注入全部表结构信息"}

            if tool_name == "generate_chart" and tool_result.get("success"):
                chart_config = tool_result.get("chart_config")
                yield {"type": "chart", "chart_config": chart_config}

            # 反馈给 LLM
            tool_feedback = f"工具 [{tool_name}] 执行结果:\n{self._format_tool_output(tool_name, tool_result)}"
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": tool_feedback})

        # 达到最大轮次 — 如果有成功结果，发送 fallback 数据
        if last_successful_result:
            rows = last_successful_result.get("rows", [])
            columns = last_successful_result.get("columns", [])
            if rows:
                preview = json.dumps(rows[:10], ensure_ascii=False, default=str)[:2000]
                fallback_text = f"查询完成，共 {last_successful_result.get('total', len(rows))} 条结果（仅显示前 {min(10, len(rows))} 条）：\n\n列: {columns}\n数据: {preview}"
            else:
                fallback_text = "查询完成，但结果为空。"
            yield {"type": "token", "content": fallback_text}
        yield {"type": "done", "conversation_id": conversation_id}

    async def _stream_llm_call(self, llm_client: LLMClient, messages: List[Dict[str, str]]):
        """
        流式调用 LLM，逐 token yield。

        调用方 collect tokens 即得完整文本。
        """
        try:
            for token in llm_client.chat_stream(messages, temperature=0.0):
                yield token
        except Exception as e:
            logger.error("[AI-Analyst] stream error: %s", e)
            raise

    # ── Schema 查询 ──────────────────────────────────────────────

    def get_schema(self, data_source_id: int, table_name: Optional[str] = None) -> Dict[str, Any]:
        """获取表结构"""
        return self.get_schema_tool(data_source_id, table_name)
