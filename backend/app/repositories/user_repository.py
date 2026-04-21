from sqlalchemy.orm import Session
from typing import Optional
from app.models.user import User
from app.core.security import get_password_hash, verify_password


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, user_data: dict) -> User:
        db_user = User(
            username=user_data["username"],
            email=user_data["email"],
            password_hash=get_password_hash(user_data["password"]),
            role_id=user_data.get("role_id"),
            department_id=user_data.get("department_id"),
            data_scope=user_data.get("data_scope", "self"),
            is_active=user_data.get("is_active", True),
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def update(self, user: User, user_data: dict) -> User:
        for key, value in user_data.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> bool:
        self.db.delete(user)
        self.db.commit()
        return True

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            return None
        return user
