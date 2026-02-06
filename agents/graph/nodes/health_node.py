"""
HealthAgent 节点

健康咨询、眼科分诊、医生预约功能。
"""
import logging
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# 兼容不同版本的 langgraph
try:
    from langgraph.prebuilt import create_react_agent
except ImportError:
    # 旧版本可能在不同位置
    from langgraph.prebuilt.chat_agent_executor import create_react_agent

from agents.graph.state import MedicalState
from agents.prompts.health_prompts import (
    get_health_system_prompt,
    get_health_stage_prompt,
    build_health_context,
)
from agents.tools.agent_tools import AGENT_1_TOOLS
from utils.llm_config import get_llm, get_streaming_llm

logger = logging.getLogger(__name__)


def health_agent_node(state: MedicalState) -> Dict[str, Any]:
    """
    HealthAgent 节点 - 处理健康咨询、眼科分诊、预约

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    role = state.get("role", "patient")
    stage = state.get("stage", "greeting")
    messages = state.get("messages", [])
    patient_id = state.get("patient_id", "")

    # 构建系统提示词
    system_prompt = get_health_system_prompt(role)
    stage_prompt = get_health_stage_prompt(stage, role)
    context = build_health_context(state)

    # 组合完整提示词
    full_system_prompt = f"""{system_prompt}

【当前阶段】{stage_prompt}

{context}"""

    logger.debug(f"[HealthNode] role={role}, stage={stage}, patient_id={patient_id}")

    try:
        # 根据流式标志选择 LLM
        is_streaming = state.get("is_streaming", False)
        llm = get_streaming_llm() if is_streaming else get_llm()

        # 创建 ReAct Agent
        agent = create_react_agent(
            model=llm,
            tools=AGENT_1_TOOLS,
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
        new_stage = _detect_stage_transition(state, ai_response, tool_calls)
        appointment_confirmed = _check_appointment_confirmed(tool_calls, response_messages)

        logger.info(f"[HealthNode] 响应生成完成, new_stage={new_stage}, appointment={appointment_confirmed}")

        # 返回状态更新
        return {
            "messages": [AIMessage(content=ai_response)] if ai_response else [],
            "stage": new_stage,
            "appointment_confirmed": appointment_confirmed,
            "last_response": ai_response,
        }

    except Exception as e:
        logger.error(f"[HealthNode] 处理失败: {e}", exc_info=True)
        error_response = "抱歉，我遇到了一些技术问题，请稍后再试。"
        return {
            "messages": [AIMessage(content=error_response)],
            "last_response": error_response,
            "error": str(e),
        }


def _detect_stage_transition(
    state: MedicalState,
    ai_response: str,
    tool_calls: list
) -> str:
    """
    检测并返回新的对话阶段

    Args:
        state: 当前状态
        ai_response: AI 响应内容
        tool_calls: 工具调用列表

    Returns:
        新的阶段名称
    """
    current_stage = state.get("stage", "greeting")
    needs_appointment = state.get("needs_appointment", False)
    response_lower = ai_response.lower()

    # 检测工具调用
    tool_names = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]

    # 预约完成检测
    if "reserve_doctor" in tool_names:
        return "completed"

    # 查询医生时间 -> 预约阶段
    if "get_doctor_free_time" in tool_names:
        return "appointment_booking"

    # 关键词检测阶段转换
    stage_keywords = {
        "health_consultation": ["症状", "不适", "问题", "情况"],
        "symptom_assessment": ["评估", "严重", "建议", "需要"],
        "appointment_inquiry": ["预约", "挂号", "就诊"],
        "ophthalmology_triage": ["眼", "视力", "检查"],
        "appointment_booking": ["时间", "日期", "选择"],
    }

    # 预约意图检测
    if any(kw in response_lower for kw in ["预约", "挂号", "就诊"]):
        if current_stage in ["greeting", "health_consultation", "symptom_assessment"]:
            return "appointment_inquiry"

    # 阶段流转
    stage_flow = {
        "greeting": "health_consultation",
        "health_consultation": "symptom_assessment",
        "symptom_assessment": "appointment_inquiry",
        "appointment_inquiry": "patient_info_collection",
        "patient_info_collection": "ophthalmology_triage",
        "ophthalmology_triage": "medical_history",
        "medical_history": "appointment_booking",
        "appointment_booking": "completed",
    }

    # 根据对话轮次自动流转（简化逻辑）
    message_count = len(state.get("messages", []))
    if message_count > 2 and current_stage == "greeting":
        return "health_consultation"

    return current_stage


def _check_appointment_confirmed(tool_calls: list, messages: list) -> bool:
    """
    检查预约是否已确认

    Args:
        tool_calls: 工具调用列表
        messages: 响应消息列表

    Returns:
        是否已确认预约
    """
    # 检查是否调用了 reserve_doctor
    for tc in tool_calls:
        if isinstance(tc, dict) and tc.get("name") == "reserve_doctor":
            return True

    # 检查消息中的工具响应
    for msg in messages:
        if hasattr(msg, "name") and msg.name == "reserve_doctor":
            # 检查是否成功
            content = getattr(msg, "content", "")
            if "预约成功" in content or '"id"' in content:
                return True

    return False
