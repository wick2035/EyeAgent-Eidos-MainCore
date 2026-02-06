"""
响应节点

处理 Agent 响应的后处理，包括格式化、日志记录等。
"""
import logging
from typing import Dict, Any

from langchain_core.messages import AIMessage

from agents.graph.state import MedicalState

logger = logging.getLogger(__name__)


def response_node(state: MedicalState) -> Dict[str, Any]:
    """
    响应后处理节点

    处理 Agent 响应后的清理和格式化工作。
    每次 graph.invoke() 处理一条消息，处理完毕后标记本轮完成。

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    last_response = state.get("last_response", "")
    current_agent = state.get("current_agent", "health")
    stage = state.get("stage", "greeting")

    # 日志记录
    logger.info(
        f"[ResponseNode] agent={current_agent}, stage={stage}, "
        f"response_len={len(last_response)}"
    )

    # 每次 invoke 处理一条消息，处理完毕后标记完成
    # 多轮对话通过多次 invoke() 调用实现
    return {"is_completed": True}


def _should_mark_completed(state: MedicalState) -> bool:
    """
    判断是否应该标记会话完成

    Args:
        state: 当前状态

    Returns:
        是否应该标记完成
    """
    stage = state.get("stage", "")
    current_agent = state.get("current_agent", "")

    # 明确的完成阶段
    if stage == "completed":
        return True

    # HealthAgent: 预约确认
    if current_agent == "health" and state.get("appointment_confirmed", False):
        return True

    # ReminderAgent: 提醒创建
    if current_agent == "reminder" and state.get("reminder_created", False):
        return True

    # ReportAgent: PDF 生成
    if current_agent == "report" and state.get("report_generated", False):
        return True

    # ComplianceAgent: 审查完成
    if current_agent == "compliance" and state.get("compliance_review_completed", False):
        return True

    # ResearchAgent: 任务完成（根据阶段判断）
    if current_agent == "research":
        research_complete_stages = ["completed", "paper_writing"]
        if stage in research_complete_stages:
            # 检查是否有明确的退出意图
            last_response = state.get("last_response", "")
            exit_keywords = ["完成", "结束", "再见", "谢谢"]
            if any(kw in last_response for kw in exit_keywords):
                return True

    return False


def format_response_node(state: MedicalState) -> Dict[str, Any]:
    """
    格式化响应节点（可选的额外处理）

    用于对响应进行额外的格式化处理。

    Args:
        state: 当前状态

    Returns:
        状态更新字典
    """
    last_response = state.get("last_response", "")
    role = state.get("role", "patient")

    # 根据角色添加尾注（如果需要）
    formatted_response = last_response

    # 如果是医生模式，可以添加专业标注
    if role == "doctor" and last_response:
        # 检查是否需要添加数据来源说明
        if "数据" in last_response or "统计" in last_response:
            if "数据来源" not in last_response:
                formatted_response += "\n\n*数据已脱敏处理*"

    if formatted_response != last_response:
        return {
            "last_response": formatted_response,
            "messages": [AIMessage(content=formatted_response)],
        }

    return {}
