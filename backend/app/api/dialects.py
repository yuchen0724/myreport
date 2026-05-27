"""
SQL 方言 API — 提供方言列表和方言详情查询
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.core.auth_deps import get_current_user_id
from app.utils.sql_dialect import list_dialects, get_dialect, DIALECT_MAP, DialectAwareValidator

router = APIRouter(prefix="/api/dialects", tags=["SQL方言"])


class DialectBrief(BaseModel):
    """方言简要信息"""
    name: str
    label: str
    description: str


class DialectDetail(BaseModel):
    """方言详细信息"""
    name: str
    label: str
    description: str
    allowed_keywords: List[str]
    extra_functions: List[str]
    allow_multistatement: bool
    backtick_quoted: bool
    double_quote_quoted: bool
    require_select_start: bool


class DialectKeywordsResponse(BaseModel):
    """方言允许的关键字和函数"""
    dialect: str
    allowed_keywords: List[str]
    allowed_functions: List[str]


class SQLValidateRequest(BaseModel):
    """SQL 验证请求"""
    sql: str
    dialect: Optional[str] = Query(default=None, description="方言名称")


class SQLValidateResponse(BaseModel):
    """SQL 验证响应"""
    valid: bool
    message: str
    dialect: Optional[str] = None


@router.get("", response_model=List[DialectBrief])
async def get_dialects(current_user_id: int = Depends(get_current_user_id)):
    """获取所有支持的 SQL 方言列表"""
    return list_dialects()


@router.get("/{dialect_name}", response_model=DialectDetail)
async def get_dialect_detail(dialect_name: str, current_user_id: int = Depends(get_current_user_id)):
    """获取指定方言的详细信息"""
    detail = get_dialect(dialect_name)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"不支持的 SQL 方言: {dialect_name}"
        )
    return detail


@router.get("/{dialect_name}/keywords", response_model=DialectKeywordsResponse)
async def get_dialect_keywords(dialect_name: str, current_user_id: int = Depends(get_current_user_id)):
    """获取方言允许的关键字和函数列表"""
    if dialect_name not in DIALECT_MAP and dialect_name != "auto":
        raise HTTPException(
            status_code=404,
            detail=f"不支持的 SQL 方言: {dialect_name}"
        )
    return DialectKeywordsResponse(
        dialect=dialect_name,
        allowed_keywords=DialectAwareValidator.get_allowed_keywords(dialect_name),
        allowed_functions=DialectAwareValidator.get_allowed_functions(dialect_name),
    )


@router.post("/validate", response_model=SQLValidateResponse)
async def validate_sql_dialect(req: SQLValidateRequest, current_user_id: int = Depends(get_current_user_id)):
    """
    验证 SQL 语句是否安全（方言感知）

    根据选定的方言调整验证规则。
    """
    dialect_name = req.dialect if req.dialect and req.dialect != "auto" else None
    valid, message = DialectAwareValidator.validate(req.sql, dialect_name)
    return SQLValidateResponse(
        valid=valid,
        message=message,
        dialect=dialect_name,
    )
