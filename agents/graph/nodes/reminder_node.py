"""
ReminderAgent 节点

提醒管理、提醒配置、提醒创建功能。
"""
import logging
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

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


def _prepare_reminder(state: MedicalState):
    """构建 ReminderAgent 的 react agent 与输入消息（sync/async 共用）"""
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

    return agent, input_messages


def _finalize_reminder(state: MedicalState, result: Dict[str, Any], input_messages: list) -> Dict[str, Any]:
    """处理 ReminderAgent 的执行结果（sync/async 共用）"""
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

    # 若 LLM 未生成文本回复，从工具调用结果中构造准确的成功/失败消息
    if not ai_response:
        from langchain_core.messages import ToolMessage
        import json
        _CREATE_TOOLS = {"create_reminder", "create_medical_reminder"}
        _CONFIG_TOOLS = {"init_patient_reminder_config", "modify_patient_reminder_config"}
        _VIEW_TOOLS = {"get_patient_reminder", "get_patient_reminder_config"}
        for msg in response_messages:
            if isinstance(msg, ToolMessage):
                try:
                    data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                except Exception:
                    data = {}
                success = (data.get("code") == 200 or "成功" in str(msg.content))
                if msg.name in _CREATE_TOOLS:
                    ai_response = "好的，提醒已为您创建成功！" if success else f"提醒创建失败，请稍后再试。({data.get('msg', '')})"
                    break
                elif msg.name in _CONFIG_TOOLS:
                    ai_response = "提醒设置已更新。" if success else f"设置更新失败。({data.get('msg', '')})"
                    break
                elif msg.name in _VIEW_TOOLS:
                    ai_response = msg.content if isinstance(msg.content, str) else str(msg.content)
                    break

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


def _reminder_error(e: Exception) -> Dict[str, Any]:
    """ReminderAgent 异常兜底（sync/async 共用）"""
    logger.error(f"[ReminderNode] 处理失败: {e}", exc_info=True)
    error_response = "抱歉，我遇到了一些技术问题，请稍后再试。"
    return {
        "messages": [AIMessage(content=error_response)],
        "last_response": error_response,
        "error": str(e),
    }


def reminder_agent_node(state: MedicalState) -> Dict[str, Any]:
    """
    ReminderAgent 节点（同步）- 非流式路径 /api/chat 使用

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    try:
        agent, input_messages = _prepare_reminder(state)
        result = agent.invoke({"messages": input_messages})
        return _finalize_reminder(state, result, input_messages)
    except Exception as e:
        return _reminder_error(e)


async def reminder_agent_node_async(state: MedicalState, config: RunnableConfig) -> Dict[str, Any]:
    """
    ReminderAgent 节点（异步）- 流式路径 /api/chat/stream 使用

    使用 await agent.ainvoke 并显式透传 config，使外层 astream_events 能逐 token 捕获。

    Args:
        state: 当前状态
        config: LangGraph 注入的运行配置（携带 astream_events 回调）

    Returns:
        状态更新字典
    """
    try:
        agent, input_messages = _prepare_reminder(state)
        result = await agent.ainvoke({"messages": input_messages}, config=config)
        return _finalize_reminder(state, result, input_messages)
    except Exception as e:
        return _reminder_error(e)


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
    if "create_reminder" in tool_names or "create_medical_reminder" in tool_names:
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
        if isinstance(tc, dict) and tc.get("name") in ("create_reminder", "create_medical_reminder"):
            return True

    for msg in messages:
        if hasattr(msg, "name") and msg.name in ("create_reminder", "create_medical_reminder"):
            content = getattr(msg, "content", "")
            if "成功" in content or '"id"' in content:
                return True

    return False
