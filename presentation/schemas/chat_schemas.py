"""
聊天相关的Pydantic Schema
"""
import re
from typing import Optional, Dict, Any, List
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from presentation.schemas.ui_schemas import UIElements


class PageImage(BaseModel):
    """PDF 单页图片数据"""
    base64: str = Field(..., description="JPEG 图片的 base64 字符串")
    mime_type: str = Field("image/jpeg", description="图片 MIME 类型")
    page: int = Field(..., description="页码（从 1 开始）")


class AttachmentRef(BaseModel):
    """附件引用 - 由前端在 /api/upload 响应后构造，随 ChatRequest 发送"""
    file_type: str = Field(..., description="附件类型: 'image' | 'pdf'")
    filename: str = Field(..., description="原始文件名")
    minio_url: Optional[str] = Field(None, description="MinIO 备份 URL（不传给 AI，仅记录）")
    # 图片专用
    base64: Optional[str] = Field(None, description="图片 base64 字符串（不含 data: 前缀）")
    mime_type: Optional[str] = Field(None, description="图片 MIME 类型，如 image/jpeg")
    # PDF 专用
    page_images: Optional[List[PageImage]] = Field(None, description="PDF 各页图片列表")

# UUID格式正则表达式（支持带连字符和不带连字符两种格式）
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE
)


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID（如果为空会自动生成）")
    patient_id: str = Field(..., description="患者UUID（必需）")
    doctor_id: Optional[str] = Field(None, description="医生UUID（医生端必需，用于记录医生的会话）")
    agent_type: Optional[str] = Field("health", description="Agent类型 (health/report/reminder/research/compliance/recommendation)")
    role: Optional[str] = Field("patient", description="用户角色 (patient/doctor)")
    conversation_id: Optional[str] = Field(None, description="数据库会话ID（用于继续对话，为空则创建新会话）")
    parent_anchor_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("parent_anchor_id", "parentAnchorId"),
        description="编辑重发时传入新 user sibling 的 ID",
    )
    dual_answer: bool = Field(
        False,
        validation_alias=AliasChoices("dual_answer", "dualAnswer"),
        description="是否为双答案请求",
    )
    request_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("request_id", "requestId"),
        description="客户端请求追踪ID",
    )
    client_message_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("client_message_id", "clientMessageId"),
        description="客户端用户消息ID，用于双答案复用同一用户锚点",
    )
    client_assistant_message_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("client_assistant_message_id", "clientAssistantMessageId"),
        description="客户端助手消息ID",
    )
    execution_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("execution_id", "executionId"),
        description="客户端执行ID",
    )
    anchor_message_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("anchor_message_id", "anchorMessageId"),
        description="客户端锚点消息ID",
    )
    dual_answer_group_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("dual_answer_group_id", "dualAnswerGroupId"),
        description="双答案分组ID",
    )
    dual_answer_index: Optional[int] = Field(
        None,
        validation_alias=AliasChoices("dual_answer_index", "dualAnswerIndex"),
        description="双答案序号",
    )
    attachments: Optional[List[AttachmentRef]] = Field(None, description="附件列表（图片/PDF），由前端通过 /api/upload 上传后附带")

    @model_validator(mode="after")
    def infer_dual_answer_from_tracking_fields(self) -> "ChatRequest":
        if not self.dual_answer and (
            self.dual_answer_group_id is not None or self.dual_answer_index is not None
        ):
            self.dual_answer = True
        return self

    @field_validator('patient_id')
    @classmethod
    def validate_patient_uuid(cls, v: str) -> str:
        """验证patient_id必须是有效的UUID格式"""
        if not UUID_PATTERN.match(v):
            raise ValueError(f'patient_id 必须是有效的UUID格式，收到: "{v}"')
        return v

    @field_validator('doctor_id')
    @classmethod
    def validate_doctor_uuid(cls, v: Optional[str]) -> Optional[str]:
        """验证doctor_id如果提供必须是有效的UUID格式"""
        if v is not None and not UUID_PATTERN.match(v):
            raise ValueError(f'doctor_id 必须是有效的UUID格式，收到: "{v}"')
        return v
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "summary": "患者端请求",
                    "value": {
                        "message": "我想预约眼科医生",
                        "session_id": "sess-abc123",
                        "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                        "agent_type": "health",
                        "role": "patient",
                        "conversation_id": None,
                        "parent_anchor_id": None
                    }
                },
                {
                    "summary": "医生端请求",
                    "value": {
                        "message": "帮我分析这位患者的报告",
                        "session_id": "sess-doc456",
                        "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                        "doctor_id": "660e8400-e29b-41d4-a716-446655440001",
                        "agent_type": "report",
                        "role": "doctor",
                        "conversation_id": None,
                        "parent_anchor_id": None
                    }
                }
            ]
        }


class ChatResponse(BaseModel):
    """聊天响应"""

    response: str = Field(..., description="AI响应内容")
    session_id: str = Field(..., description="会话ID")
    conversation_id: Optional[str] = Field(None, description="数据库会话ID（用于后续继续对话）")
    is_completed: bool = Field(..., description="对话是否完成")
    stage: str = Field(..., description="当前对话阶段")
    agent_type: str = Field(..., description="当前使用的Agent类型")
    ui_elements: Optional[UIElements] = Field(None, description="结构化UI元素（交互选项）")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "您好，我是小Eye，请问有什么可以帮您？",
                "session_id": "sess-abc123",
                "conversation_id": "550e8400-e29b-41d4-a716-446655440099",
                "is_completed": False,
                "stage": "greeting",
                "agent_type": "health",
                "metadata": {
                    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                    "message_count": 1
                }
            }
        }
