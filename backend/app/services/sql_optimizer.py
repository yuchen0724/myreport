"""SQL 优化器服务

将生成的 SQL 通过 LLM 进行优化（基于 prompts/sql_optimizer.md 提示词）。
含缓存和降级：LLM 失败时回退到静态规则优化。
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional
from app.config import get_settings
from app.utils.llm_client import get_llm_client, LLMError, LLMClient
from app.utils.semantic_context import build_semantic_snapshot

logger = logging.getLogger(__name__)


class SqlOptimizer:
    """SQL 优化器

    1. 尝试调用 LLM 优化 SQL（基于提示词文档）
    2. 失败时回退到静态规则优化
    3. 相同 SQL 使用内存缓存（避免重复 LLM 调用）
    """

    def __init__(self):
        self._llm_client: Optional[LLMClient] = None
        # LRU 缓存: sql_hash → optimized_sql
        self._cache: dict[str, str] = {}
        self._max_cache = 128

    # ── 公开接口 ──

    def optimize(self, sql: str) -> str:
        """优化 SQL

        优先级: 缓存 → LLM → 静态规则（原样返回）
        """
        sql_stripped = sql.strip()
        if not sql_stripped:
            return sql

        # 1. 查缓存
        sql_hash = self._hash(sql_stripped)
        cached = self._cache.get(sql_hash)
        if cached is not None:
            logger.debug(f"[SQL优化] 缓存命中: {len(sql_stripped)} 字符")
            return cached

        # 2. 尝试 LLM 优化
        optimized = self._optimize_with_llm(sql_stripped)
        if optimized and optimized != sql_stripped:
            self._cache_put(sql_hash, optimized)
            logger.info(f"[SQL优化] LLM 优化完成: {len(sql_stripped)}→{len(optimized)} 字符")
            return optimized

        # 3. 回退：原样返回（后续的静态规则由 caller 的 _fix_select_star 等处理）
        return sql

    def clear_cache(self):
        """清除优化缓存"""
        self._cache.clear()
        logger.info("[SQL优化] 缓存已清除")

    # ── LLM 优化 ──

    def _get_llm_client(self) -> Optional[LLMClient]:
        """获取 LLM 客户端（惰性初始化）"""
        if self._llm_client is not None:
            return self._llm_client
        try:
            self._llm_client = get_llm_client()
            return self._llm_client
        except Exception as e:
            logger.warning(f"[SQL优化] LLM 客户端初始化失败: {e}")
            return None

    def _load_prompt(self) -> str:
        """从文件加载优化提示词"""
        settings = get_settings()
        prompt_path = getattr(settings, "sql_optimizer_prompt_path", None) or "prompts/sql_optimizer.md"

        # 尝试相对 backend/ 的路径
        path = Path(prompt_path)
        if not path.is_absolute():
            # 从当前文件位置向上找 backend/
            base = Path(__file__).resolve().parent.parent.parent  # app/services/ → app/ → backend/
            if base.name != "backend":
                # 也尝试直接 path
                base = Path.cwd()
            path = base / prompt_path

        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"[SQL优化] 读取提示词失败: {path} ({e})")
            return ""

    def _optimize_with_llm(self, sql: str) -> Optional[str]:
        """调用 LLM 优化 SQL"""
        settings = get_settings()
        if not getattr(settings, "sql_optimizer_enabled", False):
            return None

        client = self._get_llm_client()
        if not client:
            logger.warning("[SQL优化] LLM 客户端不可用，跳过 LLM 优化")
            return None

        prompt = self._load_prompt()
        if not prompt:
            logger.warning("[SQL优化] 提示词为空，跳过 LLM 优化")
            return None

        semantic_doc = build_semantic_snapshot("", 0, None)
        messages = [
            {"role": "system", "content": prompt + ("\n\n" + semantic_doc if semantic_doc else "")},
            {"role": "user", "content": f"<sql>\n{sql}\n</sql>"},
        ]

        try:
            result = client.chat(messages, temperature=0.0)
            optimized = result.strip()

            # 清理可能残留的 markdown 代码块标记
            if optimized.startswith("```"):
                # 移除 ```sql 或 ``` 包裹
                lines = optimized.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                optimized = "\n".join(lines).strip()

            if not optimized:
                logger.warning("[SQL优化] LLM 返回空结果，跳过")
                return None

            # 验证结果包含有效 SQL 关键字
            upper = optimized.upper()
            if not any(kw in upper for kw in ("SELECT", "WITH", "EXPLAIN")):
                logger.warning(f"[SQL优化] LLM 返回非 SQL 内容，跳过: {optimized[:100]}")
                return None

            return optimized

        except LLMError as e:
            logger.warning(f"[SQL优化] LLM 调用失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"[SQL优化] LLM 优化异常: {e}")
            return None

    # ── 内部 ──

    @staticmethod
    def _hash(sql: str) -> str:
        return hashlib.md5(sql.encode()).hexdigest()

    def _cache_put(self, sql_hash: str, optimized: str):
        if len(self._cache) >= self._max_cache:
            # 简单 LRU: 清除一半
            keys = list(self._cache.keys())
            for k in keys[: len(keys) // 2]:
                del self._cache[k]
        self._cache[sql_hash] = optimized
