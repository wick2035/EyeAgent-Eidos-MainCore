"""
ID 映射管理模块

处理 LangGraph thread_id 与现有系统 ID（session_id, conversation_id）的映射关系。

映射策略：
- conversation_id 存在时: thread_id = "conv_{conversation_id}"
- 仅 session_id 时: thread_id = "sess_{session_id}"
"""
from typing import Optional, Dict
import uuid
import logging

logger = logging.getLogger(__name__)


class ThreadIDManager:
    """
    线程ID管理器

    负责 LangGraph thread_id 与现有 ID 体系的映射。

    现有系统ID体系：
    - session_id: 内存会话ID，30分钟TTL，格式 "sess_{uuid[:16]}"
    - conversation_id: MySQL持久化会话ID，永久存储，UUID格式

    LangGraph thread_id 格式：
    - "conv_{conversation_id}" - 持久化会话
    - "sess_{session_id}" - 临时会话
    """

    @staticmethod
    def get_thread_id(
        session_id: str,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        获取 LangGraph 的 thread_id

        优先级：
        1. conversation_id（已持久化的对话）
        2. session_id（临时会话）

        Args:
            session_id: 会话ID
            conversation_id: 数据库会话ID（可选）

        Returns:
            str: LangGraph thread_id
        """
        if conversation_id:
            thread_id = f"conv_{conversation_id}"
        else:
            thread_id = f"sess_{session_id}"

        logger.debug(f"[ThreadIDManager] 映射: session={session_id}, conv={conversation_id} -> thread={thread_id}")
        return thread_id

    @staticmethod
    def parse_thread_id(thread_id: str) -> Dict[str, str]:
        """
        解析 thread_id 获取原始ID信息

        Args:
            thread_id: LangGraph thread_id

        Returns:
            dict: {"type": "conversation"|"session"|"unknown", "id": "原始ID"}
        """
        if thread_id.startswith("conv_"):
            return {"type": "conversation", "id": thread_id[5:]}
        elif thread_id.startswith("sess_"):
            return {"type": "session", "id": thread_id[5:]}
        else:
            logger.warning(f"[ThreadIDManager] 未知的 thread_id 格式: {thread_id}")
            return {"type": "unknown", "id": thread_id}

    @staticmethod
    def is_persistent_thread(thread_id: str) -> bool:
        """
        判断是否为持久化线程（有 conversation_id）

        Args:
            thread_id: LangGraph thread_id

        Returns:
            bool: 是否为持久化线程
        """
        return thread_id.startswith("conv_")

    @staticmethod
    def create_conversation_id() -> str:
        """
        创建新的 conversation_id

        Returns:
            str: 新的 UUID 格式的 conversation_id
        """
        return str(uuid.uuid4())

    @staticmethod
    def create_session_id(prefix: str = "sess") -> str:
        """
        创建新的 session_id

        Args:
            prefix: 前缀，默认 "sess"

        Returns:
            str: 新的 session_id
        """
        return f"{prefix}_{uuid.uuid4().hex[:16]}"


def get_thread_config(
    session_id: str,
    conversation_id: Optional[str] = None
) -> Dict[str, Dict[str, str]]:
    """
    获取 LangGraph 线程配置

    这是调用 graph.invoke() 时需要传递的配置。

    Args:
        session_id: 会话ID
        conversation_id: 数据库会话ID

    Returns:
        dict: {"configurable": {"thread_id": "..."}}
    """
    thread_id = ThreadIDManager.get_thread_id(session_id, conversation_id)
    return {"configurable": {"thread_id": thread_id}}


def get_branch_thread_config(
    session_id: str,
    conversation_id: Optional[str],
    branch_node_id: str,
) -> Dict[str, Dict[str, str]]:
    """
    获取分支级 LangGraph 线程配置。

    编辑重发/重新生成会创建新的 active leaf。它们不能复用 conversation 级
    checkpoint，否则 LangGraph 的 add_messages 会把旧分支后续消息合入本轮输入。
    """
    base_thread_id = ThreadIDManager.get_thread_id(session_id, conversation_id)
    return {"configurable": {"thread_id": f"{base_thread_id}_branch_{branch_node_id}"}}
