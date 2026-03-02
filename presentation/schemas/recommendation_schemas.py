"""
RecommendationAgent API Schemas
医药产品推荐Agent请求/响应模型

ProductCard 为推荐Agent专用模型。
OptionItem、UIElements 从 ui_schemas.py 共享导入。
"""
import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

from presentation.schemas.ui_schemas import OptionItem, UIElements

# UUID格式正则表达式
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE
)


# ========== 推荐Agent专用模型 ==========

class ProductCard(BaseModel):
    """产品推荐卡片"""
    product_id: str = Field(..., description="产品UUID")
    product_name: str = Field(..., description="产品名称")
    generic_name: Optional[str] = Field(None, description="通用名")
    product_type: str = Field(..., description="产品类型: PRESCRIPTION/OTC/DEVICE")
    category: str = Field("", description="产品分类")
    image_url: Optional[str] = Field(None, description="产品图片URL")
    unit_price: float = Field(..., description="单价（元）")
    specification: Optional[str] = Field(None, description="规格")
    stock_status: str = Field("IN_STOCK", description="库存状态: IN_STOCK/LOW_STOCK/OUT_OF_STOCK")
    indications: Optional[str] = Field(None, description="适应症")
    is_prescription: bool = Field(False, description="是否需要处方")
    action_type: str = Field(..., description="操作类型: ADD_TO_CART/PRESCRIBE/VIEW_DETAIL")
    action_label: str = Field(..., description="操作按钮文本")


# ========== 请求/响应模型 ==========

class RecommendationChatRequest(BaseModel):
    """产品推荐对话请求"""

    message: str = Field(..., description="用户消息")
    patient_id: str = Field(..., description="患者UUID（必需）")
    doctor_id: Optional[str] = Field(None, description="医生UUID（医生端必需）")
    role: Optional[str] = Field("patient", description="用户角色: patient/doctor")
    session_id: Optional[str] = Field(None, description="会话ID")
    conversation_id: Optional[str] = Field(None, description="数据库会话ID")

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

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> str:
        """验证角色"""
        if v and v not in ("patient", "doctor"):
            raise ValueError(f'role 必须是 "patient" 或 "doctor"，收到: "{v}"')
        return v or "patient"


class RecommendationChatResponse(BaseModel):
    """产品推荐对话响应"""

    response: str = Field(..., description="AI响应文本内容（纯文本，不含卡片标记）")
    session_id: str = Field(..., description="会话ID")
    conversation_id: Optional[str] = Field(None, description="数据库会话ID")
    is_completed: bool = Field(..., description="对话是否完成")
    stage: str = Field(..., description="当前对话阶段")
    agent_type: str = Field(default="recommendation", description="Agent类型")
    ui_elements: Optional[UIElements] = Field(None, description="结构化UI元素（产品卡片/交互选项）")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="附加元数据")
