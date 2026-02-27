"""
RecommendationAgent 节点

医药产品推荐：根据诊断/症状推荐药品、器械。
支持医生端（处方推荐）和患者端（OTC购买推荐）。
"""
import logging
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# 兼容不同版本的 langgraph
try:
    from langgraph.prebuilt import create_react_agent
except ImportError:
    from langgraph.prebuilt.chat_agent_executor import create_react_agent

from agents.graph.state import MedicalState
from agents.prompts.recommendation_prompts import (
    get_recommendation_system_prompt,
    get_recommendation_stage_prompt,
    build_recommendation_context,
)
from agents.tools.recommendation_tools import AGENT_6_TOOLS
from utils.llm_config import get_llm, get_streaming_llm

logger = logging.getLogger(__name__)


def recommendation_agent_node(state: MedicalState) -> Dict[str, Any]:
    """
    RecommendationAgent 节点 - 处理医药产品推荐

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    role = state.get("role", "patient")
    stage = state.get("stage", "greeting")
    messages = state.get("messages", [])
    patient_id = state.get("patient_id", "")
    doctor_id = state.get("doctor_id", "")

    # 构建系统提示词
    system_prompt = get_recommendation_system_prompt(role)
    stage_prompt = get_recommendation_stage_prompt(stage, role)
    context = build_recommendation_context(state)

    # 组合完整提示词
    full_system_prompt = f"""{system_prompt}

【当前阶段】{stage_prompt}

{context}"""

    logger.debug(
        f"[RecommendationNode] role={role}, stage={stage}, "
        f"patient_id={patient_id}, doctor_id={doctor_id}"
    )

    try:
        # 根据流式标志选择 LLM
        is_streaming = state.get("is_streaming", False)
        llm = get_streaming_llm() if is_streaming else get_llm()

        # 创建 ReAct Agent
        agent = create_react_agent(
            model=llm,
            tools=AGENT_6_TOOLS,
        )

        # 准备输入消息
        input_messages = [SystemMessage(content=full_system_prompt)]

        # 添加对话历史
        for msg in messages:
            if isinstance(msg, (HumanMessage, AIMessage, SystemMessage)):
                input_messages.append(msg)
            elif isinstance(msg, dict):
                msg_type = msg.get("type", "")
                content = msg.get("content", "")
                if msg_type == "human":
                    input_messages.append(HumanMessage(content=content))
                elif msg_type == "ai":
                    input_messages.append(AIMessage(content=content))

        # 调用 Agent
        result = agent.invoke({"messages": input_messages})

        # 提取响应
        response_messages = result.get("messages", [])
        ai_response = ""
        tool_calls = []

        for msg in response_messages:
            if isinstance(msg, AIMessage):
                if msg.content:
                    ai_response = msg.content
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_calls.extend(msg.tool_calls)

        # 检测状态变更
        new_stage = _detect_recommendation_stage(state, ai_response, tool_calls)
        recommendation_completed = _check_recommendation_completed(tool_calls, response_messages)

        logger.info(
            f"[RecommendationNode] 响应生成完成, new_stage={new_stage}, "
            f"recommendation_completed={recommendation_completed}"
        )

        # 返回状态更新
        update = {
            "messages": [AIMessage(content=ai_response)] if ai_response else [],
            "stage": new_stage,
            "recommendation_completed": recommendation_completed,
            "last_response": ai_response,
            "recommendation_mode": role,
        }

        return update

    except Exception as e:
        logger.error(f"[RecommendationNode] 处理失败: {e}", exc_info=True)
        error_response = "抱歉，我遇到了一些技术问题，请稍后再试。"
        return {
            "messages": [AIMessage(content=error_response)],
            "last_response": error_response,
            "error": str(e),
        }


def _detect_recommendation_stage(
    state: MedicalState,
    ai_response: str,
    tool_calls: list
) -> str:
    """检测推荐对话的阶段变化"""
    current_stage = state.get("stage", "greeting")
    role = state.get("role", "patient")

    # 检测工具调用
    tool_names = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]

    # 开具处方或加入购物车 -> 对应确认阶段
    if "create_product_prescription" in tool_names:
        return "completed"
    if "add_to_cart" in tool_names:
        return "purchase_confirm"

    # 产品搜索/推荐工具 -> recommendation 阶段
    product_tools = {"search_products", "get_recommended_products", "get_product_detail"}
    if product_tools & set(tool_names):
        # 检查响应是否包含产品卡片标记
        if "[PRODUCT_CARDS]" in ai_response:
            return "recommendation"
        return "product_search"

    # 诊断数据获取工具 -> diagnosis_review
    diagnosis_tools = {"get_patient_diagnosis_summary", "get_patient_prescription_detail"}
    if diagnosis_tools & set(tool_names):
        if current_stage in ("product_search", "recommendation"):
            return current_stage
        return "diagnosis_review"

    # 根据响应内容判断阶段
    if ai_response:
        # 包含产品卡片 -> recommendation
        if "[PRODUCT_CARDS]" in ai_response:
            return "recommendation"

        # 包含选项 -> 根据角色判断
        if "[OPTIONS]" in ai_response:
            if role == "patient":
                if current_stage == "greeting":
                    return "need_inquiry"
                elif current_stage in ("need_inquiry", "symptom_collect"):
                    return "symptom_collect"
            else:
                if current_stage == "greeting":
                    return "diagnosis_review"

    # 阶段流转：greeting -> 下一个阶段
    if current_stage == "greeting":
        if role == "doctor":
            return "diagnosis_review"
        else:
            return "need_inquiry"

    return current_stage


def _check_recommendation_completed(tool_calls: list, messages: list) -> bool:
    """检查推荐流程是否完成"""
    completion_tools = {"create_product_prescription", "add_to_cart"}

    for tc in tool_calls:
        if isinstance(tc, dict) and tc.get("name") in completion_tools:
            return True

    for msg in messages:
        if hasattr(msg, "name") and msg.name in completion_tools:
            content = getattr(msg, "content", "")
            if "success" in content.lower() or "成功" in content:
                return True

    return False
