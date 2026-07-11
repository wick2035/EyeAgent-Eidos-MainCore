"""
ResearchAgent 节点

科研助手、文献搜索、统计分析功能。
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
from agents.prompts.research_prompts import (
    PREPARED_RESEARCH_DOCUMENT_SECURITY_DIRECTIVE,
    get_research_system_prompt,
    get_research_stage_prompt,
    build_research_context,
    detect_research_intent,
)
from agents.tools.research_tools import RESEARCH_AGENT_TOOLS
from agents.graph.attachment_citations import build_attachment_citation_tool
from utils.transient_attachment_context import (
    get_research_document_context,
    inject_untrusted_research_documents,
)
from utils.llm_config import get_llm, get_streaming_llm

logger = logging.getLogger(__name__)

_PATIENT_BOUND_TOOL_NAMES = frozenset(
    {
        "get_patient_prescription",
        "get_doctor_free_time",
        "reserve_doctor",
        "get_patient_prescription_limit",
        "get_patient_prescription_detail",
        "get_patient_scan_data",
        "get_patient_reminder",
        "get_patient_reminder_config",
        "init_patient_reminder_config",
        "modify_patient_reminder_config",
        "create_reminder",
    }
)


class PreparedResearchAgentError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("RESEARCH_AGENT_FAILED")
        self.error_code = "RESEARCH_AGENT_FAILED"


def _prepare_research(state: MedicalState, config: RunnableConfig | None = None):
    """构建 ResearchAgent 的 react agent 与输入消息（sync/async 共用）"""
    role = state.get("role", "doctor")  # 科研模式通常是医生
    stage = state.get("stage", "greeting")
    messages = state.get("messages", [])
    doctor_id = state.get("doctor_id", "")

    # 检查权限
    enable_institution_data = state.get("enable_institution_data", False)
    enable_web_search = state.get("enable_web_search", False)

    # 构建系统提示词
    system_prompt = get_research_system_prompt(role)
    stage_prompt = get_research_stage_prompt(stage, role)
    context = build_research_context(state)

    # 添加权限限制提示
    permission_note = _build_permission_note(enable_institution_data, enable_web_search)
    document_security_note = (
        PREPARED_RESEARCH_DOCUMENT_SECURITY_DIRECTIVE
        if state.get("platform_prepared")
        else ""
    )

    # 组合完整提示词
    full_system_prompt = f"""{system_prompt}

{document_security_note}

【当前阶段】{stage_prompt}

{context}

{permission_note}"""

    logger.debug(f"[ResearchNode] role={role}, stage={stage}, doctor_id={doctor_id}")

    # 根据流式标志选择 LLM
    is_streaming = state.get("is_streaming", False)
    llm = get_streaming_llm() if is_streaming else get_llm()

    # 根据权限过滤工具
    available_tools = _filter_tools_by_permission(
        RESEARCH_AGENT_TOOLS,
        enable_institution_data,
        enable_web_search,
        patient_id=state.get("patient_id"),
    )
    research_document_context = None
    if state.get("platform_prepared"):
        research_document_context = get_research_document_context()
        candidates = research_document_context.selection.citation_candidates
        if candidates:
            available_tools = [
                *available_tools,
                build_attachment_citation_tool(candidates),
            ]

    # 创建 ReAct Agent
    agent = create_react_agent(
        model=llm,
        tools=available_tools,
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

    if state.get("platform_prepared"):
        input_messages = inject_untrusted_research_documents(
            input_messages,
            research_document_context,
        )

    return agent, input_messages


def _finalize_research(state: MedicalState, result: Dict[str, Any], input_messages: list) -> Dict[str, Any]:
    """处理 ResearchAgent 的执行结果（sync/async 共用）"""
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

    # 检测新阶段
    last_user_message = _get_last_user_message(state.get("messages", []))
    new_stage = _detect_research_stage(state, ai_response, tool_calls, last_user_message)

    logger.info(f"[ResearchNode] 响应生成完成, new_stage={new_stage}")

    # 返回状态更新
    return {
        "messages": [AIMessage(content=ai_response)] if ai_response else [],
        "stage": new_stage,
        "last_response": ai_response,
    }


def _research_error(e: Exception) -> Dict[str, Any]:
    """ResearchAgent 异常兜底（sync/async 共用）"""
    logger.error(
        "[ResearchNode] 处理失败, error_type=%s",
        type(e).__name__,
    )
    error_response = "抱歉，我遇到了一些技术问题，请稍后再试。"
    return {
        "messages": [AIMessage(content=error_response)],
        "last_response": error_response,
        "error": "RESEARCH_AGENT_FAILED",
    }


def research_agent_node(state: MedicalState) -> Dict[str, Any]:
    """
    ResearchAgent 节点（同步）- 非流式路径 /api/chat 使用

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    try:
        agent, input_messages = _prepare_research(state)
        result = agent.invoke({"messages": input_messages})
        return _finalize_research(state, result, input_messages)
    except Exception as e:
        return _research_error(e)


