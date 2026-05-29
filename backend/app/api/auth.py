from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.token_blacklist import add_to_blacklist, is_blacklisted
from app.schemas.auth import Token
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["认证"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _validate_token_not_blacklisted(token: str) -> dict:
    """验证 token 并检查黑名单，返回 payload"""
    # 先检查黑名单
    if is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 再解码 JWT
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    """用户登录"""
    body = (await request.body()).decode()
    form_data = parse_qs(body, keep_blank_values=True)
    username = form_data.get("username", [""])[0]
    password = form_data.get("password", [""])[0]

    auth_service = AuthService(db)
    try:
        token = auth_service.login(username, password)
        return token
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """用户登出，将当前 token 加入黑名单"""
    if add_to_blacklist(token):
        return {"message": "登出成功"}
    # 即使添加黑名单失败，也返回成功（可能 token 已过期）
    return {"message": "已登出"}


@router.get("/me")
async def get_current_user_info(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """获取当前用户信息"""
    payload = _validate_token_not_blacklisted(token)

    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
        )

    auth_service = AuthService(db)
    try:
        user_info = auth_service.get_current_user(username)
        return user_info
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
