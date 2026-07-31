"""统一鉴权依赖注入

提供 get_current_user_id / get_current_admin_user 等 FastAPI Depends，
替换所有 API 路由中硬编码的 current_user_id: int = 3。
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.token_blacklist import is_blacklisted
from app.models.user import User
from app.models.role import Role

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=True,
)


def _decode_and_validate_token(token: str) -> dict:
    """解码并验证 token，包括黑名单检查"""
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
    payload = _decode_and_validate_token(token)

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
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或令牌已失效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
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
    payload = _decode_and_validate_token(token)

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
    db: Session = Depends(get_db),
) -> User:
    """验证当前用户是否为管理员，是则返回 User 对象。

    用于需要管理员权限的 API 端点。
    通过查询 roles 表中 name='admin' 的角色进行验证。

    Raises:
        HTTPException 403: 非管理员用户
    """
    # 查询 roles 表获取 admin 角色的 ID
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if admin_role is None or current_user.role_id != admin_role.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
