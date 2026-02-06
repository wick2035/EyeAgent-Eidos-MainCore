"""
ReminderAgent 节点

提醒管理、提醒配置、提醒创建功能。
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
from agents.prompts.reminder_prompts import (
    get_reminder_system_prompt,
    get_reminder_stage_prompt,
    build_reminder_context,
)
from agents.tools.agent_tools import AGENT_3_TOOLS
from utils.llm_config import get_llm, get_streaming_llm

logger = logging.getLogger(__name__)


def reminder_agent_node(state: MedicalState) -> Dict[str, Any]:
    """
    ReminderAgent 节点 - 处理提醒管理、创建、配置

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
    system_prompt = get_reminder_system_prompt(role)
    stage_prompt = get_reminder_stage_prompt(stage, role)
    context = build_reminder_context(state)

    # 组合完整提示词
    full_system_prompt = f"""{system_prompt}

【当前阶段】{stage_prompt}

{context}"""

    logger.debug(f"[ReminderNode] role={role}, stage={stage}, patient_id={patient_id}")

    try:
        # 根据流式标志选择 LLM
        is_streaming = state.get("is_streaming", False)
        llm = get_streaming_llm() if is_streaming else get_llm()

        # 创建 ReAct Agent
        agent = create_react_agent(
            model=llm,
            tools=AGENT_3_TOOLS,
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
        new_stage = _detect_reminder_stage(state, ai_response, tool_calls)
        reminder_created = _check_reminder_created(tool_calls, response_messages)

        logger.info(f"[ReminderNode] 响应生成完成, new_stage={new_stage}, created={reminder_created}")

        # 返回状态更新
        return {
            "messages": [AIMessage(content=ai_response)] if ai_response else [],
            "stage": new_stage,
            "reminder_created": reminder_created,
            "last_response": ai_response,
        }

    except Exception as e:
        logger.error(f"[ReminderNode] 处理失败: {e}", exc_info=True)
        error_response = "抱歉，我遇到了一些技术问题，请稍后再试。"
        return {
            "messages": [AIMessage(content=error_response)],
            "last_response": error_response,
            "error": str(e),
        }


def _detect_reminder_stage(
    state: MedicalState,
    ai_response: str,
    tool_calls: list
) -> str:
    """检测提醒相关的阶段变化"""
    current_stage = state.get("stage", "greeting")

    # 检测工具调用
    tool_names = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]

    # 创建提醒完成
    if "create_reminder" in tool_names:
        return "completed"

    # 配置更新
    if "init_patient_reminder_config" in tool_names or "modify_patient_reminder_config" in tool_names:
        return "config_settings"

    # 查看提醒
    if "get_patient_reminder" in tool_names:
        return "view_reminders"

    # 查看配置
    if "get_patient_reminder_config" in tool_names:
        return "config_settings"

    # 阶段流转
    if current_stage == "greeting":
        return "select_action"

    return current_stage


def _check_reminder_created(tool_calls: list, messages: list) -> bool:
    """检查是否创建了提醒"""
    for tc in tool_calls:
        if isinstance(tc, dict) and tc.get("name") == "create_reminder":
            return True

    for msg in messages:
        if hasattr(msg, "name") and msg.name == "create_reminder":
            content = getattr(msg, "content", "")
            if "成功" in content or '"id"' in content:
                return True

    return False
