"""
ComplianceAgent API Schemas
合规性审查Agent请求/响应模型
"""
import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

# UUID格式正则表达式
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE
)


class ComplianceChatRequest(BaseModel):
    """合规审查对话请求"""

    message: str = Field(..., description="用户消息")
    doctor_id: str = Field(..., description="医生UUID（必需）")
    patient_id: str = Field(..., description="患者UUID（必需，审查目标患者）")
    session_id: Optional[str] = Field(None, description="会话ID")
    conversation_id: Optional[str] = Field(None, description="数据库会话ID")

    @field_validator('doctor_id')
    @classmethod
    def validate_doctor_uuid(cls, v: str) -> str:
        """验证doctor_id必须是有效的UUID格式"""
        if not UUID_PATTERN.match(v):
            raise ValueError(f'doctor_id 必须是有效的UUID格式，收到: "{v}"')
        return v

    @field_validator('patient_id')
    @classmethod
    def validate_patient_uuid(cls, v: str) -> str:
        """验证patient_id必须是有效的UUID格式"""
        if not UUID_PATTERN.match(v):
            raise ValueError(f'patient_id 必须是有效的UUID格式，收到: "{v}"')
        return v


class ComplianceChatResponse(BaseModel):
    """合规审查对话响应"""

    response: str = Field(..., description="AI响应内容")
    session_id: str = Field(..., description="会话ID")
    conversation_id: Optional[str] = Field(None, description="数据库会话ID")
    is_completed: bool = Field(..., description="对话是否完成")
    stage: str = Field(..., description="当前对话阶段")
    agent_type: str = Field(default="compliance", description="Agent类型")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加元数据")
