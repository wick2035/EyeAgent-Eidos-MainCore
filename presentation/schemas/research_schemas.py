"""
ResearchAgent API Schemas
医问通科研Agent请求/响应模型
"""
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
from datetime import datetime

# UUID格式正则表达式
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE
)


class WebSearchType(str, Enum):
    """网页搜索类型"""
    GENERAL = "general"    # 通用搜索
    PUBMED = "pubmed"      # PubMed医学文献
    SCHOLAR = "scholar"    # Google Scholar学术搜索


class ResearchChatRequest(BaseModel):
    """科研对话请求"""

    message: str = Field(..., description="用户消息")
    doctor_id: str = Field(..., description="医生UUID（必需）")
    patient_id: Optional[str] = Field(
        None,
        description="科研模式必须为空；字段仅为 wire compatibility 保留",
    )
    session_id: Optional[str] = Field(None, description="会话ID")
    conversation_id: Optional[str] = Field(None, description="数据库会话ID")
    enable_institution_data: bool = Field(False, description="机构数据库访问开关")
    enable_web_search: bool = Field(False, description="网页搜索开关")
    web_search_types: List[str] = Field(
        default_factory=list,
        description="搜索类型列表 ['general', 'pubmed', 'scholar']"
    )

    @field_validator('doctor_id')
    @classmethod
    def validate_doctor_uuid(cls, v: str) -> str:
        """验证doctor_id必须是有效的UUID格式"""
        if not UUID_PATTERN.match(v):
            raise ValueError(f'doctor_id 必须是有效的UUID格式，收到: "{v}"')
        return v

    @field_validator('patient_id')
    @classmethod
    def validate_patient_uuid(cls, v: Optional[str]) -> Optional[str]:
        """验证patient_id如果提供必须是有效的UUID格式"""
        if v is not None and not UUID_PATTERN.match(v):
            raise ValueError(f'patient_id 必须是有效的UUID格式，收到: "{v}"')
        return v

    @field_validator('web_search_types')
    @classmethod
    def validate_search_types(cls, v: List[str]) -> List[str]:
        """验证搜索类型有效性"""
        valid_types = {"general", "pubmed", "scholar"}
        for search_type in v:
            if search_type not in valid_types:
                raise ValueError(f'无效的搜索类型: "{search_type}"，有效值: {valid_types}')
        return v

    @model_validator(mode="after")
    def validate_no_patient_binding(self):
        if self.patient_id is not None:
            raise ValueError("科研模式不得绑定患者")
        return self


class ResearchChatResponse(BaseModel):
    """科研对话响应"""

    response: str = Field(..., description="AI响应内容")
    session_id: str = Field(..., description="会话ID")
    conversation_id: Optional[str] = Field(None, description="数据库会话ID")
    is_completed: bool = Field(..., description="对话是否完成")
    stage: str = Field(..., description="当前对话阶段")
    agent_type: str = Field(default="research", description="Agent类型")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加元数据")


class SSEEventType(str, Enum):
    """SSE事件类型"""
    START = "start"        # 开始处理
    CHUNK = "chunk"        # 内容块
    TOOL_CALL = "tool_call"  # 工具调用
    DONE = "done"          # 完成
    ERROR = "error"        # 错误


class SSEMessage(BaseModel):
    """SSE消息格式"""
    event: str = Field(default="message", description="事件类型")
    data: Dict[str, Any] = Field(..., description="消息内容")


class ConversationSummary(BaseModel):
    """会话摘要"""
    id: str
    title: str
    summary: Optional[str] = None
    total_messages: int
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


class ResearchConversationListResponse(BaseModel):
    """科研会话列表响应"""
    conversations: List[ConversationSummary] = Field(..., description="会话列表")
    total: int = Field(..., description="总数")
    has_more: bool = Field(..., description="是否还有更多")


class ResearchStatsResponse(BaseModel):
    """科研数据统计响应"""
    total_patients: int = Field(0, description="总患者数")
    total_appointments: int = Field(0, description="总预约数")
    total_prescriptions: int = Field(0, description="总处方数")
    date_range: Optional[Dict[str, str]] = Field(None, description="日期范围")
    anonymization_enabled: bool = Field(True, description="是否启用脱敏")


class WebSearchResult(BaseModel):
    """网页搜索结果"""
    title: str = Field(..., description="标题")
    url: str = Field(..., description="链接")
    snippet: str = Field(..., description="摘要")
    source: str = Field(..., description="来源类型")


class WebSearchResponse(BaseModel):
    """网页搜索响应"""
    query: str = Field(..., description="搜索查询")
    total_results: int = Field(..., description="总结果数")
    results_by_type: Dict[str, List[WebSearchResult]] = Field(..., description="按类型分组的结果")
