"""SQL 修正日志服务 — 存储和匹配历史修正案例"""

import re
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.sql_correction import SqlCorrection

logger = logging.getLogger(__name__)


class SqlCorrectionService:
    """SQL 修正日志服务"""

    def __init__(self, db: Session):
        self.db = db

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
        # 去重检查
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
        """保存一条修正记录"""
        # 提取表名
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
        logger.info("[SqlCorrection] 保存修正: id=%s question=%s", record.id, question[:60])
        return record

    def find_matches(
        self,
        question: str,
        data_source_id: Optional[int] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """根据问题和数据源查找最相关历史修正"""
        current_tables = self._extract_tables(question)

        # 先查当前数据源
        query = self.db.query(SqlCorrection).filter(SqlCorrection.is_active == True)
        if data_source_id is not None:
            query = query.filter(SqlCorrection.data_source_id == data_source_id)
        records = query.order_by(SqlCorrection.created_at.desc()).limit(30).all()

        # 如果当前数据源记录不足，补充跨数据源的记录
        if len(records) < 5:
            cross_records = (
                self.db.query(SqlCorrection)
                .filter(SqlCorrection.is_active == True)
                .order_by(SqlCorrection.created_at.desc())
                .limit(30)
                .all()
            )
            existing_ids = {r.id for r in records}
            for r in cross_records:
                if r.id not in existing_ids:
                    records.append(r)
                    existing_ids.add(r.id)

        if not records:
            return []

        # 按关键词匹配度打分
        scored = []
        for r in records:
            score = 0
            r_tables = set(t.strip() for t in (r.table_names or "").split(",") if t.strip())
            overlap = current_tables & r_tables
            score += len(overlap) * 3

            q_words = set(re.findall(r'\w+', question.lower()))
            r_words = set(re.findall(r'\w+', r.question.lower()))
            common_words = q_words & r_words
            score += len(common_words)

            # 优质案例加分（original_sql为空表示一次性成功）
            if not r.original_sql:
                score += 1

            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: -x[0])
        results = []
        for score, r in scored[:top_k]:
            results.append({
                "id": r.id,
                "data_source_id": r.data_source_id,
                "question": r.question[:80],
                "original_sql": r.original_sql,
                "corrected_sql": r.corrected_sql,
                "user_feedback": r.user_feedback,
                "score": score,
            })

        return results

    def build_few_shot_prompt(self, question: str, data_source_id: int) -> str:
        """构建 few-shot 示例 prompt 段落（跨数据源 RAG）"""
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
        # 匹配 FROM/JOIN 后的表名
        matches = re.findall(r'(?:FROM|JOIN)\s+([`"]?)(?:ads_cockpit_freedom\.)?(\w+)\1', text, re.IGNORECASE)
        for _, table in matches:
            tables.add(table.lower())
        # 也匹配完整的 库名.表名
        matches2 = re.findall(r'(?:FROM|JOIN)\s+(\w+)\.(\w+)', text, re.IGNORECASE)
        for _, table in matches2:
            tables.add(table.lower())
        return tables
