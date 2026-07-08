"""
会话管理 API 请求/响应模型
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    """会话摘要"""
    id: str = Field(..., description="会话UUID")
    title: str = Field(..., description="会话标题")
    summary: Optional[str] = Field(None, description="会话摘要")
    total_messages: int = Field(0, description="消息总数")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "眼睛不舒服想预约医生",
                "summary": "患者描述眼睛干涩，想预约眼科医生",
                "total_messages": 12,
                "create_time": "2025-12-01T10:00:00",
                "update_time": "2025-12-01T10:30:00"
            }
        }


class ConversationListResponse(BaseModel):
    """会话列表响应"""
    conversations: List[ConversationSummary] = Field(..., description="会话列表")
    total: int = Field(..., description="总数")
    has_more: bool = Field(..., description="是否还有更多")

    class Config:
        json_schema_extra = {
            "example": {
                "conversations": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "眼睛不舒服想预约医生",
                        "total_messages": 12,
                        "create_time": "2025-12-01T10:00:00",
                        "update_time": "2025-12-01T10:30:00"
                    }
                ],
                "total": 5,
                "has_more": False
            }
        }


class MessageSiblingResponse(BaseModel):
    id: str
    message_type: str
    text_preview: str
    active: bool


class MessageResponse(BaseModel):
    """消息响应"""
    id: str = Field(..., description="消息UUID")
    message_order: int = Field(..., description="消息顺序")
    message_content: str = Field(..., description="消息内容")
    message_type: str = Field(..., description="消息类型 (user/assistant/system)")
    create_time: datetime = Field(..., description="创建时间")
    context: Optional[List[Dict[str, Any]]] = Field(None, description="上下文信息")
    parent_id: Optional[str] = None
    siblings_group_id: Optional[str] = None
    status: Optional[str] = None
    feedback: Optional[int] = None
    siblings: List[MessageSiblingResponse] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "message_order": 1,
                "message_content": "我眼睛最近很干涩",
                "message_type": "user",
                "create_time": "2025-12-01T10:00:00",
                "context": [
                    {"patient_info": {"name": "张三", "age": 35}},
                    {"conversation_stage": "health_consultation"}
                ]
            }
        }


class ConversationDetailResponse(BaseModel):
    """会话详情响应"""
    id: str = Field(..., description="会话UUID")
    user_type: str = Field(..., description="用户类型 (patient/doctor)")
    host_id: str = Field(..., description="会话主体ID")
    title: str = Field(..., description="会话标题")
    summary: Optional[str] = Field(None, description="会话摘要")
    total_messages: int = Field(0, description="消息总数")
    create_time: datetime = Field(..., description="创建时间")
    update_time: datetime = Field(..., description="更新时间")
    messages: List[MessageResponse] = Field(..., description="消息列表")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_type": "patient",
                "host_id": "550e8400-e29b-41d4-a716-446655440001",
                "title": "眼睛不舒服想预约医生",
                "total_messages": 2,
                "create_time": "2025-12-01T10:00:00",
                "update_time": "2025-12-01T10:30:00",
                "messages": [
                    {
                        "id": "msg-001",
                        "message_order": 1,
                        "message_content": "我眼睛最近很干涩",
                        "message_type": "user",
                        "create_time": "2025-12-01T10:00:00"
                    },
                    {
                        "id": "msg-002",
                        "message_order": 2,
                        "message_content": "您好，我了解到您眼睛干涩...",
                        "message_type": "assistant",
                        "create_time": "2025-12-01T10:00:05"
                    }
                ]
            }
        }


class DeleteConversationResponse(BaseModel):
    """删除会话响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    conversation_id: str = Field(..., description="会话ID")


class ActiveBranchRequest(BaseModel):
    through_message_id: str = Field(..., description="要切换到的路径经过消息ID")
