# backend/app/api/sql_reviews.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id, get_current_admin_user, get_current_user
from app.models.user import User
from app.schemas.sql_review import (
    SqlReviewCreate,
    SqlReviewUpdate,
    SqlReviewResponse,
    SqlReviewListResponse,
)
from app.services.sql_review_service import SqlReviewService

router = APIRouter(prefix="/api/reviews", tags=["SQL审核"])


def _enrich_review(review, db: Session) -> SqlReviewResponse:
    """补充审核工单的关联名称信息"""
    resp = SqlReviewResponse.model_validate(review)
    if review.submitter:
        resp.submitter_name = review.submitter.username
    if review.reviewer:
        resp.reviewer_name = review.reviewer.username
    if review.template:
        resp.template_name = review.template.name
    return resp


# ---- 提交审核（所有已登录用户） ----

@router.post("", response_model=SqlReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    data: SqlReviewCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """提交 SQL 审核工单"""
    service = SqlReviewService(db)
    try:
        review = service.create_review(data, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_review(review, db)


# ---- 查询审核列表（所有已登录用户可查看） ----

@router.get("", response_model=SqlReviewListResponse)
async def list_reviews(
    review_status: Optional[str] = Query(None, alias="status", description="状态过滤: pending/approved/rejected"),
    submitted_by: Optional[int] = Query(None, description="提交者用户 ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核列表"""
    service = SqlReviewService(db)
    is_admin = bool(current_user.role and current_user.role.name == "admin")
    effective_submitter = submitted_by if is_admin else current_user.id
    result = service.list_reviews(
        status=review_status,
        submitted_by=effective_submitter,
        page=page,
        page_size=page_size,
    )
    items = [_enrich_review(r, db) for r in result["items"]]
    return SqlReviewListResponse(
        items=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


# ---- 查询单个审核详情 ----

@router.get("/{review_id}", response_model=SqlReviewResponse)
async def get_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核工单详情"""
    service = SqlReviewService(db)
    review = service.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="审核工单不存在")
    is_admin = bool(current_user.role and current_user.role.name == "admin")
    if review.submitted_by != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="无权查看该审核工单")
    return _enrich_review(review, db)


@router.post("/{review_id}/ai-review", response_model=SqlReviewResponse)
async def refresh_ai_review(
    review_id: int,
    use_llm: bool = Query(True, description="是否生成 LLM 中文审核摘要"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """重新执行机器预审；结构化规则始终运行，LLM 解释失败时自动降级。"""
    try:
        review = SqlReviewService(db).refresh_ai_review(review_id, use_llm=use_llm)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _enrich_review(review, db)


# ---- 审核操作（仅管理员） ----

@router.put("/{review_id}/review", response_model=SqlReviewResponse)
async def review_sql(
    review_id: int,
    data: SqlReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """审核通过 / 拒绝（仅管理员）"""
    if data.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status 必须是 approved 或 rejected")

    service = SqlReviewService(db)
    try:
        if data.status == "approved":
            review = service.approve(review_id, current_user.id, data.review_comment)
        else:
            review = service.reject(review_id, current_user.id, data.review_comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _enrich_review(review, db)


# ---- 删除审核工单（仅提交者本人可删） ----

@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """删除审核工单（仅提交者可删除）"""
    service = SqlReviewService(db)
    review = service.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="审核工单不存在")
    if review.submitted_by != current_user_id:
        raise HTTPException(status_code=403, detail="只能删除自己提交的工单")
    if review.status != "pending":
        raise HTTPException(status_code=400, detail="已审核的工单不可删除")

    db.delete(review)
    db.commit()
