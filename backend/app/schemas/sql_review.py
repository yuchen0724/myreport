# backend/app/schemas/sql_review.py
from pydantic import ConfigDict, BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime


class SqlReviewCreate(BaseModel):
    """创建 SQL 审核工单"""
    template_id: int = Field(..., description="关联的模板 ID")
    sql_content: Optional[str] = Field(None, description="待审核的 SQL 内容")


class SqlReviewUpdate(BaseModel):
    """更新 SQL 审核工单（审核操作）"""
    status: str = Field(..., description="审核结果: approved / rejected")
    review_comment: Optional[str] = Field(None, description="审核意见")


class SqlReviewResponse(BaseModel):
    """SQL 审核工单响应"""
    id: int
    template_id: int
    submitted_by: int
    status: str
    reviewer_id: Optional[int] = None
    review_comment: Optional[str] = None
    sql_content: Optional[str] = None
    ai_risk_level: Optional[str] = None
    ai_review: Optional[Dict[str, Any]] = None
    ai_reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    # 额外展示字段
    submitter_name: Optional[str] = None
    reviewer_name: Optional[str] = None
    template_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SqlReviewListResponse(BaseModel):
    """分页审核列表响应"""
    items: list[SqlReviewResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
