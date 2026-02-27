"""
RecommendationAgent API Schemas
医药产品推荐Agent请求/响应模型

包含产品卡片(ProductCard)、交互选项(OptionItem)、UI元素(UIElements)等结构化模型
"""
import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

# UUID格式正则表达式
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
    re.IGNORECASE
)


# ========== UI 结构化元素模型 ==========

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


class OptionItem(BaseModel):
    """交互选项"""
    option_id: str = Field(..., description="选项唯一ID")
    label: str = Field(..., description="选项显示文本")
    value: str = Field(..., description="选项值（发送回AI的内容）")
    description: Optional[str] = Field(None, description="选项说明")
    icon: Optional[str] = Field(None, description="图标标识")


class UIElements(BaseModel):
    """UI结构化元素"""
    product_cards: Optional[List[ProductCard]] = Field(None, description="产品卡片列表")
    options: Optional[List[OptionItem]] = Field(None, description="交互选项列表")
    ui_type: str = Field("none", description="UI类型: product_cards/options/none")


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
