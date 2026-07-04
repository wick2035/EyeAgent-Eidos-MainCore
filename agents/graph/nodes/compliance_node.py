"""
ComplianceAgent 节点

合规性审查：处方审查、诊断审查、病历文书审查、检查合理性审查。
仅面向医生用户开放。
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
from agents.prompts.compliance_prompts import (
    get_compliance_system_prompt,
    get_compliance_stage_prompt,
    build_compliance_context,
)
from agents.tools.compliance_tools import AGENT_5_TOOLS
from utils.llm_config import get_llm, get_streaming_llm
from utils.attachment_analyzer import inject_attachment_analysis

logger = logging.getLogger(__name__)


def _prepare_compliance(state: MedicalState):
    """构建 ComplianceAgent 的 react agent 与输入消息（sync/async 共用）"""
    role = state.get("role", "patient")
    stage = state.get("stage", "greeting")
    messages = state.get("messages", [])
    patient_id = state.get("patient_id", "")
    doctor_id = state.get("doctor_id", "")

    # 构建系统提示词
    system_prompt = get_compliance_system_prompt(role)
    stage_prompt = get_compliance_stage_prompt(stage, role)
    context = build_compliance_context(state)

    # 组合完整提示词
    full_system_prompt = f"""{system_prompt}

【当前阶段】{stage_prompt}

{context}"""

    logger.debug(
        f"[ComplianceNode] role={role}, stage={stage}, "
        f"patient_id={patient_id}, doctor_id={doctor_id}"
    )

    # 注入附件分析结果（如有）
    attachment_analysis = state.get("attachment_analysis") or ""
    messages = inject_attachment_analysis(list(messages), attachment_analysis)
    if attachment_analysis:
        logger.info(f"[ComplianceNode] 已注入附件分析，长度={len(attachment_analysis)}")

    # 根据流式标志选择 LLM
    is_streaming = state.get("is_streaming", False)
    llm = get_streaming_llm() if is_streaming else get_llm()

    # 创建 ReAct Agent
    agent = create_react_agent(
        model=llm,
        tools=AGENT_5_TOOLS,
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


def _finalize_compliance(state: MedicalState, result: Dict[str, Any], input_messages: list) -> Dict[str, Any]:
    """处理 ComplianceAgent 的执行结果（sync/async 共用）"""
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
    new_stage = _detect_compliance_stage(state, ai_response, tool_calls)
    review_completed = _check_review_completed(tool_calls, response_messages)

    # 检测审查类型
    review_type = _detect_review_type(state, ai_response)

    logger.info(
        f"[ComplianceNode] 响应生成完成, new_stage={new_stage}, "
        f"review_completed={review_completed}"
    )

    # 返回状态更新
    update = {
        "messages": [AIMessage(content=ai_response)] if ai_response else [],
        "stage": new_stage,
        "compliance_review_completed": review_completed,
        "last_response": ai_response,
    }

    if review_type:
        update["compliance_review_type"] = review_type

    return update


def _compliance_error(e: Exception) -> Dict[str, Any]:
    """ComplianceAgent 异常兜底（sync/async 共用）"""
    logger.error(f"[ComplianceNode] 处理失败: {e}", exc_info=True)
    error_response = "抱歉，我遇到了一些技术问题，请稍后再试。"
    return {
        "messages": [AIMessage(content=error_response)],
        "last_response": error_response,
        "error": str(e),
    }


def compliance_agent_node(state: MedicalState) -> Dict[str, Any]:
    """
    ComplianceAgent 节点（同步）- 非流式路径 /api/chat 使用（仅医生可用）

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    try:
        agent, input_messages = _prepare_compliance(state)
        result = agent.invoke({"messages": input_messages})
        return _finalize_compliance(state, result, input_messages)
    except Exception as e:
        return _compliance_error(e)


async def compliance_agent_node_async(state: MedicalState, config: RunnableConfig) -> Dict[str, Any]:
    """
    ComplianceAgent 节点（异步）- 流式路径 /api/chat/stream 使用（仅医生可用）

    使用 await agent.ainvoke 并显式透传 config，使外层 astream_events 能逐 token 捕获。

    Args:
        state: 当前状态
        config: LangGraph 注入的运行配置（携带 astream_events 回调）

    Returns:
        状态更新字典
    """
    try:
        agent, input_messages = _prepare_compliance(state)
        result = await agent.ainvoke({"messages": input_messages}, config=config)
        return _finalize_compliance(state, result, input_messages)
    except Exception as e:
        return _compliance_error(e)


def _detect_compliance_stage(
    state: MedicalState,
    ai_response: str,
    tool_calls: list
) -> str:
    """检测合规审查的阶段变化"""
    current_stage = state.get("stage", "greeting")

    # 检测工具调用
    tool_names = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]

    # 保存审查结果或生成PDF -> completed
    if "save_compliance_review" in tool_names or "generate_compliance_report_pdf" in tool_names:
        return "completed"

    # 联网搜索 -> reviewing
    if "web_search_medical" in tool_names:
        return "reviewing"

    # 获取患者数据 -> data_loading / reviewing
    data_tools = {
        "get_patient_prescription_detail",
        "get_patient_prescription_limit",
        "get_patient_scan_data",
    }
    if data_tools & set(tool_names):
        # 如果已经在 reviewing 阶段，保持
        if current_stage in ("reviewing", "result"):
            return current_stage
        return "data_loading"

    # 检查响应内容判断阶段
    response_lower = ai_response.lower() if ai_response else ""

    # 审查报告输出标记
    result_keywords = ["审查概要", "审查总结", "合规评级", "项合规", "项不合规", "项建议改进"]
    if any(kw in ai_response for kw in result_keywords):
        return "result"

    # 阶段流转
    if current_stage == "greeting":
        return "data_loading"

    return current_stage


def _check_review_completed(tool_calls: list, messages: list) -> bool:
    """检查审查是否完成（保存或生成PDF）"""
    completion_tools = {"save_compliance_review", "generate_compliance_report_pdf"}

    for tc in tool_calls:
        if isinstance(tc, dict) and tc.get("name") in completion_tools:
            return True

    for msg in messages:
        if hasattr(msg, "name") and msg.name in completion_tools:
            content = getattr(msg, "content", "")
            if "success" in content.lower() or "成功" in content:
                return True

    return False


def _detect_review_type(state: MedicalState, ai_response: str) -> str:
    """从对话内容检测审查类型"""
    # 如果已经设置了类型，保持
    existing_type = state.get("compliance_review_type")
    if existing_type:
        return existing_type

    if not ai_response:
        return ""

    # 关键词检测审查类型
    if "处方" in ai_response and ("审查" in ai_response or "合规" in ai_response):
        return "prescription"
    if "诊断" in ai_response and ("审查" in ai_response or "合规" in ai_response):
        return "diagnosis"
    if "病历" in ai_response and ("审查" in ai_response or "合规" in ai_response):
        return "record"
    if "检查" in ai_response and ("合理" in ai_response or "审查" in ai_response):
        return "examination"
    if "全面" in ai_response and "审查" in ai_response:
        return "full"

    return ""
