# backend/app/services/ai_analyst_service.py
"""
AI 数据分析师服务 v2 — 增强版

改进:
- P0-1: 原生工具调用 (chat_with_tools) 替代 JSON 文本协议
- P0-2: 数据预处理层 — execute_sql 自动统计摘要
- P0-3: LLM 多轮对话语义摘要
- P1-4: 洞察主动推送 — 自动检测趋势/异常/相关性
- P1-5: 图表类型扩展 — heatmap/treemap/waterfall/boxplot/dual-axis
- P1-6: SQL 优化建议 — 执行后质量检查
- P2-8: 联邦查询 — query_metric 支持跨数据源
- P2-9: 解读分级 — 动态 system prompt 复杂度分级
- P2-11: 语义缓存升级 — embedding 语义相似度缓存
"""
import json
import uuid
import logging
import hashlib
import re
import statistics
import time
from typing import Optional, List, Dict, Any, AsyncGenerator
from collections import Counter
from sqlalchemy.orm import Session

from app.config import get_settings
from app.utils.llm_client import LLMClient, LLMError, get_llm_client, ToolDefinition
from app.services.query_service import QueryService
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.semantic_metric_repository import SemanticMetricRepository
from app.utils.sql_validator import SQLValidator
from app.utils.sql_normalizer import strip_trailing_semicolon, has_multi_level_table_reference, has_forbidden_sql_tokens
from app.schemas.ai_analyst import AIAnalystChatResponse, AIAnalystMessage, AIAnalystToolCall
from app.schemas.query import SQLQueryRequest
from pydantic import BaseModel, Field
from app.schemas.semantic_metric import SemanticMetricQueryRequest
from app.services.semantic_metric_query_service import SemanticMetricQueryService
from app.utils.semantic_runtime_context import build_semantic_runtime_context
from app.utils.chart_axis_inference import infer_chart_axes
from app.models.user import User
from app.core.redis import get_redis
from app.services.nl2sql.prompt_utils import PromptManager

logger = logging.getLogger(__name__)

MAX_HISTORY = 20
_REDIS_CONVERSATION_PREFIX = "ai_analyst:conversation:"
_SEMANTIC_CACHE_PREFIX = "ai_analyst:semcache:"

LEVEL_SIMPLE = "simple"
LEVEL_COMPARE = "compare"
LEVEL_ATTRIBUTION = "attribution"
LEVEL_PREDICT = "predict"


