from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """获取用户列表"""
        return self.db.query(User).offset(skip).limit(limit).all()

    def get_user(self, user_id: int) -> Optional[User]:
        """获取用户详情"""
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, user_data: UserCreate) -> User:
        """创建用户"""
        # 检查用户名是否已存在
        existing_user = self.db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            raise ValueError("用户名已存在")

        # 检查邮箱是否已存在
        existing_email = self.db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise ValueError("邮箱已存在")

        # 创建用户
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role_id=user_data.role_id,
            department_id=user_data.department_id,
            data_scope=user_data.data_scope,
            is_active=True
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """更新用户"""
        user = self.get_user(user_id)
        if not user:
            return None

        # 更新字段
        update_data = user_data.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["password_hash"] = get_password_hash(update_data.pop("password"))

        for field, value in update_data.items():
            setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        user = self.get_user(user_id)
        if not user:
            return False

        self.db.delete(user)
        self.db.commit()
        return True
