"""统一鉴权依赖注入

提供 get_current_user_id / get_current_admin_user 等 FastAPI Depends，
替换所有 API 路由中硬编码的 current_user_id: int = 3。
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=True,
)


def get_current_user_id(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> int:
    """从 JWT token 中提取当前用户 ID，作为 FastAPI 依赖使用。

    Usage:
        @router.get("/xxx")
        async def handler(current_user_id: int = Depends(get_current_user_id)):
            ...
    """
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少 user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 JWT token 中提取完整 User 对象。

    比 get_current_user_id 多一次 DB 查询，
    仅在需要用户角色/权限检查时使用。
    """
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int | None = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少 user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """验证当前用户是否为管理员，是则返回 User 对象。

    用于需要管理员权限的 API 端点。
    管理员通过 role_id=1 标识（对应 roles 表中 name='admin' 的角色）。

    Raises:
        HTTPException 403: 非管理员用户
    """
    if current_user.role_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