class AIAnalystService:
    """AI 数据分析师服务 v2"""

    MAX_AGENT_STEPS = 30

    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.query_service = QueryService(db)
        self._prompt_mgr = PromptManager()
        self._system_prompt_cache: Optional[str] = None

    # ── Prompt 加载 ──────────────────────────────────

    def _load_system_prompt(self, level: str = LEVEL_SIMPLE) -> str:
        base = self._load_base_system_prompt()
        instructions = {
            LEVEL_SIMPLE: "\n## L1 — 简单查询\n直接用 SQL 获取结果返回，不要做不必要的深度分析。",
            LEVEL_COMPARE: "\n## L2 — 比较分析\n自动计算增长率/变化率，生成对比图表，给出增长/下降结论。",
            LEVEL_ATTRIBUTION: "\n## L3 — 归因分析\n获取整体指标，按下钻维度拆解贡献度，找出最大贡献因子，展示拆解结果。",
            LEVEL_PREDICT: "\n## L4 — 预测分析\n获取历史数据，分析趋势，给出预测结论。",
        }
        return base + instructions.get(level, instructions[LEVEL_SIMPLE])

    def _load_base_system_prompt(self) -> str:
        if self._system_prompt_cache:
            return self._system_prompt_cache
        settings = get_settings()
        prompt_path = getattr(settings, 'ai_analyst_system_prompt_path', None) or "prompts/ai_analyst/system_prompt.md"
        template = self._prompt_mgr.load_template(prompt_path, "ai_analyst_system")
        if template:
            self._system_prompt_cache = template
            return template
        return "你是一个专业的 AI 数据分析师。请帮助用户分析数据。"

    def _detect_complexity_level(self, message: str) -> str:
        msg = message.lower()
        if any(k in msg for k in ["预测", "预估", "趋势", "forecast", "predict", "未来"]):
            return LEVEL_PREDICT
        if any(k in msg for k in ["原因", "为什么", "归因", "贡献", "影响", "root cause", "why"]):
            return LEVEL_ATTRIBUTION
        if any(k in msg for k in ["同比", "环比", "对比", "比较", "增长", "变化", "vs", "versus"]):
            return LEVEL_COMPARE
        return LEVEL_SIMPLE

    def _build_schema_hint(self, ds_id: int) -> str:
        try:
            ds = self.ds_repo.get_by_id(ds_id)
            if not ds:
                return ""
            from app.utils.db_executor import execute_query
            rows, _ = execute_query(
                ds, "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() LIMIT 20"
            )
            if not rows:
                return ""
            lines = ["可用表:"]
            for r in rows[:20]:
                name = r[0] if isinstance(r, (list, tuple)) else r.get("TABLE_NAME", "")
                cmt = r[1] if isinstance(r, (list, tuple)) else r.get("TABLE_COMMENT", "")
                lines.append(f"  - {name}  ({cmt or '无注释'})")
            return "\n".join(lines)
        except Exception:
            return ""

    def _get_llm_client(self) -> LLMClient:
        return get_llm_client()

    # ── 工具定义 ──────────────────────────────────

    def _build_tool_definitions(self, ds_id: int) -> List[ToolDefinition]:
        return [
            ToolDefinition(name="execute_sql", description="执行 SELECT 查询。尽量在一个 SQL 中完成所有计算。",
                           parameters={"type": "object", "properties": {
                               "sql": {"type": "string", "description": "SELECT 语句"},
                               "data_source_id": {"type": "integer", "description": "数据源 ID"}},
                               "required": ["sql", "data_source_id"]}),
            ToolDefinition(name="get_schema", description="仅当语义层文档未覆盖表结构时，补充获取表名和列名",
                           parameters={"type": "object", "properties": {
                               "data_source_id": {"type": "integer", "description": "数据源 ID"},
                               "table_name": {"type": "string", "description": "表名（可选）"}},
                               "required": ["data_source_id"]}),
            ToolDefinition(name="generate_chart",
                           description="生成 ECharts 图表。类型: bar, line, pie, scatter, heatmap, treemap, waterfall, boxplot, dual-axis",
                           parameters={"type": "object", "properties": {
                               "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "scatter", "heatmap", "treemap", "waterfall", "boxplot", "dual-axis"]},
                               "data": {"type": "array"}, "x_axis_field": {"type": "string"},
                               "y_axis_field": {"type": "string"}, "title": {"type": "string"},
                               "series_fields": {"type": "array", "items": {"type": "string"}}},
                               "required": ["chart_type", "data", "x_axis_field", "y_axis_field"]}),
            ToolDefinition(name="list_metrics", description="列出当前数据源下用户可用的语义指标",
                           parameters={"type": "object", "properties": {
                               "data_source_id": {"type": "integer"}}, "required": ["data_source_id"]}),
            ToolDefinition(name="query_metric",
                           description="按语义指标查询数据。支持 alternate_ds_id 跨数据源联邦查询",
                           parameters={"type": "object", "properties": {
                               "metric_key": {"type": "string"}, "data_source_id": {"type": "integer"},
                               "dimensions": {"type": "array", "items": {"type": "string"}},
                               "start_time": {"type": "string"}, "end_time": {"type": "string"},
                               "filters": {"type": "object"},
                               "alternate_ds_id": {"type": "integer", "description": "联邦查询时指定其他数据源 ID"}},
                               "required": ["metric_key", "data_source_id"]}),
            ToolDefinition(name="analyze_data", description="对已有数据做统计分析",
                           parameters={"type": "object", "properties": {
                               "data": {"type": "array"}, "columns": {"type": "array", "items": {"type": "string"}},
                               "question": {"type": "string"}}, "required": ["data", "columns"]}),
        ]

    # ── 缓存 ──────────────────────────────────────

    @staticmethod
    def _cache_key(msg: str, ds_id: int, gid: int = None, user_id: int = None) -> str:
        payload = f"{msg}:{ds_id}:{gid or ''}:{user_id or ''}"
        return f"ai_analyst:cache:{hashlib.md5(payload.encode()).hexdigest()}"

    def _get_cached_response(self, key: str) -> Optional[str]:
        try:
            r = get_redis()
            raw = r.get(key)
            return raw.decode() if raw else None
        except Exception:
            return None

    def _set_cached_response(self, key: str, text: str, ttl: int = 300):
        try:
            r = get_redis()
            r.setex(key, ttl, text)
        except Exception:
            pass

    def _get_semantic_cache(self, message: str, ds_id: int, user_id: int, threshold: float = 0.92) -> Optional[str]:
        try:
            r = get_redis()
            llm = self._get_llm_client()
            qemb = llm.get_embedding(message)
            if not qemb:
                return None
            items = r.hgetall(f"{_SEMANTIC_CACHE_PREFIX}index:{user_id}:{ds_id}")
            if not items:
                return None
            best_score, best_ans = 0.0, None
            for _, v in items.items():
                try:
                    e = json.loads(v)
                    cemb, cans = e.get("embedding", []), e.get("answer", "")
                    if not cemb or not cans:
                        continue
                    dot = sum(a * b for a, b in zip(qemb, cemb))
                    nq = sum(a * a for a in qemb) ** 0.5
                    nc = sum(a * a for a in cemb) ** 0.5
                    if nq == 0 or nc == 0:
                        continue
                    score = dot / (nq * nc)
                    if score > best_score:
                        best_score, best_ans = score, cans
                except Exception:
                    continue
            if best_score >= threshold and best_ans:
                return best_ans
        except Exception:
            pass
        return None

    def _set_semantic_cache(self, message: str, answer: str, ds_id: int, user_id: int, ttl: int = 3600):
        try:
            llm = self._get_llm_client()
            qemb = llm.get_embedding(message)
            if not qemb:
                return
            r = get_redis()
            key = f"{_SEMANTIC_CACHE_PREFIX}index:{user_id}:{ds_id}"
            entry = {"question": message, "answer": answer, "embedding": qemb, "ts": time.time()}
            r.hset(key, hashlib.md5(message.encode()).hexdigest(), json.dumps(entry, ensure_ascii=False))
            r.expire(key, ttl)
        except Exception:
            pass

    # ── 对话历史 ──────────────────────────────────

    def _get_conversation_history(self, cid: str) -> List[Dict[str, str]]:
        try:
            r = get_redis()
            raw = r.get(f"{_REDIS_CONVERSATION_PREFIX}{cid}")
            if not raw:
                return []
            history = json.loads(raw)
            if len(history) > MAX_HISTORY:
                recent = history[-MAX_HISTORY:]
                early = history[:-MAX_HISTORY]
                llm = self._get_llm_client()
                summary = llm._summarize_messages(early, max_tokens=300)
                return [{"role": "system", "content": f"[历史对话摘要]\n{summary}"}] + recent
            return history
        except Exception:
            return []

    def _save_conversation_history(self, cid: str, history: List[Dict[str, str]]):
        try:
            r = get_redis()
            r.setex(f"{_REDIS_CONVERSATION_PREFIX}{cid}", 86400,
                    json.dumps(history[-MAX_HISTORY * 2:], ensure_ascii=False, default=str))
        except Exception:
            pass

    # ── 工具 prompt ──────────────────────────────

    def _build_tools_prompt(self, ds_id: int) -> str:
        s = get_settings()
        path = getattr(s, 'ai_analyst_tools_prompt_path', None) or "prompts/ai_analyst/tools.md"
        tpl = self._prompt_mgr.load_template(path, "ai_analyst_tools")
        return tpl.replace("{data_source_id}", str(ds_id)) if tpl else ""

    # ── SQL 预检 ──────────────────────────────────

    def _precheck_sql(self, sql: str) -> Optional[str]:
        agg_fns = ["SUM", "COUNT", "AVG", "MAX", "MIN", "GROUP_CONCAT"]
        has_agg = any(re.search(rf"\b{fn}\s*\(", sql, re.I) for fn in agg_fns)
        if has_agg and "GROUP BY" not in sql.upper() and "SELECT" in sql.upper():
            return "聚合查询必须包含 GROUP BY 所有非聚合字段"
        return None

    # ── SQL 执行（P0-2 + P1-4 + P1-6） ────────────

    def execute_sql_tool(self, sql: str, data_source_id: int, user_id: int = None) -> Dict[str, Any]:
        if user_id is None:
            return {"success": False, "error": "缺少用户上下文"}
        sql = strip_trailing_semicolon(sql)
        if has_forbidden_sql_tokens(sql):
            return {"success": False, "error": "不允许使用 QUALIFY"}
        if "FROM INFORMATION_SCHEMA" in sql.upper() or "JOIN INFORMATION_SCHEMA" in sql.upper():
            return {"success": False, "error": "禁止查询 information_schema，请用 get_schema"}
        pre = self._precheck_sql(sql)
        if pre:
            return {"success": False, "error": f"SQL 预检失败: {pre}"}
        ok, msg = SQLValidator.validate(sql)
        if not ok:
            return {"success": False, "error": f"SQL 验证失败: {msg}"}
        if has_multi_level_table_reference(sql):
            return {"success": False, "error": "表名格式错误，只允许 库名.表名"}
        try:
            response = self.query_service.execute_sql(
                SQLQueryRequest(
                    data_source_id=data_source_id,
                    sql=sql,
                    page=1,
                    page_size=2000,
                    skip_deep_pagination_check=True,
                ),
                user_id=user_id,
            )
            rows, cols = response.rows, response.columns
        except Exception as e:
            return {"success": False, "error": f"SQL 执行失败: {e}", "columns": [], "rows": [], "total": 0}
        if not rows:
            return {"success": True, "columns": cols or [], "rows": [], "total": 0}
        result = {"success": True, "columns": cols, "rows": rows[:2000], "total": len(rows),
                  "truncated": len(rows) > 2000, "execution_time_ms": 0}

        insights = self._auto_statistical_summary(cols, rows)
        patterns = self._auto_detect_patterns(cols, rows)
        warns = self._check_sql_quality(sql, result)

        # ── 自学习: 成功后自动保存为 SQL 修正案例（仅保存非全表扫描的查询） ──
        if "WHERE" in sql.upper() or "LIMIT" in sql.upper() or "GROUP BY" in sql.upper():
            try:
                self._save_sql_learning_case(
                    ds_id=data_source_id, sql=sql, rows=rows, cols=cols,
                    insights=insights, patterns=patterns, warns=warns
                )
            except Exception:
                pass
        # P0-2: 自动统计
        if insights:
            result["_auto_insights"] = insights
        # P1-4: 模式检测
        if patterns:
            result["_auto_patterns"] = patterns
        # P1-6: 质量检查
        if warns:
            result["_sql_quality_warnings"] = warns
        return result

    # ── 自学习: 保存成功 SQL 案例 ────────────────────

    def _save_sql_learning_case(self, ds_id: int, sql: str, rows: List,
                                 cols: List[str] = None, insights: Optional[Dict] = None,
                                 patterns: Optional[List] = None, warns: Optional[List] = None):
        """将成功执行的 SQL 保存为学习案例（自动去重）"""
        from app.services.sql_correction_service import SqlCorrectionService
        quality_tags = []
        if warns:
            quality_tags.extend(w[:10] for w in warns)
        if patterns:
            quality_tags.extend(p.get("type", "") for p in patterns[:2])
        feedback = f"成功执行, 返回{len(rows)}行"
        if quality_tags:
            feedback += f", 特征: {', '.join(quality_tags)}"
        SqlCorrectionService(self.db).save_correction(
            data_source_id=ds_id,
            question=f"[AI分析师] SQL查询 {sql[:60]}...",
            original_sql="",
            corrected_sql=sql,
            user_feedback=feedback,
            user_id=None,
        )

    @staticmethod
    def _extract_tables_from_sql(sql: str) -> List[str]:
        """从 SQL 中提取表名"""
        import re
        tables = re.findall(r'(?:FROM|JOIN)\s+[`"]?(\w+)[`"]?(?:\s+|$|\.)', sql, re.IGNORECASE)
        return list(set(t.lower() for t in tables if t.lower() not in ("select", "where", "and", "or", "on", "as")))

    def _auto_statistical_summary(self, cols: List[str], rows: List) -> Optional[Dict]:
        if not cols or not rows:
            return None
        num_summary, cat_top = {}, {}
        for ci, cn in enumerate(cols):
            vals = []
            for r in rows:
                v = r[ci] if isinstance(r, (list, tuple)) else r.get(cn)
                try:
                    vals.append(float(v))
                except (ValueError, TypeError):
                    continue
            if len(vals) > len(rows) * 0.5 and vals:
                num_summary[cn] = {"min": min(vals), "max": max(vals),
                                   "avg": round(sum(vals) / len(vals), 2),
                                   "median": round(statistics.median(vals), 2) if len(vals) > 2 else vals[0],
                                   "non_null": len(vals), "total": len(rows)}
            else:
                svals = []
                for r in rows:
                    v = r[ci] if isinstance(r, (list, tuple)) else r.get(cn)
                    if v is not None:
                        svals.append(str(v))
                if len(set(svals)) <= 20 and svals:
                    cat_top[cn] = Counter(svals).most_common(5)
        return {"numeric_summary": num_summary, "categorical_top": cat_top,
                "row_count": len(rows), "column_count": len(cols)} if (num_summary or cat_top) else None

    def _auto_detect_patterns(self, cols: List[str], rows: List) -> Optional[List[Dict]]:
        if not cols or len(rows) < 3:
            return None
        patterns, num_cols, date_col = [], [], None
        for ci, cn in enumerate(cols):
            if any(k in cn.lower() for k in ["date", "time", "dt", "day", "month", "year"]):
                date_col = cn
            vals = []
            for r in rows:
                v = r[ci] if isinstance(r, (list, tuple)) else r.get(cn)
                try:
                    vals.append(float(v))
                except (ValueError, TypeError):
                    break
            if len(vals) == len(rows):
                num_cols.append((cn, vals))
        # 趋势
        if date_col and num_cols:
            for cn, vals in num_cols:
                if len(vals) >= 3:
                    h = len(vals) // 2
                    fh = sum(vals[:h]) / max(h, 1)
                    sh = sum(vals[h:]) / max(len(vals) - h, 1)
                    if fh > 0:
                        cp = (sh - fh) / fh * 100
                        if abs(cp) > 10:
                            patterns.append({"type": "trend", "field": cn,
                                             "direction": "up" if cp > 0 else "down",
                                             "change_pct": round(cp, 1)})
        # 异常
        for cn, vals in num_cols:
            if len(vals) >= 5:
                m, s = statistics.mean(vals), statistics.stdev(vals) if len(vals) > 1 else 0
                if s > 0:
                    for i, v in enumerate(vals):
                        if abs(v - m) / s > 2.5:
                            patterns.append({"type": "anomaly", "field": cn, "index": i,
                                             "value": round(v, 2), "z_score": round(abs(v - m) / s, 2)})
        # 相关性
        if len(num_cols) >= 2:
            for i in range(len(num_cols)):
                for j in range(i + 1, len(num_cols)):
                    na, va = num_cols[i]
                    nb, vb = num_cols[j]
                    n = min(len(va), len(vb))
                    if n >= 5:
                        ma, mb = statistics.mean(va[:n]), statistics.mean(vb[:n])
                        sa, sb = statistics.stdev(va[:n]) if n > 1 else 1, statistics.stdev(vb[:n]) if n > 1 else 1
                        if sa > 0 and sb > 0:
                            corr = sum((va[k] - ma) * (vb[k] - mb) for k in range(n)) / (n * sa * sb)
                            if abs(corr) > 0.7:
                                patterns.append({"type": "correlation", "field_a": na, "field_b": nb, "correlation": round(corr, 3)})
        return patterns if patterns else None

    def _check_sql_quality(self, sql: str, result: Dict) -> Optional[List[str]]:
        warns, upper = [], sql.upper()
        if "SELECT *" in upper and "COUNT(*)" not in upper:
            warns.append("建议明确选择需要的列而非 SELECT *")
        if "WHERE" not in upper and "LIMIT" not in upper and "SELECT" in upper:
            warns.append("全表扫描！建议添加 WHERE 或 LIMIT")
        if result.get("total", 0) > 10000 and "LIMIT" not in upper:
            warns.append(f"返回 {result['total']} 行，建议添加 LIMIT")
        if upper.count("SELECT") - 1 > 3:
            warns.append("过多子查询嵌套，建议用 CTE(WITH) 改写")
        return warns if warns else None

    # ── 工具执行 ──────────────────────────────────

    def _is_admin_user(self, uid: int) -> bool:
        if not uid:
            return False
        try:
            u = self.db.query(User).filter(User.id == uid).first()
            return bool(u and u.role and u.role.name == "admin")
        except Exception:
            return False

    def list_metrics_tool(self, data_source_id: int, user_id: int = None) -> Dict[str, Any]:
        if user_id is None:
            return {"success": False, "error": "缺少用户上下文", "metrics": []}
        try:
            self.query_service.data_source_service.require_access(data_source_id, user_id)
            metrics = SemanticMetricRepository(self.db).list_visible_for_data_source(
                data_source_id, user_id, self._is_admin_user(user_id), 50, True)
            return {"success": True, "metrics": [{"metric_key": m.metric_key, "name": m.name, "description": m.description,
                     "metric_expression": m.metric_expression, "dimensions": m.dimensions or [], "time_column": m.time_column}
                    for m in metrics], "total": len(metrics)}
        except Exception as e:
            return {"success": False, "error": str(e), "metrics": []}

    def query_metric_tool(self, metric_key: str, data_source_id: int, user_id: int = None,
                          dimensions: list = None, start_time: str = None, end_time: str = None,
                          filters: dict = None, page: int = 1, page_size: int = 50,
                          alternate_ds_id: int = None) -> Dict[str, Any]:
        if user_id is None:
            return {"success": False, "error": "缺少用户上下文"}
        qid = alternate_ds_id or data_source_id
        try:
            self.query_service.data_source_service.require_access(qid, user_id)
            admin = self._is_admin_user(user_id)
            vm = SemanticMetricRepository(self.db).get_visible_by_key(metric_key, user_id, admin, True)
            if not vm:
                return {"success": False, "error": "指标不存在或已禁用"}
            if vm.data_source_id != qid:
                return {"success": False, "error": f"指标属于 ds_id={vm.data_source_id}"}
            _, result = SemanticMetricQueryService(self.db).execute(
                SemanticMetricQueryRequest(metric_key=metric_key, start_time=start_time, end_time=end_time,
                                            dimensions=dimensions or [], filters=filters or {},
                                            page=page, page_size=page_size), user_id, admin)
            return {"success": True, "metric": {"metric_key": vm.metric_key, "name": vm.name,
                     "dimensions": vm.dimensions or [], "time_column": vm.time_column},
                     "columns": result.columns, "rows": result.rows[:100], "total": result.total}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_schema_tool(self, data_source_id: int, table_name: str = None, user_id: int = None) -> Dict[str, Any]:
        if user_id is None:
            return {"success": False, "error": "缺少用户上下文"}
        try:
            ds = self.query_service.data_source_service.require_access(data_source_id, user_id)
            from app.utils.db_executor import execute_query
            db_type = (ds.type or "").upper()
            if db_type in ("POSTGRES", "POSTGRESQL", "PG"):
                sql = ("SELECT table_name, column_name, data_type, is_nullable, column_default, "
                       "col_description((quote_ident(table_schema)||'.'||quote_ident(table_name))::regclass, ordinal_position) as comment "
                       "FROM information_schema.columns WHERE table_schema = 'public' ORDER BY table_name, ordinal_position")
            else:
                sql = f"SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT FROM information_schema.columns WHERE TABLE_SCHEMA = '{ds.database}' ORDER BY TABLE_NAME, ORDINAL_POSITION"
                if table_name:
                    sql = sql.replace("WHERE", f"WHERE TABLE_NAME = '{table_name}' AND")
            rows, _ = execute_query(ds, sql)
            tables = {}
            for r in rows:
                t = r[0]
                if t not in tables:
                    tables[t] = []
                tables[t].append({"column": r[1], "type": r[2], "nullable": r[3],
                                   "default": str(r[4]) if r[4] else None,
                                   "comment": str(r[5]) if r[5] else None})
            return {"success": True, "tables": [{"table_name": t, "columns": c, "column_count": len(c)}
                     for t, c in sorted(tables.items())], "total_count": len(tables)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_chart_tool(self, chart_type: str, data: List, x_axis_field: str, y_axis_field: str,
                            title: str = "", series_fields: List[str] = None) -> Dict[str, Any]:
        if not data:
            return {"success": False, "error": "无数据"}
        cols = list(data[0].keys()) if isinstance(data[0], dict) else [f"c{i}" for i in range(len(data[0]))]

        def _get(r, f):
            if isinstance(r, dict):
                return r.get(f)
            try:
                return r[cols.index(f)] if f in cols else None
            except (ValueError, IndexError):
                return None

        x_axis_field, y_axis_field = infer_chart_axes(cols, data, x_axis_field, y_axis_field)

        def _num(r, f):
            try:
                return float(_get(r, f) or 0)
            except (ValueError, TypeError):
                return 0

        x_raw = [str(_get(r, x_axis_field)) for r in data]
        x_uniq = list(dict.fromkeys(x_raw))

        if chart_type == "heatmap":
            xd = sorted(set(x_raw))
            yd = sorted(set(str(_get(r, y_axis_field)) for r in data))
            vf = [c for c in cols if c not in (x_axis_field, y_axis_field)]
            vf = vf[0] if vf else None
            hd = []
            for r in data:
                xv, yv = str(_get(r, x_axis_field)), str(_get(r, y_axis_field))
                if xv in xd and yv in yd:
                    try:
                        hd.append([xd.index(xv), yd.index(yv), _num(r, vf) if vf else 0])
                    except (ValueError, TypeError):
                        pass
            mv = max((v[2] for v in hd), default=1)
            return {"success": True, "chart_config": {
                "title": {"text": title or "热力图"}, "tooltip": {"position": "top"},
                "xAxis": {"type": "category", "data": xd, "splitArea": {"show": True}},
                "yAxis": {"type": "category", "data": yd, "splitArea": {"show": True}},
                "visualMap": {"min": min((v[2] for v in hd), default=0), "max": mv, "calculable": True, "orient": "horizontal", "left": "center", "bottom": 0},
                "series": [{"type": "heatmap", "data": hd}]}, "chart_type": "heatmap"}

        if chart_type == "treemap":
            td = [{"name": str(_get(r, x_axis_field)), "value": _num(r, y_axis_field)} for r in data]
            return {"success": True, "chart_config": {
                "title": {"text": title or "矩形树图"}, "tooltip": {"formatter": "{b}: {c}"},
                "series": [{"type": "treemap", "data": td, "roam": False, "label": {"show": True, "formatter": "{b}\n{c}"}}]},
                     "chart_type": "treemap"}

        if chart_type == "waterfall":
            cats, vals = [], []
            for r in data:
                cats.append(str(_get(r, x_axis_field)))
                vals.append(_num(r, y_axis_field))
            base = [0]
            for v in vals[:-1]:
                base.append(base[-1] + v)
            return {"success": True, "chart_config": {
                "title": {"text": title or "瀑布图"}, "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "xAxis": {"type": "category", "data": cats}, "yAxis": {"type": "value"},
                "series": [{"type": "bar", "stack": "total", "data": base, "itemStyle": {"color": "transparent"}},
                           {"type": "bar", "stack": "total", "data": vals}]}, "chart_type": "waterfall"}

        if chart_type == "boxplot":
            groups = {}
            for r in data:
                g = str(_get(r, x_axis_field))
                v = _num(r, y_axis_field)
                groups.setdefault(g, []).append(v)
            bd, ct = [], []
            for g, vs in sorted(groups.items()):
                if len(vs) < 5:
                    continue
                ct.append(g)
                sv = sorted(vs)
                n = len(sv)
                bd.append([min(sv), sv[n // 4], statistics.median(sv), sv[3 * n // 4], max(sv)])
            return {"success": True, "chart_config": {
                "title": {"text": title or "箱线图"}, "tooltip": {"trigger": "item"},
                "xAxis": {"type": "category", "data": ct}, "yAxis": {"type": "value"},
                "series": [{"type": "boxplot", "data": bd}]}, "chart_type": "boxplot"}

        if chart_type == "dual-axis":
            nc = [c for c in cols if c not in (x_axis_field, y_axis_field)]
            rc = nc[0] if nc else y_axis_field
            ld, rd = [], []
            for xv in x_uniq:
                lv, rv = 0, 0
                for r in data:
                    if str(_get(r, x_axis_field)) == xv:
                        lv = _num(r, y_axis_field)
                        rv = _num(r, rc)
                ld.append(lv)
                rd.append(rv)
            return {"success": True, "chart_config": {
                "title": {"text": title or "双轴图"}, "tooltip": {"trigger": "axis"},
                "legend": {"data": [y_axis_field, rc]},
                "xAxis": {"type": "category", "data": x_uniq},
                "yAxis": [{"type": "value", "name": y_axis_field}, {"type": "value", "name": rc}],
                "series": [{"name": y_axis_field, "type": "bar", "data": ld},
                           {"name": rc, "type": "line", "yAxisIndex": 1, "data": rd}]},
                     "chart_type": "dual-axis"}

        # 标准多系列/单系列
        y_data = [_num(r, y_axis_field) for r in data]
        colors = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de",
                   "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc", "#1ab1ff"]

        if series_fields and series_fields:
            sc = series_fields[0]
            us = sorted(set(str(_get(r, sc)) for r in data if _get(r, sc)))
            if len(us) > 1:
                sl, lg = [], []
                for idx, sv in enumerate(us[:20]):
                    sm = {}
                    for r in data:
                        if str(_get(r, sc)) == sv:
                            sm[str(_get(r, x_axis_field))] = _num(r, y_axis_field)
                    sdata = [sm.get(x, 0) for x in x_uniq]
                    sl.append({"name": sv, "type": chart_type if chart_type in ("bar", "line", "scatter") else "line",
                               "data": sdata, "itemStyle": {"color": colors[idx % len(colors)]}})
                    lg.append(sv)
                return {"success": True, "chart_config": {
                    "title": {"text": title or "多系列图"}, "tooltip": {"trigger": "axis"},
                    "legend": {"data": lg, "top": 8, "type": "scroll"},
                    "xAxis": {"type": "category", "data": x_uniq},
                    "yAxis": {"type": "value"}, "series": sl}, "chart_type": chart_type, "series_count": len(us)}

        cc = {"title": {"text": title or f"{y_axis_field} by {x_axis_field}"},
              "tooltip": {"trigger": "axis"}, "legend": {"data": [y_axis_field]},
              "xAxis": {"type": "category", "data": [str(v) if v else "未知" for v in x_raw]},
              "yAxis": {"type": "value"},
              "series": [{"name": y_axis_field, "type": chart_type if chart_type in ("bar", "line", "scatter") else "bar", "data": y_data}]}
        if chart_type == "pie":
            pd = [{"name": str(x), "value": y} for x, y in zip(x_raw, y_data) if y > 0]
            cc = {"title": {"text": title or y_axis_field}, "tooltip": {"trigger": "item"},
                  "series": [{"type": "pie", "data": pd}]}
        return {"success": True, "chart_config": cc, "chart_type": chart_type}

    def analyze_data_tool(self, data: List, columns: List[str], question: str = "") -> Dict[str, Any]:
        if not data or not columns:
            return {"success": False, "error": "无数据", "insights": []}
        insights = [f"数据 {len(data)} 行, {len(columns)} 列"]
        num_cols = []
        for ci, cn in enumerate(columns):
            vals = [_num(r, cn) for r in data if (_num := lambda r, f: (lambda v: float(v) if v else 0)(r[ci] if isinstance(r, (list, tuple)) else r.get(f)))]
            # simplified - use direct approach
            vals_actual = []
            for r in data:
                v = r[ci] if isinstance(r, (list, tuple)) else r.get(cn)
                try:
                    vals_actual.append(float(v))
                except (ValueError, TypeError):
                    pass
            if len(vals_actual) > len(data) * 0.5:
                num_cols.append(cn)
                insights.append(f"【{cn}】均值={statistics.mean(vals_actual):.2f}, 最小={min(vals_actual)}, 最大={max(vals_actual)}")
        llm_analysis = None
        if question and data:
            try:
                llm = self._get_llm_client()
                llm_analysis = llm.chat([
                    {"role": "system", "content": "你是一个专业的数据分析师。"},
                    {"role": "user", "content": f"分析数据:\n问题: {question}\n列: {columns}\n数据: {json.dumps(data[:30], ensure_ascii=False, default=str)}\n请从趋势、关键发现、异常、行动建议角度分析，用 markdown。"}
                ], temperature=0.3)
            except Exception as e:
                logger.warning(f"LLM 分析失败: {e}")
        return {"success": True, "insights": insights, "llm_analysis": llm_analysis,
                "numeric_columns": num_cols, "row_count": len(data), "column_count": len(columns)}

    # ── Agent 核心 ──────────────────────────────────

    def _execute_tool(self, action: Dict, data_source_id: int, user_id: int = None) -> Dict:
        name, inp = action.get("tool", ""), action.get("input", {})
        if name == "execute_sql":
            return self.execute_sql_tool(
                inp.get("sql", ""), inp.get("data_source_id", data_source_id), user_id
            )
        if name == "get_schema":
            return self.get_schema_tool(
                inp.get("data_source_id", data_source_id), inp.get("table_name"), user_id
            )
        if name == "generate_chart":
            return self.generate_chart_tool(inp.get("chart_type", "bar"), inp.get("data", []),
                                             inp.get("x_axis_field", ""), inp.get("y_axis_field", ""),
                                             inp.get("title", ""), inp.get("series_fields"))
        if name == "analyze_data":
            return self.analyze_data_tool(inp.get("data", []), inp.get("columns", []), inp.get("question", ""))
        if name == "list_metrics":
            return self.list_metrics_tool(inp.get("data_source_id", data_source_id), user_id)
        if name == "query_metric":
            return self.query_metric_tool(inp.get("metric_key", ""), inp.get("data_source_id", data_source_id), user_id,
                                           inp.get("dimensions"), inp.get("start_time"), inp.get("end_time"),
                                           inp.get("filters"), inp.get("page", 1), inp.get("page_size", 50),
                                           inp.get("alternate_ds_id"))
        return {"success": False, "error": f"未知工具: {name}"}

    def _compact_for_llm(self, name: str, result: Dict) -> Dict:
        if name == "execute_sql" and result.get("success"):
            c = {"success": True, "columns": result.get("columns", []), "total": result.get("total", 0), "truncated": result.get("truncated", False),
                 "rows_preview": result.get("rows", [])[:20], "rows_truncated": len(result.get("rows", [])) > 20}
            if "_auto_insights" in result:
                c["_auto_insights"] = result["_auto_insights"]
            if "_auto_patterns" in result:
                c["_auto_patterns"] = result["_auto_patterns"]
            if "_sql_quality_warnings" in result:
                c["_sql_quality_warnings"] = result["_sql_quality_warnings"]
            return c
        if name == "get_schema" and result.get("success"):
            tables = []
            for table in result.get("tables", []):
                column_names = [column.get("column") for column in table.get("columns", [])]
                tables.append({
                    "table_name": table.get("table_name"),
                    "column_count": table.get("column_count", len(column_names)),
                    "columns_preview": column_names[:12],
                    "columns_truncated": len(column_names) > 12,
                })
            return {
                "success": True,
                "total_count": result.get("total_count", len(tables)),
                "tables": tables,
            }
        return result

    def _compact_tool_result_for_llm(self, name: str, result: Dict) -> Dict:
        """Compatibility alias with a descriptive public helper name."""
        return self._compact_for_llm(name, result)

    def _fmt_tool(self, name: str, result: Dict, limit: int = 12000) -> str:
        return json.dumps(self._compact_for_llm(name, result), ensure_ascii=False, default=str)[:limit]

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        start = text.find("{")
        if start == -1:
            return None
        depth, instr, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if instr:
                esc = False if not esc else (ch == "\\")
                if ch == '"' and not esc:
                    instr = False
                continue
            if ch == '"':
                instr = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    def _parse_action(self, text: str) -> Optional[Dict]:
        obj = self._extract_json(text)
        if obj and isinstance(obj, dict) and "tool" in obj:
            return {"tool": obj["tool"], "input": obj.get("input", {})}
        return None

    # ── 同步 chat ──────────────────────────────────

    def chat(self, message: str, data_source_id: int, conversation_id: str = None,
             group_id: int = None, user_id: int = None) -> AIAnalystChatResponse:
        if user_id is None:
            raise ValueError("缺少用户上下文")
        self.query_service.data_source_service.require_access(data_source_id, user_id)
        ds_id, cid, gid, uid = data_source_id, conversation_id, group_id, user_id
        if not cid:
            cid = str(uuid.uuid4())
        scoped_cid = f"{uid}:{cid}"
        ck = self._cache_key(message, ds_id, gid, uid)
        cached = self._get_cached_response(ck)
        if cached:
            return AIAnalystChatResponse(conversation_id=cid, message=AIAnalystMessage(role="assistant", content=cached))
        sc = self._get_semantic_cache(message, ds_id, uid)
        if sc:
            return AIAnalystChatResponse(conversation_id=cid, message=AIAnalystMessage(role="assistant", content=sc))

        history = self._get_conversation_history(scoped_cid)
        tp = self._build_tools_prompt(ds_id)
        sem = build_semantic_runtime_context(self.db, ds_id, message, max_chars=0)
        from app.services.sql_correction_service import SqlCorrectionService
        fs = SqlCorrectionService(self.db).build_few_shot_prompt(message, ds_id)
        level = self._detect_complexity_level(message)

        bf = ""
        try:
            r = get_redis()
            dso = self.ds_repo.get_by_id(ds_id)
            if dso and dso.database:
                bk = r.keys(f"bad_functions:{dso.database}:*")
                if bk:
                    bn = [k.decode().split(":")[-1] for k in bk]
                    bf = "\n## 不支持的函数:\n" + ", ".join(f"`{f}`" for f in sorted(bn)) + "\n"
        except Exception:
            pass

        sp = self._load_system_prompt(level)
        sys = sp + "\n\n" + tp + "\n\n" + fs + "\n\n" + bf + "\n### 语义层文档\n\n" + sem
        if gid:
            sys += f"\n\n⚠️ 集团ID={gid}！所有SQL必须带 WHERE group_id = {gid}。"

        messages = [{"role": "system", "content": sys}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        chart_cfg = None
        tool_recs = []
        all_text = []
        last_ok = None
        llm = self._get_llm_client()
        tdefs = self._build_tool_definitions(ds_id)

        for step in range(self.MAX_AGENT_STEPS):
            try:
                if llm.supports_tools:
                    choice = llm.chat_with_tools(messages, tdefs, temperature=0.0)
                    if choice.tool_calls:
                        for tc in choice.tool_calls:
                            act = {"tool": tc.name, "input": tc.arguments}
                            tr = self._execute_tool(act, ds_id, uid)
                            tool_recs.append(AIAnalystToolCall(tool_name=tc.name, tool_input=tc.arguments,
                                                               tool_output=self._fmt_tool(tc.name, tr)))
                            if tc.name == "execute_sql" and tr.get("success"):
                                last_ok = tr
                            if tc.name == "generate_chart" and tr.get("success"):
                                chart_cfg = tr.get("chart_config")
                            messages.append({"role": "assistant", "content": choice.content or ""})
                            messages.append({"role": "user", "content": f"工具 [{tc.name}]:\n{self._fmt_tool(tc.name, tr)}"})
                        continue
                    response_text = choice.content or ""
                else:
                    response_text = llm.chat(messages, temperature=0.0)
                    act = self._parse_action(response_text)
                    if act:
                        tr = self._execute_tool(act, ds_id, uid)
                        tool_recs.append(AIAnalystToolCall(tool_name=act["tool"], tool_input=act.get("input", {}),
                                                           tool_output=self._fmt_tool(act["tool"], tr)))
                        if act["tool"] == "execute_sql" and tr.get("success"):
                            last_ok = tr
                        if act["tool"] == "generate_chart" and tr.get("success"):
                            chart_cfg = tr.get("chart_config")
                        messages.append({"role": "assistant", "content": response_text})
                        messages.append({"role": "user", "content": f"工具 [{act['tool']}]:\n{self._fmt_tool(act['tool'], tr)}"})
                        continue
            except LLMError as e:
                return AIAnalystChatResponse(conversation_id=cid,
                    message=AIAnalystMessage(role="assistant", content=f"AI 服务暂时不可用: {e}"))

            all_text.append(response_text)
            self._set_cached_response(ck, response_text)
            self._set_semantic_cache(message, response_text, ds_id, uid)
            self._save_conversation_history(scoped_cid, [{"role": "user", "content": message}, {"role": "assistant", "content": response_text}])
            return AIAnalystChatResponse(conversation_id=cid,
                message=AIAnalystMessage(role="assistant", content=response_text, tool_calls=tool_recs or None, chart_config=chart_cfg))

        return AIAnalystChatResponse(conversation_id=cid,
            message=AIAnalystMessage(role="assistant", content=all_text[-1] if all_text else "已完成分析。",
                                      tool_calls=tool_recs or None, chart_config=chart_cfg))

    # ── 流式 chat ──────────────────────────────────

    async def chat_stream(self, message: str, data_source_id: int, conversation_id: str = None,
                           group_id: int = None, user_id: int = None):
        if user_id is None:
            raise ValueError("缺少用户上下文")
        self.query_service.data_source_service.require_access(data_source_id, user_id)
        ds_id, cid, gid, uid = data_source_id, conversation_id, group_id, user_id
        if not cid:
            cid = str(uuid.uuid4())
        scoped_cid = f"{uid}:{cid}"
        history = self._get_conversation_history(scoped_cid)
        tp = self._build_tools_prompt(ds_id)
        sem = build_semantic_runtime_context(self.db, ds_id, message, max_chars=0)
        from app.services.sql_correction_service import SqlCorrectionService
        fs = SqlCorrectionService(self.db).build_few_shot_prompt(message, ds_id)
        level = self._detect_complexity_level(message)
        bf = ""
        try:
            r = get_redis()
            dso = self.ds_repo.get_by_id(ds_id)
            if dso and dso.database:
                bk = r.keys(f"bad_functions:{dso.database}:*")
                if bk:
                    bn = [k.decode().split(":")[-1] for k in bk]
                    bf = "\n## 不支持的函数:\n" + ", ".join(f"`{f}`" for f in sorted(bn)) + "\n"
        except Exception:
            pass
        sp = self._load_system_prompt(level)
        sys = sp + "\n\n" + tp + "\n\n" + fs + "\n\n" + bf + "\n### 语义层文档\n\n" + sem
        if gid:
            sys += f"\n\n⚠️ 集团ID={gid}！所有SQL必须带 WHERE group_id = {gid}。"

        messages = [{"role": "system", "content": sys}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        chart_cfg = None
        llm = self._get_llm_client()
        tdefs = self._build_tool_definitions(ds_id)

        for step in range(self.MAX_AGENT_STEPS):
            try:
                if llm.supports_tools:
                    text_parts = []
                    tool_calls = []
                    for chunk in llm.chat_stream_with_tools(messages, tdefs):
                        if chunk["type"] == "text":
                            text_parts.append(chunk["content"])
                            yield {"type": "token", "content": chunk["content"]}
                        elif chunk["type"] == "tool_call":
                            tool_calls.append(chunk)
                            yield {"type": "tool_call", "tool_name": chunk["tool_name"], "tool_input": chunk["arguments"]}

                    if tool_calls:
                        for tc in tool_calls:
                            act = {"tool": tc["tool_name"], "input": tc["arguments"]}
                            tr = self._execute_tool(act, ds_id, uid)
                            yield {"type": "tool_result", "tool_name": tc["tool_name"],
                                   "tool_output": self._fmt_tool(tc["tool_name"], tr)}
                            if tc["tool_name"] == "execute_sql" and tr.get("success"):
                                for p in (tr.get("_auto_patterns") or [])[:3]:
                                    yield {"type": "token", "content": f"\n📊 {p.get('description', '')}\n"}
                                for w in (tr.get("_sql_quality_warnings") or [])[:2]:
                                    yield {"type": "token", "content": f"\n💡 {w}\n"}
                            if tc["tool_name"] == "generate_chart" and tr.get("success"):
                                chart_cfg = tr.get("chart_config")
                                yield {"type": "chart", "chart_config": chart_cfg}
                            messages.append({"role": "assistant", "content": "".join(text_parts)})
                            messages.append({"role": "user", "content": f"工具 [{tc['tool_name']}]:\n{self._fmt_tool(tc['tool_name'], tr)}"})
                        continue
                    else:
                        all_text = "".join(text_parts)
                        self._save_conversation_history(scoped_cid, [{"role": "user", "content": message}, {"role": "assistant", "content": all_text}])
                        yield {"type": "done", "conversation_id": cid}
                        return
                else:
                    tokens = []
                    for t in llm.chat_stream(messages):
                        tokens.append(t)
                    text = "".join(tokens)
                    act = self._parse_action(text)
                    if act:
                        yield {"type": "tool_call", "tool_name": act.get("tool"), "tool_input": act.get("input", {})}
                        tr = self._execute_tool(act, ds_id, uid)
                        yield {"type": "tool_result", "tool_name": act.get("tool"),
                               "tool_output": self._fmt_tool(act.get("tool"), tr)}
                        if act.get("tool") == "execute_sql" and tr.get("success"):
                            for p in (tr.get("_auto_patterns") or [])[:3]:
                                yield {"type": "token", "content": f"\n📊 {p.get('description', '')}\n"}
                            for w in (tr.get("_sql_quality_warnings") or [])[:2]:
                                yield {"type": "token", "content": f"\n💡 {w}\n"}
                        if act.get("tool") == "generate_chart" and tr.get("success"):
                            chart_cfg = tr.get("chart_config")
                            yield {"type": "chart", "chart_config": chart_cfg}
                        messages.append({"role": "assistant", "content": text})
                        messages.append({"role": "user", "content": f"工具 [{act['tool']}]:\n{self._fmt_tool(act['tool'], tr)}"})
                        continue
                    for t in tokens:
                        yield {"type": "token", "content": t}
                    self._save_conversation_history(scoped_cid, [{"role": "user", "content": message}, {"role": "assistant", "content": text}])
                    yield {"type": "done", "conversation_id": cid}
                    return
            except Exception as e:
                logger.error(f"[AI-Analyst] step {step} 失败: {e}")
                yield {"type": "error", "error": str(e)}
                return

        yield {"type": "done", "conversation_id": cid}

    async def _stream_llm_call(self, llm: LLMClient, messages: List[Dict]):
        for token in llm.chat_stream(messages):
            yield token

    def get_schema(self, data_source_id: int, table_name: str = None, user_id: int = None):
        return self.get_schema_tool(data_source_id, table_name, user_id)
