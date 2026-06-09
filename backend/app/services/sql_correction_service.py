"""SQL 修正日志服务 — 存储和匹配历史修正案例"""

import re
import json
import hashlib
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.sql_correction import SqlCorrection
from app.utils.llm_client import get_llm_client
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

_EMBEDDING_PREFIX = "sql_correction:embedding:"


class SqlCorrectionService:
    """SQL 修正日志服务"""

    def __init__(self, db: Session):
        self.db = db

    def _embedding_key(self, correction_id: int) -> str:
        return f"{_EMBEDDING_PREFIX}{correction_id}"

    def save_correction(
        self,
        data_source_id: int,
        question: str,
        original_sql: str,
        corrected_sql: str,
        user_feedback: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Optional[SqlCorrection]:
        """保存一条修正记录（自动去重：同数据源同 corrected_sql 只保存一次）"""
        if not corrected_sql:
            return None
        existing = (
            self.db.query(SqlCorrection)
            .filter(
                SqlCorrection.data_source_id == data_source_id,
                SqlCorrection.corrected_sql == corrected_sql,
            )
            .first()
        )
        if existing:
            logger.info("[SqlCorrection] 跳过重复: id=%s data_source=%d sql=%s",
                         existing.id, data_source_id, corrected_sql[:60])
            return existing
        tables = self._extract_tables(original_sql) | self._extract_tables(corrected_sql)

        record = SqlCorrection(
            data_source_id=data_source_id,
            question=question,
            original_sql=original_sql,
            corrected_sql=corrected_sql,
            user_feedback=user_feedback,
            table_names=",".join(sorted(tables)) if tables else None,
            created_by=user_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        # P1-7: 保存时自动生成并缓存 question embedding 到 Redis
        try:
            llm = get_llm_client()
            embedding = llm.get_embedding(question)
            if embedding:
                r = get_redis()
                r.setex(self._embedding_key(record.id), 86400 * 30,
                        json.dumps(embedding))
        except Exception as e:
            logger.warning(f"[SqlCorrection] embedding 生成失败: {e}")

        logger.info("[SqlCorrection] 保存修正: id=%s question=%s", record.id, question[:60])
        return record

    def _get_embedding_from_cache(self, correction_id: int) -> Optional[List[float]]:
        """从 Redis 读取缓存的 embedding"""
        try:
            r = get_redis()
            raw = r.get(self._embedding_key(correction_id))
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def find_matches(
        self,
        question: str,
        data_source_id: Optional[int] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """根据问题和数据源查找最相关历史修正（P1-7: embedding 语义匹配 + 关键词混合）"""
        current_tables = self._extract_tables(question)

        query = self.db.query(SqlCorrection).filter(SqlCorrection.is_active == True)
        if data_source_id is not None:
            query = query.filter(SqlCorrection.data_source_id == data_source_id)
        records = query.order_by(SqlCorrection.created_at.desc()).limit(50).all()

        if len(records) < 5:
            cross = (
                self.db.query(SqlCorrection)
                .filter(SqlCorrection.is_active == True)
                .order_by(SqlCorrection.created_at.desc())
                .limit(50).all()
            )
            eids = {r.id for r in records}
            for r in cross:
                if r.id not in eids:
                    records.append(r)
                    eids.add(r.id)

        if not records:
            return []

        # 获取 query embedding 做语义匹配
        query_emb = None
        try:
            llm = get_llm_client()
            query_emb = llm.get_embedding(question)
        except Exception:
            pass

        scored = []
        for r in records:
            score = 0
            # 关键词匹配
            r_tables = set(t.strip() for t in (r.table_names or "").split(",") if t.strip())
            score += len(current_tables & r_tables) * 3
            q_words = set(re.findall(r'\w+', question.lower()))
            r_words = set(re.findall(r'\w+', (r.question or "").lower()))
            score += len(q_words & r_words)
            if not r.original_sql:
                score += 1  # 优质案例加分

            # P1-7: embedding 语义相似度
            if query_emb:
                cached_emb = self._get_embedding_from_cache(r.id)
                if cached_emb and len(cached_emb) > 0 and len(query_emb) > 0:
                    dot = sum(a * b for a, b in zip(query_emb, cached_emb))
                    nq = sum(a * a for a in query_emb) ** 0.5
                    nc = sum(a * a for a in cached_emb) ** 0.5
                    if nq > 0 and nc > 0:
                        emb_score = dot / (nq * nc)
                        score += emb_score * 5  # 语义相似度权重更高

            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: -x[0])
        results = []
        for score, r in scored[:top_k]:
            results.append({
                "id": r.id,
                "data_source_id": r.data_source_id,
                "question": r.question[:80] if r.question else "",
                "original_sql": r.original_sql,
                "corrected_sql": r.corrected_sql,
                "user_feedback": r.user_feedback,
                "score": score,
            })

        return results

    def build_few_shot_prompt(self, question: str, data_source_id: int) -> str:
        """构建 few-shot 示例 prompt 段落（P1-7: 增强版语义匹配 RAG）"""
        matches = self.find_matches(question, data_source_id, top_k=3)
        if not matches:
            return ""

        parts = ["## 历史修正案例（请参考避免相同错误）\n"]
        for m in matches:
            parts.append(f"### 类似问题: {m['question']}")
            if m.get("original_sql"):
                parts.append(f"**原始 SQL（有问题的）**:")
                parts.append(f"```sql\n{m['original_sql']}\n```")
            parts.append(f"**正确的 SQL**:")
            parts.append(f"```sql\n{m['corrected_sql']}\n```")
            if m.get("user_feedback"):
                parts.append(f"**说明**: {m['user_feedback']}")
            parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _extract_tables(text: str) -> set:
        """从 SQL 或文本中提取表名"""
        tables = set()
        matches = re.findall(r'(?:FROM|JOIN)\s+([`"]?)(?:ads_cockpit_freedom\.)?(\w+)\1', text, re.IGNORECASE)
        for _, table in matches:
            tables.add(table.lower())
        matches2 = re.findall(r'(?:FROM|JOIN)\s+(\w+)\.(\w+)', text, re.IGNORECASE)
        for _, table in matches2:
            tables.add(table.lower())
        return tables
