"""
Conversation 领域模型
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from domain.enums.agent_type import AgentType
from domain.enums.conversation_stage import ConversationStage


class Message(BaseModel):
    """对话消息"""
    
    role: str = Field(..., description="角色（user/assistant）")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "我想预约眼科医生",
                "timestamp": "2025-12-01T10:00:00"
            }
        }


class Conversation(BaseModel):
    """对话实体"""
    
    session_id: str = Field(..., description="会话ID")
    patient_id: str = Field(..., description="患者UUID")
    agent_type: AgentType = Field(..., description="智能体类型")
    stage: ConversationStage = Field(..., description="当前对话阶段")
    
    # 对话历史
    history: List[Message] = Field(default_factory=list, description="对话历史")
    
    # 状态
    is_completed: bool = Field(default=False, description="对话是否完成")
    
    # 元数据
    metadata: Optional[dict] = Field(default_factory=dict, description="附加元数据")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    
    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        message = Message(role=role, content=content)
        self.history.append(message)
        self.updated_at = datetime.now()
    
    def get_history_text(self) -> str:
        """获取格式化的对话历史文本"""
        history_text = ""
        for msg in self.history:
            role_name = "患者" if msg.role == "user" else "助手"
            history_text += f"{role_name}：{msg.content}\n"
        return history_text
    
    class Config:
        use_enum_values = False
        json_schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent_type": "health",
                "stage": "greeting",
                "history": [
                    {
                        "role": "assistant",
                        "content": "您好，我是小Eye，请问有什么可以帮您？"
                    },
                    {
                        "role": "user",
                        "content": "我想预约眼科医生"
                    }
                ],
                "is_completed": False
            }
        }

