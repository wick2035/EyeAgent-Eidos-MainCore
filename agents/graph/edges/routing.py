"""
路由边函数

定义 LangGraph 图的条件边路由逻辑。
"""
import logging
from typing import Literal

from agents.graph.state import MedicalState

logger = logging.getLogger(__name__)

# 定义 Agent 类型
AgentType = Literal["health", "report", "reminder", "research", "compliance"]

# 定义节点目标
NodeTarget = Literal["health", "report", "reminder", "research", "compliance", "response", "__end__"]


def route_by_agent_type(state: MedicalState) -> AgentType:
    """
    根据 current_agent 路由到对应的 Agent 节点

    Args:
        state: 当前状态

    Returns:
        目标 Agent 类型
    """
    current_agent = state.get("current_agent", "health")

    valid_agents = {"health", "report", "reminder", "research", "compliance"}

    if current_agent not in valid_agents:
        logger.warning(f"[Routing] 未知的 agent 类型: {current_agent}，默认路由到 health")
        return "health"

    logger.debug(f"[Routing] 路由到 Agent: {current_agent}")
    return current_agent


def should_continue_or_end(state: MedicalState) -> NodeTarget:
    """
    判断是否继续处理或结束

    每次 graph.invoke() 处理一条用户消息并返回一个响应。
    多轮对话通过多次 invoke() 调用实现，而非在单次 invoke 中循环。

    Args:
        state: 当前状态

    Returns:
        "__end__" - 结束图执行（默认行为）
    """
    is_completed = state.get("is_completed", False)

    # 已完成时结束
    if is_completed:
        logger.debug("[Routing] 会话已完成，结束执行")
        return "__end__"

    # 注意：不再检查 stage == "completed"
    # 即使预约已完成，用户仍可以继续对话（如说谢谢、询问其他问题）

    # 默认：处理完毕后结束本轮，下一条消息会触发新的 invoke()
    logger.debug("[Routing] 本轮处理完毕，结束执行")
    return "__end__"


def route_from_health_stage(state: MedicalState) -> str:
    """
    从 HealthAgent 阶段路由

    根据 HealthAgent 的当前阶段决定下一步动作。

    Args:
        state: 当前状态

    Returns:
        下一个节点名称
    """
    appointment_confirmed = state.get("appointment_confirmed", False)

    # 预约已确认 -> 结束
    if appointment_confirmed:
        return "__end__"

    # 注意：不再检查 stage == "completed"
    # 即使预约已完成，用户仍可以继续对话

    # 其他情况继续处理
    return "response"


def route_after_router(state: MedicalState) -> AgentType:
    """
    路由节点之后的路由决策

    在 router_node 处理后，根据更新后的 current_agent 决定路由。

    Args:
        state: 当前状态

    Returns:
        目标 Agent 类型
    """
    return route_by_agent_type(state)


def route_after_agent(state: MedicalState) -> NodeTarget:
    """
    Agent 节点之后的路由决策

    在任意 Agent 节点处理后，决定是继续还是结束。

    Args:
        state: 当前状态

    Returns:
        下一个节点或结束标识
    """
    # 检查是否有新的路由需求
    routing_confidence = state.get("routing_confidence", 0.0)

    # 高置信度的路由变更，需要重新路由
    if routing_confidence > 0.9:
        new_agent = state.get("current_agent")
        logger.debug(f"[Routing] 高置信度路由变更到: {new_agent}")
        # 这里返回 response 让流程继续，实际切换在下一轮
        return "response"

    return should_continue_or_end(state)


def should_switch_agent(state: MedicalState) -> bool:
    """
    判断是否需要切换 Agent

    Args:
        state: 当前状态

    Returns:
        是否需要切换
    """
    routing_confidence = state.get("routing_confidence", 0.0)

    # 置信度超过阈值才切换
    return routing_confidence >= 0.7


def get_next_stage(current_stage: str, agent_type: str) -> str:
    """
    获取下一个阶段

    Args:
        current_stage: 当前阶段
        agent_type: Agent 类型

    Returns:
        下一个阶段名称
    """
    # 各 Agent 的阶段流转定义
    stage_flows = {
        "health": {
            "greeting": "health_consultation",
            "health_consultation": "symptom_assessment",
            "symptom_assessment": "appointment_inquiry",
            "appointment_inquiry": "patient_info_collection",
            "patient_info_collection": "ophthalmology_triage",
            "ophthalmology_triage": "medical_history",
            "medical_history": "appointment_booking",
            "appointment_booking": "completed",
        },
        "report": {
            "greeting": "select_action",
            "select_action": "generate_report",
            "generate_report": "analyze_history",
            "analyze_history": "completed",
        },
        "reminder": {
            "greeting": "select_action",
            "select_action": "view_reminders",
            "view_reminders": "create_reminder",
            "create_reminder": "completed",
            "config_settings": "completed",
        },
        "research": {
            "greeting": "research_init",
            "research_init": "data_query",
            "data_query": "statistical_analysis",
            "web_search": "literature_review",
            "statistical_analysis": "research_design",
            "literature_review": "research_design",
            "research_design": "paper_writing",
            "paper_writing": "completed",
        },
        "compliance": {
            "greeting": "data_loading",
            "data_loading": "reviewing",
            "reviewing": "result",
            "result": "completed",
        },
    }

    flow = stage_flows.get(agent_type, {})
    return flow.get(current_stage, current_stage)
