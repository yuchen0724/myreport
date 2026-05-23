"""SQL 分析 API

提供 SQL 复杂度分析、慢查询检测、优化建议接口
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth_deps import get_current_user_id
from app.models.sql_analysis import SQLAnalysisResult
from app.services.sql_analyzer import sql_analyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sql", tags=["SQL分析"])


# ── 请求/响应 Schema ──

class SQLAnalyzeRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=50000, description="待分析的 SQL 语句")
    save: bool = Field(default=False, description="是否保存分析结果到数据库")


class SQLComplexityMetricsResponse(BaseModel):
    select_column_count: int = 0
    join_count: int = 0
    subquery_depth: int = 0
    group_by_count: int = 0
    order_by_count: int = 0
    function_call_count: int = 0
    where_condition_count: int = 0
    table_count: int = 0
    has_select_star: bool = False
    has_or_in_where: bool = False
    has_distinct: bool = False
    has_union: bool = False


class SQLIssueResponse(BaseModel):
    type: str
    severity: str
    position: str
    description: str


class SQLSuggestionResponse(BaseModel):
    action: str
    field: str
    description: str


class SQLAnalyzeResponse(BaseModel):
    sql_hash: str
    complexity_score: int
    complexity_level: str  # low/medium/high/critical
    metrics: SQLComplexityMetricsResponse
    issues: list[SQLIssueResponse]
    suggestions: list[SQLSuggestionResponse]
    estimated_time_ms: Optional[int] = None
    has_full_table_scan_risk: str = "no"
    missing_where_clause: str = "no"


class SQLAnalysisHistoryResponse(BaseModel):
    id: int
    sql_hash: str
    complexity_score: int
    complexity_level: str
    issues_count: int
    suggestions_count: int
    created_at: str

    class Config:
        from_attributes = True


# ── API 端点 ──

@router.post("/analyze", response_model=SQLAnalyzeResponse)
async def analyze_sql(
    request: SQLAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """分析 SQL 复杂度、检测慢查询模式、生成优化建议"""
    try:
        result = sql_analyzer.analyze(request.sql)
    except Exception as e:
        logger.error(f"SQL 分析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL 分析失败: {str(e)}",
        )

    # 可选保存到数据库
    if request.save:
        try:
            existing = db.query(SQLAnalysisResult).filter(
                SQLAnalysisResult.sql_hash == result["sql_hash"]
            ).first()
            if not existing:
                record = SQLAnalysisResult(
                    sql_hash=result["sql_hash"],
                    original_sql=request.sql.strip(),
                    complexity_score=result["complexity_score"],
                    complexity_level=result["complexity_level"],
                    select_column_count=result["metrics"]["select_column_count"],
                    join_count=result["metrics"]["join_count"],
                    subquery_depth=result["metrics"]["subquery_depth"],
                    group_by_count=result["metrics"]["group_by_count"],
                    order_by_count=result["metrics"]["order_by_count"],
                    function_call_count=result["metrics"]["function_call_count"],
                    where_condition_count=result["metrics"]["where_condition_count"],
                    issues=result["issues"],
                    suggestions=result["suggestions"],
                    estimated_time_ms=result["estimated_time_ms"],
                    has_full_table_scan_risk=result["has_full_table_scan_risk"],
                    missing_where_clause=result["missing_where_clause"],
                    analyzer_version=sql_analyzer.ANALYZER_VERSION,
                )
                db.add(record)
                db.commit()
        except Exception as e:
            logger.warning(f"保存分析结果失败（不影响返回）: {e}")
            db.rollback()

    return result


@router.get("/analyze/{sql_hash}", response_model=SQLAnalyzeResponse)
async def get_analysis_by_hash(
    sql_hash: str,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """根据 sql_hash 获取缓存的分析结果"""
    record = db.query(SQLAnalysisResult).filter(
        SQLAnalysisResult.sql_hash == sql_hash
    ).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该 SQL 的分析记录",
        )
    return record.to_dict()


@router.get("/history", response_model=list[SQLAnalysisHistoryResponse])
async def get_analysis_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    level: Optional[str] = Query(default=None, description="按复杂度等级筛选: low/medium/high/critical"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取 SQL 分析历史记录"""
    query = db.query(SQLAnalysisResult)
    if level:
        query = query.filter(SQLAnalysisResult.complexity_level == level)
    query = query.order_by(SQLAnalysisResult.created_at.desc())
    records = query.offset(offset).limit(limit).all()

    results = []
    for r in records:
        results.append({
            "id": r.id,
            "sql_hash": r.sql_hash,
            "complexity_score": r.complexity_score,
            "complexity_level": r.complexity_level,
            "issues_count": len(r.issues) if r.issues and isinstance(r.issues, list) else 0,
            "suggestions_count": len(r.suggestions) if r.suggestions and isinstance(r.suggestions, list) else 0,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        })
    return results


@router.get("/stats")
async def get_analysis_stats(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取 SQL 分析统计数据"""
    from sqlalchemy import func

    total = db.query(func.count(SQLAnalysisResult.id)).scalar() or 0

    level_counts = {}
    for row in db.query(
        SQLAnalysisResult.complexity_level,
        func.count(SQLAnalysisResult.id),
    ).group_by(SQLAnalysisResult.complexity_level).all():
        level_counts[row[0]] = row[1]

    avg_score = db.query(func.avg(SQLAnalysisResult.complexity_score)).scalar() or 0

    return {
        "total_analyses": total,
        "average_score": round(float(avg_score), 1),
        "level_distribution": level_counts,
    }
