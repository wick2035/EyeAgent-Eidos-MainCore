"""
对话持久化实体模型
映射到数据库表 chat_conversation 和 chat_message
"""
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import json


class ChatConversationEntity(BaseModel):
    """
    对话会话实体
    映射到 chat_conversation 表
    """
    id: str = Field(..., description="会话UUID")
    user_type: str = Field(..., description="用户类型 (patient/doctor)")
    host_id: str = Field(..., description="会话主体ID（患者/医生UUID）")
    title: str = Field(default="Untitled", description="会话标题")
    summary: Optional[str] = Field(default=None, description="会话摘要")
    total_messages: int = Field(default=0, description="消息总数")
    create_time: datetime = Field(default_factory=datetime.now, description="创建时间")
    create_by: Optional[str] = Field(default=None, description="创建者")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间")
    update_by: Optional[str] = Field(default=None, description="更新者")
    deleted: bool = Field(default=False, description="是否删除")
    version: int = Field(default=1, description="版本号（乐观锁）")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_type": "patient",
                "host_id": "550e8400-e29b-41d4-a716-446655440001",
                "title": "眼睛不舒服想预约医生",
                "summary": "患者描述眼睛干涩，想预约眼科医生",
                "total_messages": 12,
                "create_time": "2025-12-01T10:00:00",
                "update_time": "2025-12-01T10:30:00",
                "deleted": False,
                "version": 1
            }
        }


class ChatMessageEntity(BaseModel):
    """
    对话消息实体
    映射到 chat_message 表
    """
    id: str = Field(..., description="消息UUID")
    chat_id: str = Field(..., description="所属会话ID (FK -> chat_conversation)")
    parent_id: Optional[str] = Field(default=None, description="父消息ID，None 表示根消息")
    message_order: int = Field(..., description="消息顺序")
    message_content: str = Field(..., description="消息内容")
    message_type: str = Field(..., description="消息类型 (user/assistant/system)")
    sender_id: Optional[str] = Field(default=None, description="发送者ID")
    context: Optional[str] = Field(default=None, description="上下文JSON")
    token_used: Optional[int] = Field(default=None, description="使用的token数")
    status: str = Field(default="success", description="消息状态 (running/success/failed/cancelled)")
    error_message: Optional[str] = Field(default=None, description="错误信息（失败时）")
    create_time: datetime = Field(default_factory=datetime.now, description="创建时间")
    create_by: Optional[str] = Field(default=None, description="创建者")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间")
    update_by: Optional[str] = Field(default=None, description="更新者")
    deleted: bool = Field(default=False, description="是否删除")
    version: int = Field(default=1, description="版本号")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "chat_id": "550e8400-e29b-41d4-a716-446655440000",
                "parent_id": None,
                "message_order": 1,
                "message_content": "我眼睛最近很干涩",
                "message_type": "user",
                "sender_id": "550e8400-e29b-41d4-a716-446655440001",
                "context": "[{\"patient_info\": {...}}, {\"conversation_stage\": \"health_consultation\"}]",
                "status": "success",
                "error_message": None,
                "create_time": "2025-12-01T10:00:00",
                "deleted": False,
                "version": 1
            }
        }

    def get_context_dict(self) -> List[Dict[str, Any]]:
        """
        解析 context JSON 字符串为列表

        Returns:
            List[Dict]: 上下文列表 [patient_info, stage, tool_results, citations]
        """
        if not self.context:
            return []
        try:
            return json.loads(self.context)
        except json.JSONDecodeError:
            return []

    def set_context_from_dict(self, context_list: List[Dict[str, Any]]):
        """
        将列表序列化为 context JSON 字符串

        Args:
            context_list: 上下文列表
        """
        self.context = json.dumps(context_list, ensure_ascii=False)


class MessageContext(BaseModel):
    """
    消息上下文模型
    用于构建 context JSON
    """
    patient_info: Optional[Dict[str, Any]] = Field(default=None, description="患者信息")
    conversation_stage: Optional[str] = Field(default=None, description="对话阶段")
    tool_results: Optional[List[Dict[str, Any]]] = Field(default=None, description="统一结构的工具调用结果")
    citations: Optional[List[Dict[str, Any]]] = Field(default=None, description="前端 CitationBlock 引用来源")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="其他元数据")

    def to_context_list(self) -> List[Dict[str, Any]]:
        """
        转换为 context 列表格式

        Returns:
            List[Dict]: [{"patient_info": ...}, {"conversation_stage": ...}, {"tool_results": ...}, {"citations": ...}]
        """
        context_list = []
        if self.patient_info:
            context_list.append({"patient_info": self.patient_info})
        if self.conversation_stage:
            context_list.append({"conversation_stage": self.conversation_stage})
        if self.tool_results:
            context_list.append({"tool_results": self.tool_results})
        if self.citations:
            context_list.append({"citations": self.citations})
        if self.metadata:
            context_list.append({"metadata": self.metadata})
        return context_list

    def to_json(self) -> str:
        """
        转换为 JSON 字符串

        Returns:
            str: JSON 字符串
        """
        return json.dumps(self.to_context_list(), ensure_ascii=False)

    @classmethod
    def from_context_list(cls, context_list: List[Dict[str, Any]]) -> "MessageContext":
        """
        从 context 列表构建 MessageContext

        Args:
            context_list: 上下文列表

        Returns:
            MessageContext: 实例
        """
        patient_info = None
        conversation_stage = None
        tool_results = None
        citations = None
        metadata = None

        for item in context_list:
            if "patient_info" in item:
                patient_info = item["patient_info"]
            elif "conversation_stage" in item:
                conversation_stage = item["conversation_stage"]
            elif "tool_results" in item:
                tool_results = item["tool_results"]
            elif "citations" in item:
                citations = item["citations"]
            elif "metadata" in item:
                metadata = item["metadata"]

        return cls(
            patient_info=patient_info,
            conversation_stage=conversation_stage,
            tool_results=tool_results,
            citations=citations,
            metadata=metadata
        )
