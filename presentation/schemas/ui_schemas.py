"""
通用UI元素Schema - 交互选项和UI元素容器

被 chat_schemas.py 和 recommendation_schemas.py 共同引用。
OptionItem 和 UIElements 是跨Agent通用的UI结构，
ProductCard 仅在 recommendation_schemas.py 中定义（推荐Agent专用）。
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class OptionItem(BaseModel):
    """交互选项"""
    option_id: str = Field(..., description="选项唯一ID")
    label: str = Field(..., description="选项显示文本")
    value: str = Field(..., description="选项值（发送回AI的内容）")
    description: Optional[str] = Field(None, description="选项说明")
    icon: Optional[str] = Field(None, description="图标标识")


class UIElements(BaseModel):
    """UI结构化元素"""
    product_cards: Optional[list] = Field(None, description="产品卡片列表（仅推荐Agent使用）")
    options: Optional[List[OptionItem]] = Field(None, description="交互选项列表")
    ui_type: str = Field("none", description="UI类型: product_cards/options/none")
