"""
Agent管理相关的Pydantic Schema
"""
from typing import Optional
from pydantic import BaseModel, Field


class AgentStatusResponse(BaseModel):
    """Agent状态响应"""
    
    session_id: str = Field(..., description="会话ID")
    patient_id: str = Field(..., description="患者UUID")
    agent_type: str = Field(..., description="Agent类型")
    stage: str = Field(..., description="当前对话阶段")
    is_completed: bool = Field(..., description="对话是否完成")
    message_count: int = Field(..., description="消息数量")
    role: str = Field(..., description="用户角色")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent_type": "health",
                "stage": "greeting",
                "is_completed": False,
                "message_count": 2,
                "role": "patient"
            }
        }

