"""
ReportAgent 节点

报告查看、处方查询、PDF 生成功能。
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
from agents.prompts.report_prompts import (
    get_report_system_prompt,
    get_report_stage_prompt,
    build_report_context,
)
from agents.tools.agent_tools import AGENT_2_TOOLS
from utils.llm_config import get_llm, get_streaming_llm

logger = logging.getLogger(__name__)


def report_agent_node(state: MedicalState) -> Dict[str, Any]:
    """
    ReportAgent 节点 - 处理报告查看、处方查询、PDF生成

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
    system_prompt = get_report_system_prompt(role)
    stage_prompt = get_report_stage_prompt(stage, role)
    context = build_report_context(state)

    # 组合完整提示词
    full_system_prompt = f"""{system_prompt}

【当前阶段】{stage_prompt}

{context}"""

    logger.debug(f"[ReportNode] role={role}, stage={stage}, patient_id={patient_id}")

    try:
        # 根据流式标志选择 LLM
        is_streaming = state.get("is_streaming", False)
        llm = get_streaming_llm() if is_streaming else get_llm()

        # 创建 ReAct Agent
        agent = create_react_agent(
            model=llm,
            tools=AGENT_2_TOOLS,
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
        new_stage = _detect_report_stage(state, ai_response, tool_calls)
        pdf_generated = _check_pdf_generated(tool_calls, response_messages)

        logger.info(f"[ReportNode] 响应生成完成, new_stage={new_stage}, pdf={pdf_generated}")

        # 返回状态更新
        return {
            "messages": [AIMessage(content=ai_response)] if ai_response else [],
            "stage": new_stage,
            "report_generated": pdf_generated,
            "last_response": ai_response,
        }

    except Exception as e:
        logger.error(f"[ReportNode] 处理失败: {e}", exc_info=True)
        error_response = "抱歉，我遇到了一些技术问题，请稍后再试。"
        return {
            "messages": [AIMessage(content=error_response)],
            "last_response": error_response,
            "error": str(e),
        }


def _detect_report_stage(
    state: MedicalState,
    ai_response: str,
    tool_calls: list
) -> str:
    """检测报告相关的阶段变化"""
    current_stage = state.get("stage", "greeting")

    # 检测工具调用
    tool_names = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]

    # PDF 生成完成
    if "generate_medical_record_pdf" in tool_names or "generate_prescription_pdf" in tool_names:
        return "completed"

    # 查看处方详情
    if "get_patient_prescription_detail" in tool_names:
        return "analyze_history"

    # 查看处方列表
    if "get_patient_prescription_limit" in tool_names:
        return "generate_report"

    # 阶段流转
    if current_stage == "greeting":
        return "select_action"

    return current_stage


def _check_pdf_generated(tool_calls: list, messages: list) -> bool:
    """检查是否生成了 PDF"""
    pdf_tools = ["generate_medical_record_pdf", "generate_prescription_pdf"]

    for tc in tool_calls:
        if isinstance(tc, dict) and tc.get("name") in pdf_tools:
            return True

    for msg in messages:
        if hasattr(msg, "name") and msg.name in pdf_tools:
            content = getattr(msg, "content", "")
            if "成功" in content or "http" in content.lower():
                return True

    return False
