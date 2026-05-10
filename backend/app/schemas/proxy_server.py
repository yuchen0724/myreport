from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProxyServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="代理名称")
    proxy_type: str = Field(default="http", description="代理类型: http, https, socks5")
    host: str = Field(..., min_length=1, max_length=255, description="代理主机")
    port: int = Field(..., gt=0, le=65535, description="代理端口")
    username: Optional[str] = Field(None, max_length=100, description="代理用户名（可选）")
    password: Optional[str] = Field(None, description="代理密码（可选）")
    is_active: bool = Field(default=True, description="是否启用")


class ProxyServerCreate(ProxyServerBase):
    pass


class ProxyServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    proxy_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class ProxyServerResponse(BaseModel):
    id: int
    name: str
    proxy_type: str
    host: str
    port: int
    username: Optional[str] = None
    is_active: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProxyServerTestRequest(BaseModel):
    proxy_type: str = Field(..., description="代理类型: http, https, socks5")
    host: str = Field(..., description="代理主机")
    port: int = Field(..., gt=0, le=65535, description="代理端口")
    username: Optional[str] = None
    password: Optional[str] = None


class ProxyServerTestResponse(BaseModel):
    success: bool
    message: str