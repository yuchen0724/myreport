"""Prompt template utilities — loading, caching, and rendering of NL2SQL prompt templates."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages prompt template loading, caching, and rendering."""

    def __init__(self):
        self._template_cache: Dict[str, Dict[str, Any]] = {}

    def load_template(self, template_path: Optional[str], template_name: str) -> Optional[str]:
        """从配置路径读取提示词模板（支持绝对路径或相对 backend/ 路径，含热更新）。"""
        if not template_path:
            return None

        cache_key = f"{template_name}:{template_path}"
        path = Path(template_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[3] / path

        try:
            stat_result = path.stat()
        except OSError as e:
            logger.warning("读取 %s 提示词模板失败: %s (%s)", template_name, path, e)
            self._template_cache.pop(cache_key, None)
            return None

        cached = self._template_cache.get(cache_key)
        if (
            cached
            and cached.get("path") == str(path)
            and cached.get("mtime_ns") == stat_result.st_mtime_ns
        ):
            return cached.get("content")

        try:
            template = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("读取 %s 提示词模板失败: %s (%s)", template_name, path, e)
            self._template_cache.pop(cache_key, None)
            return None

        self._template_cache[cache_key] = {
            "path": str(path),
            "mtime_ns": stat_result.st_mtime_ns,
            "content": template,
        }
        logger.info("加载/刷新 %s 提示词模板: %s", template_name, path)
        return template

    def render_template(
        self,
        template: str,
        context: Dict[str, Any],
        template_name: str,
        fallback: str = "",
    ) -> str:
        """渲染提示词模板；渲染失败时回退默认模板。"""
        try:
            return template.format(**context)
        except Exception as e:
            logger.warning("渲染 %s 提示词模板失败，回退默认模板: %s", template_name, e)
            return fallback

    def clear_cache(self):
        """Clear template cache (for testing / hot-reload)."""
        self._template_cache.clear()


def is_postgres_db_type(db_type: Optional[str]) -> bool:
    """判断是否 PostgreSQL 数据源类型。"""
    if not db_type:
        return False
    return db_type.upper() in {"POSTGRES", "POSTGRESQL", "PG"}


def build_system_prompt(
    prompt_mgr: PromptManager,
    db_type: str,
    db_limitations: str,
    schema_prompt: str,
    group_id: Optional[int] = None,
    semantic_metrics_prompt: Optional[str] = None,
    settings=None,
) -> str:
    """构建 NL2SQL 系统提示词。"""
    from datetime import datetime
    today_date = datetime.now().strftime("%Y-%m-%d")
    group_context = (
        f"**{group_id}**（已确认，该用户的查询应基于此集团的数据）"
        if group_id
        else "未知（未指定，按全局数据查询）"
    )
    table_name_rule = (
        "【重要】所有表名必须带库名前缀，且 PostgreSQL 必须使用 `库名.public.表名` 格式"
        "（例如 `mydb.public.dim_store`）"
        if is_postgres_db_type(db_type)
        else "【重要】所有表名必须带库名前缀，如 `库名.表名`"
        "（例如 `ads_cockpit_freedom.store_sales`），否则跨库查询会失败！"
    )

    settings = settings or get_settings()
    custom_template = prompt_mgr.load_template(
        getattr(settings, "nl2sql_system_prompt_path", None),
        "system",
    )
    if not custom_template:
        logger.warning("system 提示词模板未配置或读取失败，当前使用空提示词")
        return ""

    context = {
        "db_type": db_type,
        "db_limitations": db_limitations,
        "schema_prompt": schema_prompt,
        "semantic_metrics_prompt": semantic_metrics_prompt or "无可用语义指标。",
        "group_context": group_context,
        "table_name_rule": table_name_rule,
        "today_date": today_date,
    }
    return prompt_mgr.render_template(
        custom_template,
        context=context,
        template_name="system",
        fallback="",
    )


def build_repair_prompt(
    prompt_mgr: PromptManager,
    question: str,
    failed_sql: str,
    error_msg: str,
    settings=None,
) -> str:
    """构建 SQL 修复提示词。"""
    settings = settings or get_settings()
    custom_template = prompt_mgr.load_template(
        getattr(settings, "nl2sql_repair_prompt_path", None),
        "repair",
    )
    if not custom_template:
        logger.warning("repair 提示词模板未配置或读取失败，当前使用空提示词")
        return ""

    context = {
        "question": question,
        "failed_sql": failed_sql,
        "error_msg": error_msg,
    }
    return prompt_mgr.render_template(
        custom_template,
        context=context,
        template_name="repair",
        fallback="",
    )
