from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DataSourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern="^(DORIS|MYSQL|POSTGRESQL)$")
    host: str = Field(..., min_length=1)
    port: int = Field(..., gt=0, le=65535)
    database: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    use_proxy: bool = Field(default=False, description="是否使用代理")
    proxy_server_id: Optional[int] = Field(None, description="关联的代理服务器ID")


class DataSourceCreate(DataSourceBase):
    pass


class DataSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, le=65535)
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None  # 空字符串表示不修改密码
    use_proxy: Optional[bool] = None
    proxy_server_id: Optional[int] = None
    is_active: Optional[bool] = None


class DataSourceInDB(DataSourceBase):
    id: int
    password_encrypted: str
    is_active: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DataSourceResponse(BaseModel):
    id: int
    name: str
    type: str
    host: str
    port: int
    database: str
    username: str
    password_decrypted: Optional[str] = None  # 编辑时返回解密密码
    use_proxy: bool = False
    proxy_server_id: Optional[int] = None
    is_active: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DataSourceTestRequest(BaseModel):
    type: str
    host: str
    port: int
    database: str
    username: str
    password: str


class DataSourceTestResponse(BaseModel):
    success: bool
    message: str