async def research_agent_node_async(state: MedicalState, config: RunnableConfig) -> Dict[str, Any]:
    """
    ResearchAgent 节点（异步）- 流式路径 /api/chat/stream 使用

    使用 await agent.ainvoke 并显式透传 config，使外层 astream_events 能逐 token 捕获。

    Args:
        state: 当前状态
        config: LangGraph 注入的运行配置（携带 astream_events 回调）

    Returns:
        状态更新字典
    """
    try:
        agent, input_messages = _prepare_research(state, config)
        result = await agent.ainvoke({"messages": input_messages}, config=config)
        return _finalize_research(state, result, input_messages)
    except Exception as e:
        if state.get("platform_prepared"):
            logger.error(
                "[ResearchNode] prepared 处理失败, error_type=%s",
                type(e).__name__,
            )
            raise PreparedResearchAgentError() from None
        return _research_error(e)


def _build_permission_note(enable_institution_data: bool, enable_web_search: bool) -> str:
    """构建权限说明"""
    notes = ["【权限状态提醒】"]

    if not enable_institution_data:
        notes.append("- 机构数据库访问: 未开启 (无法使用 get_institution_research_data)")
    else:
        notes.append("- 机构数据库访问: 已开启")

    if not enable_web_search:
        notes.append("- 网页搜索: 未开启 (无法使用 web_search_medical)")
    else:
        notes.append("- 网页搜索: 已开启")

    return "\n".join(notes)


def _filter_tools_by_permission(
    tools: list,
    enable_institution_data: bool,
    enable_web_search: bool,
    patient_id: str | None = None,
) -> list:
    """
    根据权限过滤工具

    Args:
        tools: 完整工具列表
        enable_institution_data: 是否启用机构数据
        enable_web_search: 是否启用网页搜索

    Returns:
        过滤后的工具列表
    """
    filtered = []

    for tool in tools:
        tool_name = getattr(tool, "name", "")

        if patient_id is None and tool_name in _PATIENT_BOUND_TOOL_NAMES:
            continue

        # 过滤机构数据工具
        if tool_name == "get_institution_research_data" and not enable_institution_data:
            continue

        # 过滤网页搜索工具
        if tool_name == "web_search_medical" and not enable_web_search:
            continue

        filtered.append(tool)

    return filtered


def _get_last_user_message(messages: list) -> str:
    """获取最后一条用户消息"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
        elif isinstance(msg, dict) and msg.get("type") == "human":
            return msg.get("content", "")
    return ""


def _detect_research_stage(
    state: MedicalState,
    ai_response: str,
    tool_calls: list,
    user_message: str,
) -> str:
    """检测科研相关的阶段变化"""
    current_stage = state.get("stage", "greeting")

    # 使用提示词模块的意图检测
    if user_message:
        intent = detect_research_intent(user_message)
        if intent != "unknown":
            # 意图映射到阶段
            intent_to_stage = {
                "data_query": "data_query",
                "web_search": "web_search",
                "statistical_analysis": "statistical_analysis",
                "research_design": "research_design",
                "paper_writing": "paper_writing",
                "exit": "completed",
            }
            if intent in intent_to_stage:
                return intent_to_stage[intent]

    # 检测工具调用
    tool_names = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]

    # 根据工具推断阶段
    if "get_institution_research_data" in tool_names:
        return "data_query"
    if "web_search_medical" in tool_names:
        return "web_search"
    if "statistical_analysis" in tool_names:
        return "statistical_analysis"
    if "design_research_protocol" in tool_names:
        return "research_design"
    if "assist_paper_writing" in tool_names:
        return "paper_writing"

    # 阶段流转
    if current_stage == "greeting":
        return "research_init"

    return current_stage
