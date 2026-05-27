# backend/app/schemas/ai_analyst.py
"""
AI 数据分析师 - 请求/响应模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AIAnalystChatRequest(BaseModel):
    """AI 分析师对话请求"""
    message: str = Field(..., description="用户消息")
    data_source_id: int = Field(..., description="数据源 ID")
    conversation_id: Optional[str] = Field(None, description="对话 ID，用于多轮对话")
    group_id: Optional[int] = Field(None, description="集团 ID")


class AIAnalystToolCall(BaseModel):
    """工具调用记录"""
    tool_name: str = Field(..., description="工具名称")
    tool_input: Dict[str, Any] = Field(..., description="工具输入参数")
    tool_output: Optional[str] = Field(None, description="工具输出结果")
    error: Optional[str] = Field(None, description="工具调用错误")


class AIAnalystMessage(BaseModel):
    """单条消息"""
    role: str = Field(..., description="角色: user / assistant / tool")
    content: str = Field("", description="消息内容")
    tool_calls: Optional[List[AIAnalystToolCall]] = Field(None, description="工具调用列表")
    chart_config: Optional[Dict[str, Any]] = Field(None, description="图表配置")


class AIAnalystChatResponse(BaseModel):
    """AI 分析师对话响应"""
    conversation_id: str = Field(..., description="对话 ID")
    message: AIAnalystMessage = Field(..., description="助手消息")


class AIAnalystStreamChunk(BaseModel):
    """SSE 流式消息块"""
    type: str = Field(..., description="消息类型: token / tool_call / tool_result / chart / done / error")
    content: Optional[str] = Field(None, description="文本内容")
    tool_name: Optional[str] = Field(None, description="工具名称")
    tool_input: Optional[Dict[str, Any]] = Field(None, description="工具输入")
    tool_output: Optional[str] = Field(None, description="工具输出")
    chart_config: Optional[Dict[str, Any]] = Field(None, description="图表配置")
    error: Optional[str] = Field(None, description="错误信息")


class AIAnalystSchemaRequest(BaseModel):
    """获取表结构请求"""
    data_source_id: int = Field(..., description="数据源 ID")
    table_name: Optional[str] = Field(None, description="指定表名（可选）")


class AIAnalystSchemaResponse(BaseModel):
    """获取表结构响应"""
    tables: List[Dict[str, Any]] = Field(..., description="表结构信息")
    total_count: int = Field(..., description="表总数")
