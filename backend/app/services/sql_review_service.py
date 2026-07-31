# backend/app/services/sql_review_service.py
"""
SQL 审核服务

职责：
1. 创建审核工单
2. 查询审核列表（支持过滤 + 分页）
3. 审核操作（通过 / 拒绝）
"""
import logging
import math
import json
from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.sql_review import SqlReview
from app.models.user import User
from app.models.template import Template
from app.schemas.sql_review import SqlReviewCreate, SqlReviewUpdate
from app.services.sql_review_analyzer import SqlReviewAnalyzer

logger = logging.getLogger(__name__)


class SqlReviewService:
    """SQL 审核服务"""

    def __init__(self, db: Session):
        self.db = db
        self.analyzer = SqlReviewAnalyzer()

    # ------------------------------------------------------------------
    # 提交审核
    # ------------------------------------------------------------------
    def create_review(self, data: SqlReviewCreate, current_user_id: int) -> SqlReview:
        """创建新的审核工单"""
        # 验证模板存在
        template = self.db.query(Template).filter(Template.id == data.template_id).first()
        if not template:
            raise ValueError("模板不存在")

        sql_content = data.sql_content or self._sql_from_template(template)
        ai_review = self.analyzer.analyze(sql_content, use_llm=False)
        review = SqlReview(
            template_id=data.template_id,
            submitted_by=current_user_id,
            status="pending",
            sql_content=sql_content,
            ai_risk_level=ai_review["risk_level"],
            ai_review=ai_review,
            ai_reviewed_at=datetime.now(timezone.utc),
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        logger.info("SQL 审核工单已创建: id=%d, submitted_by=%d", review.id, current_user_id)
        return review

    @staticmethod
    def _sql_from_template(template: Template) -> str:
        try:
            config = json.loads(template.config or "{}")
            return str(config.get("sql") or "")
        except (TypeError, ValueError):
            return ""

    def refresh_ai_review(self, review_id: int, use_llm: bool = True) -> SqlReview:
        review = self.get_review(review_id)
        if not review:
            raise ValueError("审核工单不存在")
        ai_review = self.analyzer.analyze(review.sql_content or "", use_llm=use_llm)
        review.ai_risk_level = ai_review["risk_level"]
        review.ai_review = ai_review
        review.ai_reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(review)
        return review

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def get_review(self, review_id: int) -> Optional[SqlReview]:
        """获取单个审核工单（带关联信息）"""
        return (
            self.db.query(SqlReview)
            .filter(SqlReview.id == review_id)
            .first()
        )

    def list_reviews(
        self,
        status: Optional[str] = None,
        submitted_by: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页查询审核列表"""
        query = self.db.query(SqlReview)
        if status:
            query = query.filter(SqlReview.status == status)
        if submitted_by:
            query = query.filter(SqlReview.submitted_by == submitted_by)

        total = query.count()
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        items = (
            query.order_by(desc(SqlReview.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ------------------------------------------------------------------
    # 审核操作
    # ------------------------------------------------------------------
    def approve(self, review_id: int, reviewer_id: int, comment: Optional[str] = None) -> SqlReview:
        """审核通过"""
        return self._perform_review(review_id, reviewer_id, "approved", comment)

    def reject(self, review_id: int, reviewer_id: int, comment: Optional[str] = None) -> SqlReview:
        """审核拒绝"""
        return self._perform_review(review_id, reviewer_id, "rejected", comment)

    def _perform_review(
        self,
        review_id: int,
        reviewer_id: int,
        target_status: str,
        comment: Optional[str],
    ) -> SqlReview:
        review = self.db.query(SqlReview).filter(SqlReview.id == review_id).first()
        if not review:
            raise ValueError("审核工单不存在")
        if review.status != "pending":
            raise ValueError("该工单已审核，不可重复操作")

        review.status = target_status
        review.reviewer_id = reviewer_id
        review.review_comment = comment
        review.reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(review)
        logger.info("SQL 审核工单 %s: id=%d, reviewer=%d", target_status, review_id, reviewer_id)
        return review
