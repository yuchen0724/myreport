"""查询结果订阅推送 Schema"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SubscriptionCreate(BaseModel):
    template_id: int
    cron_expression: str = Field(..., description="Cron 表达式，如 '0 8 * * 1'")
    notify_channel: str = Field(default="feishu", description="通知渠道: feishu / email")


class SubscriptionUpdate(BaseModel):
    cron_expression: Optional[str] = None
    notify_channel: Optional[str] = None
    is_active: Optional[bool] = None


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    template_id: int
    cron_expression: str
    notify_channel: str
    is_active: bool
    last_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    template_name: Optional[str] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True


class SubscriptionExecutionResponse(BaseModel):
    id: int
    subscription_id: int
    status: str
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
