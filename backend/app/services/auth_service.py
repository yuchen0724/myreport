from datetime import timedelta
from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token
from app.core.security import create_access_token
from app.config import get_settings

settings = get_settings()


class AuthService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def login(self, username: str, password: str) -> Token:
        """用户登录"""
        user = self.user_repo.authenticate(username, password)
        if not user:
            raise ValueError("用户名或密码错误")
        if not user.is_active:
            raise ValueError("用户已被禁用")

        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id},
            expires_delta=access_token_expires
        )
        return Token(access_token=access_token)

    def get_current_user(self, username: str) -> dict:
        """获取当前用户信息"""
        user = self.user_repo.get_by_username(username)
        if not user:
            raise ValueError("用户不存在")
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role_id": user.role_id,
            "department_id": user.department_id,
            "data_scope": user.data_scope,
            "is_active": user.is_active,
        }
