"""
UI元素解析工具 - 通用[OPTIONS]和[PRODUCT_CARDS]标记解析

从AI响应文本中提取结构化UI元素（选项按钮、产品卡片），
供所有Agent路由共享使用。

- parse_ui_elements(): 完整解析，用于 RecommendationAgent（支持 PRODUCT_CARDS + OPTIONS）
- parse_options_only(): 仅解析 OPTIONS，用于 Health/Reminder/Report Agent
"""
import re
import json
import logging
from typing import Tuple, Optional

from presentation.schemas.ui_schemas import OptionItem, UIElements
from presentation.schemas.recommendation_schemas import ProductCard

logger = logging.getLogger(__name__)

# UI元素标记正则（模块级编译，复用）
PRODUCT_CARDS_PATTERN = re.compile(
    r'\[PRODUCT_CARDS\]\s*([\s\S]*?)\s*\[/PRODUCT_CARDS\]',
    re.DOTALL
)
OPTIONS_PATTERN = re.compile(
    r'\[OPTIONS\]\s*([\s\S]*?)\s*\[/OPTIONS\]',
    re.DOTALL
)


def parse_ui_elements(response_text: str) -> Tuple[str, Optional[UIElements]]:
    """
    从AI响应文本中解析UI元素标记（完整版：PRODUCT_CARDS + OPTIONS）

    用于 RecommendationAgent，支持产品卡片和交互选项。
    产品卡片优先级高于选项（二选一）。

    Args:
        response_text: 原始AI响应文本

    Returns:
        (clean_text, ui_elements): 清理后的文本和UI元素对象
    """
    ui_elements = None
    clean_text = response_text

    # 解析产品卡片
    product_match = PRODUCT_CARDS_PATTERN.search(response_text)
    if product_match:
        try:
            cards_json = product_match.group(1).strip()
            cards_data = json.loads(cards_json)
            if isinstance(cards_data, list):
                product_cards = []
                for card in cards_data:
                    try:
                        product_cards.append(ProductCard(**card))
                    except Exception as e:
                        logger.warning(f"[UIParser] 解析产品卡片失败: {e}")
                        continue
                if product_cards:
                    ui_elements = UIElements(
                        product_cards=[c.model_dump() for c in product_cards],
                        ui_type="product_cards"
                    )
        except json.JSONDecodeError as e:
            logger.warning(f"[UIParser] 产品卡片JSON解析失败: {e}")

        # 从文本中移除标记
        clean_text = PRODUCT_CARDS_PATTERN.sub('', clean_text)

    # 解析选项（如果没有产品卡片）
    if not ui_elements:
        clean_text, ui_elements = _parse_options(clean_text)
    else:
        # 即使有产品卡片，也移除选项标记
        clean_text = OPTIONS_PATTERN.sub('', clean_text)

    # 清理多余空行
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

    return clean_text, ui_elements


def parse_options_only(response_text: str) -> Tuple[str, Optional[UIElements]]:
    """
    仅解析[OPTIONS]标记（不解析[PRODUCT_CARDS]）

    用于非推荐Agent（health/reminder/report），这些Agent
    不会输出产品卡片，仅需要OPTIONS解析。

    Args:
        response_text: 原始AI响应文本

    Returns:
        (clean_text, ui_elements): 清理后的文本和UI元素对象（仅options类型）
    """
    clean_text, ui_elements = _parse_options(response_text)

    # 清理多余空行
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

    return clean_text, ui_elements


def _parse_options(text: str) -> Tuple[str, Optional[UIElements]]:
    """
    内部函数：解析[OPTIONS]标记

    Args:
        text: 文本内容

    Returns:
        (clean_text, ui_elements)
    """
    ui_elements = None
    clean_text = text

    options_match = OPTIONS_PATTERN.search(text)
    if options_match:
        try:
            options_json = options_match.group(1).strip()
            options_data = json.loads(options_json)
            if isinstance(options_data, list):
                option_items = []
                for opt in options_data:
                    try:
                        option_items.append(OptionItem(**opt))
                    except Exception as e:
                        logger.warning(f"[UIParser] 解析选项失败: {e}")
                        continue
                if option_items:
                    ui_elements = UIElements(
                        options=option_items,
                        ui_type="options"
                    )
        except json.JSONDecodeError as e:
            logger.warning(f"[UIParser] 选项JSON解析失败: {e}")

        # 从文本中移除标记
        clean_text = OPTIONS_PATTERN.sub('', clean_text)

    return clean_text, ui_elements
