"""
响应节点

处理 Agent 响应的后处理，包括格式化、日志记录等。
"""
import re
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

    # === 清理原始 ID ===
    if last_response:
        cleaned = _strip_ids_from_response(last_response)
        if cleaned != last_response:
            logger.info("[ResponseNode] 已从响应中清理原始ID")
            last_response = cleaned

    # === 输出安全校验 ===
    from utils.input_guard import check_output_safety

    if last_response:
        output_check = check_output_safety(last_response)
        if not output_check["is_safe"]:
            logger.warning(
                f"[ResponseNode] 输出安全检查失败: {output_check['issues']}"
            )
            return {
                "is_completed": True,
                "last_response": output_check["sanitized_response"],
                "messages": [AIMessage(content=output_check["sanitized_response"])],
            }

    # 响应内容为空时的兜底处理
    if not last_response:
        fallback = "抱歉，我没有生成有效回复，请重新提问。"
        logger.warning(f"[ResponseNode] 响应为空 (agent={current_agent}, stage={stage})，返回兜底消息")
        return {
            "is_completed": True,
            "last_response": fallback,
            "messages": [AIMessage(content=fallback)],
        }

    # 每次 invoke 处理一条消息，处理完毕后标记完成
    # 多轮对话通过多次 invoke() 调用实现
    # 如果响应被清理过（去除了ID），需要更新 state
    if last_response != state.get("last_response", ""):
        return {
            "is_completed": True,
            "last_response": last_response,
            "messages": [AIMessage(content=last_response)],
        }
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

    # RecommendationAgent: 推荐完成
    if current_agent == "recommendation" and state.get("recommendation_completed", False):
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


def _strip_ids_from_response(text: str) -> str:
    """
    从用户可见的响应文本中清除原始 UUID / 数据库 ID

    Args:
        text: 响应文本

    Returns:
        清理后的文本
    """
    # 标准 UUID 格式 (8-4-4-4-12)
    text = re.sub(
        r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
        '', text
    )
    # 32 位无横线 hex 字符串
    text = re.sub(r'\b[0-9a-fA-F]{32}\b', '', text)
    # 清理残留的 ID 标签（如 "doctorId: " 后面已无值）
    text = re.sub(
        r'(?:doctorId|hospitalId|patientId|appointmentId|id)\s*[:：]\s*(?=[,，。\s\n]|$)',
        '', text, flags=re.IGNORECASE
    )
    # 合并多余空格
    text = re.sub(r'  +', ' ', text)
    return text.strip()
