from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """获取用户列表"""
        return self.user_repo.get_all(skip, limit)

    def get_user(self, user_id: int) -> Optional[User]:
        """获取用户详情"""
        return self.user_repo.get_by_id(user_id)

    def create_user(self, user_data: UserCreate) -> User:
        """创建用户"""
        existing_user = self.user_repo.get_by_username(user_data.username)
        if existing_user:
            raise ValueError("用户名已存在")

        existing_email = self.user_repo.get_by_email(user_data.email)
        if existing_email:
            raise ValueError("邮箱已存在")

        return self.user_repo.create(user_data.model_dump())

    def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """更新用户"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None

        update_data = user_data.model_dump(exclude_unset=True)
        return self.user_repo.update(user, update_data)

    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return False
        return self.user_repo.delete(user)
