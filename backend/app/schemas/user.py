from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role_id: Optional[int] = None
    department_id: Optional[int] = None
    data_scope: Optional[str] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    id: int
    role_id: Optional[int] = None
    department_id: Optional[int] = None
    data_scope: str = "self"
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    pass


class UserLogin(BaseModel):
    username: str
    password: str
