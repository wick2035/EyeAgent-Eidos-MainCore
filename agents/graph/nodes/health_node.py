"""
HealthAgent 节点

健康咨询、眼科分诊、医生预约功能。
"""
import re
import logging
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

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
from utils.attachment_analyzer import inject_attachment_analysis

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

    logger.info(f"[HealthNode] === 开始处理 === role={role}, stage={stage}, patient_id={patient_id}")

    try:
        # 注入附件分析结果（如有）
        attachment_analysis = state.get("attachment_analysis") or ""
        messages = inject_attachment_analysis(list(messages), attachment_analysis)
        if attachment_analysis:
            logger.info(f"[HealthNode] 已注入附件分析，长度={len(attachment_analysis)}")

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

        # 添加对话历史（包含 ToolMessage 以保留工具调用结果如 doctorId）
        for msg in messages:
            if isinstance(msg, (HumanMessage, AIMessage, SystemMessage, ToolMessage)):
                input_messages.append(msg)
            elif isinstance(msg, dict):
                msg_type = msg.get("type", "")
                content = msg.get("content", "")
                if msg_type == "human":
                    input_messages.append(HumanMessage(content=content))
                elif msg_type == "ai":
                    input_messages.append(AIMessage(content=content))

        logger.info(f"[HealthNode] 输入消息数: {len(input_messages)} (含系统提示词)")

        # 调用 Agent
        result = agent.invoke({"messages": input_messages})

        # 提取响应并记录详细日志
        response_messages = result.get("messages", [])
        ai_response = ""
        tool_calls = []

        logger.info(f"[HealthNode] Agent 返回消息数: {len(response_messages)}")
        for i, msg in enumerate(response_messages):
            msg_type = type(msg).__name__
            msg_name = getattr(msg, "name", None)
            msg_content = getattr(msg, "content", "")
            msg_tool_calls = getattr(msg, "tool_calls", [])
            content_preview = (msg_content[:200] + "...") if len(msg_content) > 200 else msg_content
            logger.info(
                f"[HealthNode]   消息[{i}] type={msg_type}, name={msg_name}, "
                f"content_len={len(msg_content)}, tool_calls={len(msg_tool_calls)}, "
                f"preview={content_preview}"
            )
            if msg_tool_calls:
                for tc in msg_tool_calls:
                    tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                    tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    logger.info(f"[HealthNode]     tool_call: {tc_name}({tc_args})")

            if isinstance(msg, AIMessage):
                if msg.content:
                    ai_response = msg.content
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_calls.extend(msg.tool_calls)

        tool_names = [tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "") for tc in tool_calls]
        logger.info(f"[HealthNode] 最终 ai_response 长度={len(ai_response)}, tool_calls={tool_names}")

        # 防护：拦截预约成功的提前声明
        ai_response = _sanitize_premature_confirmation(ai_response, tool_calls, response_messages)

        # 检测状态变更
        new_stage = _detect_stage_transition(state, ai_response, tool_calls, response_messages)
        appointment_confirmed = _check_appointment_confirmed(tool_calls, response_messages)

        # 提取本轮新增的消息（跳过输入消息），保留 ToolMessage 以便下轮使用
        new_messages = response_messages[len(input_messages):]
        # 如果 ai_response 被 sanitize 修改过，替换最后一条 AIMessage 的内容
        if new_messages:
            for i in range(len(new_messages) - 1, -1, -1):
                if isinstance(new_messages[i], AIMessage) and new_messages[i].content:
                    if new_messages[i].content != ai_response:
                        new_messages[i] = AIMessage(content=ai_response)
                    break

        logger.info(
            f"[HealthNode] === 处理完成 === new_stage={new_stage}, "
            f"appointment_confirmed={appointment_confirmed}, "
            f"new_messages_count={len(new_messages)}, "
            f"response_preview={ai_response[:150]}"
        )

        # 返回状态更新（包含所有新消息：AIMessage + ToolMessage）
        return {
            "messages": new_messages if new_messages else ([AIMessage(content=ai_response)] if ai_response else []),
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
    tool_calls: list,
    response_messages: list = None
) -> str:
    """
    检测并返回新的对话阶段

    Args:
        state: 当前状态
        ai_response: AI 响应内容
        tool_calls: 工具调用列表
        response_messages: 完整响应消息列表（用于验证工具调用结果）

    Returns:
        新的阶段名称
    """
    current_stage = state.get("stage", "greeting")
    needs_appointment = state.get("needs_appointment", False)
    response_lower = ai_response.lower()

    # 检测工具调用
    tool_names = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]

    # 预约完成检测：必须验证 reserve_doctor 实际成功
    if "reserve_doctor" in tool_names:
        reserve_succeeded = False
        if response_messages:
            for msg in response_messages:
                if hasattr(msg, "name") and msg.name == "reserve_doctor":
                    content = getattr(msg, "content", "")
                    if ('"id"' in content or "预约成功" in content) and "失败" not in content:
                        reserve_succeeded = True
                        break
        if reserve_succeeded:
            logger.info("[HealthNode] reserve_doctor 调用成功，进入 completed 阶段")
            return "completed"
        else:
            logger.warning("[HealthNode] reserve_doctor 被调用但未成功，保持 appointment_booking 阶段")
            return "appointment_booking"

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
    检查预约是否已确认（必须验证工具返回成功结果）

    Args:
        tool_calls: 工具调用列表
        messages: 响应消息列表

    Returns:
        是否已确认预约
    """
    # 只通过 ToolMessage 的实际返回内容来判断是否成功
    for msg in messages:
        if hasattr(msg, "name") and msg.name == "reserve_doctor":
            content = getattr(msg, "content", "")
            # 必须包含成功标志且不包含失败标志
            if ('"id"' in content or "预约成功" in content) and "失败" not in content:
                return True

    return False


def _sanitize_premature_confirmation(
    ai_response: str,
    tool_calls: list,
    response_messages: list
) -> str:
    """
    防止 LLM 在 reserve_doctor 实际成功前声明预约成功

    Args:
        ai_response: AI 响应文本
        tool_calls: 工具调用列表
        response_messages: 完整响应消息列表

    Returns:
        清理后的响应文本
    """
    if not ai_response:
        return ai_response

    # 检测是否有预约成功声明
    success_patterns = [
        r'已(?:成功)?(?:为您|帮您)?预约',
        r'预约成功',
        r'已(?:成功)?(?:完成|确认)预约',
        r'成功(?:预约|挂号)',
    ]

    has_success_claim = any(re.search(p, ai_response) for p in success_patterns)
    if not has_success_claim:
        return ai_response

    # 检查 reserve_doctor 是否实际调用且成功返回
    reserve_succeeded = False
    for msg in response_messages:
        if hasattr(msg, "name") and msg.name == "reserve_doctor":
            content = getattr(msg, "content", "")
            if ('"id"' in content or "预约成功" in content) and "失败" not in content:
                reserve_succeeded = True
                break

    if not reserve_succeeded:
        # 替换提前声明的成功消息
        for pattern in success_patterns:
            ai_response = re.sub(pattern, "预约处理遇到问题", ai_response)
        ai_response += "\n\n抱歉，预约未能成功完成，请您再次确认预约信息，我将重新为您预约。"
        logger.warning("[HealthNode] 拦截了预约成功的提前声明，reserve_doctor 未成功返回")

    return ai_response
