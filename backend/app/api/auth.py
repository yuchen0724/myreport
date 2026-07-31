from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.token_blacklist import add_to_blacklist
from app.schemas.auth import Token
from app.services.auth_service import AuthService
from app.core.auth_deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["认证"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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
    current_user: User = Depends(get_current_user),
):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role_id": current_user.role_id,
        "department_id": current_user.department_id,
        "data_scope": current_user.data_scope,
        "is_active": current_user.is_active,
    }
