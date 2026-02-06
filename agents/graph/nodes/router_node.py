"""
路由节点

使用 HybridIntentRouter 进行意图识别和 Agent 路由。
"""
import logging
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage

from agents.graph.state import MedicalState
from utils.hybrid_intent_router import get_hybrid_router

logger = logging.getLogger(__name__)


def router_node(state: MedicalState) -> Dict[str, Any]:
    """
    路由节点 - 决定消息应该路由到哪个 Agent

    Args:
        state: 当前状态

    Returns:
        状态更新字典，包含:
        - current_agent: 目标 Agent 类型
        - routing_confidence: 路由置信度
        - routing_reason: 路由原因
    """
    messages = state.get("messages", [])
    role = state.get("role", "patient")
    current_agent = state.get("current_agent", "health")
    stage = state.get("stage", "greeting")

    # 获取最后一条用户消息
    last_message = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_message = msg.content
            break
        elif isinstance(msg, dict) and msg.get("type") == "human":
            last_message = msg.get("content", "")
            break

    if not last_message:
        logger.warning("[RouterNode] 未找到用户消息，保持当前 Agent")
        return {
            "current_agent": current_agent,
            "routing_confidence": 0.0,
            "routing_reason": "无用户消息",
        }

    # 构建对话历史（用于上下文理解）
    conversation_history = _build_conversation_history(messages)

    # 使用混合路由器进行意图识别
    router = get_hybrid_router()
    result = router.route(
        message=last_message,
        role=role,
        conversation_history=conversation_history,
        current_agent=current_agent,
        current_stage=stage,
    )

    detected_agent = result.get("agent_type", "health")
    confidence = result.get("confidence", 0.0)
    reason = result.get("reason", "默认路由")
    strategy = result.get("strategy", "unknown")

    # 判断是否需要切换 Agent
    should_switch = router.should_switch_agent(
        current_agent=current_agent,
        detected_intent=result,
        threshold=0.7,
    )

    if should_switch:
        target_agent = detected_agent
        logger.info(
            f"[RouterNode] 切换 Agent: {current_agent} -> {target_agent} "
            f"(confidence={confidence:.2f}, strategy={strategy})"
        )
        # 切换 Agent 时重置 stage
        new_stage = "greeting"
    else:
        target_agent = current_agent
        new_stage = stage
        logger.debug(
            f"[RouterNode] 保持 Agent: {target_agent} "
            f"(detected={detected_agent}, confidence={confidence:.2f})"
        )

    # 合规审查仅对医生开放，患者角色无法路由到合规Agent
    if target_agent == "compliance" and role != "doctor":
        target_agent = current_agent if current_agent != "compliance" else "health"
        new_stage = stage if target_agent == current_agent else "greeting"
        logger.warning("[RouterNode] 患者角色无法访问合规审查Agent，保持当前Agent")

    return {
        "current_agent": target_agent,
        "stage": new_stage,
        "routing_confidence": confidence,
        "routing_reason": reason,
    }


def _build_conversation_history(messages: List[Any]) -> List[Dict[str, str]]:
    """
    从 messages 构建对话历史

    Args:
        messages: LangGraph 消息列表

    Returns:
        对话历史列表 [{"role": "user"/"assistant", "content": "..."}]
    """
    history = []

    for msg in messages[-10:]:  # 只取最近10条
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.content})
        elif hasattr(msg, "content"):
            # AIMessage 或其他消息类型
            msg_type = getattr(msg, "type", "assistant")
            if msg_type == "human":
                history.append({"role": "user", "content": msg.content})
            else:
                history.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, dict):
            role = "user" if msg.get("type") == "human" else "assistant"
            history.append({"role": role, "content": msg.get("content", "")})

    return history


def get_target_agent(state: MedicalState) -> str:
    """
    获取目标 Agent 类型（用于条件边）

    Args:
        state: 当前状态

    Returns:
        Agent 类型: "health" | "report" | "reminder" | "research"
    """
    return state.get("current_agent", "health")
