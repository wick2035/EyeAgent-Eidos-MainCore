"""
消息持久化适配器抽象接口

提供可插拔的持久化机制，支持：
- MySQLPersistenceAdapter: 生产环境
- NullPersistenceAdapter: 禁用持久化（测试/调试）
- InMemoryPersistenceAdapter: 内存存储（单元测试）
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class PersistenceAdapter(ABC):
    """
    消息持久化适配器抽象接口

    职责：
    - 保存用户消息
    - 创建/更新 AI 回复（两阶段写入）
    - 更新会话标题
    """

    @abstractmethod
    def save_user_message(
        self,
        chat_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
        is_first_message: bool = False,
    ) -> str:
        """
        保存用户消息

        Args:
            chat_id: 会话ID
            content: 消息内容
            sender_id: 发送者ID
            context: 上下文信息 {patient_info, stage, agent_type}
            is_first_message: 是否为首条消息

        Returns:
            str: 消息ID
        """
        pass

    @abstractmethod
    def create_assistant_placeholder(
        self,
        chat_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        创建 AI 回复占位（status=running）

        用于两阶段写入：先占位，执行成功后更新内容

        Args:
            chat_id: 会话ID
            context: 上下文信息

        Returns:
            str: 消息ID（用于后续更新）
        """
        pass

    @abstractmethod
    def prepare_normal_turn(
        self,
        chat_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
        is_first_message: bool = False,
    ) -> Dict[str, str]:
        """创建普通用户消息和助手占位。"""
        pass

    @abstractmethod
    def prepare_edit_resend_turn(
        self,
        chat_id: str,
        source_message_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """创建编辑重发的用户消息和助手占位。"""
        pass

    @abstractmethod
    def prepare_regenerate_turn(
        self,
        chat_id: str,
        source_assistant_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """创建重新生成的助手占位。"""
        pass

    @abstractmethod
    def update_assistant_success(
        self,
        message_id: str,
        content: str,
        token_used: Optional[int] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        更新 AI 回复为成功状态

        Args:
            message_id: 消息ID
            content: 完整回复内容
            token_used: Token 消耗数
            tool_results: 统一后的工具调用结果数组
            citations: 前端 CitationBlock 引用来源数组
            context: 更新的上下文信息

        Returns:
            bool: 是否更新成功
        """
        pass

    @abstractmethod
    def update_assistant_failed(
        self,
        message_id: str,
        error_message: str,
    ) -> bool:
        """
        更新 AI 回复为失败状态

        Args:
            message_id: 消息ID
            error_message: 错误信息

        Returns:
            bool: 是否更新成功
        """
        pass

    @abstractmethod
    def update_assistant_final_status(
        self,
        message_id: str,
        status: str,
        content: str,
        error_message: Optional[str] = None,
        token_used: Optional[int] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        更新 AI 回复为最终状态

        用于取消或异常等非正常完成场景，确保 running 占位不会残留。
        正常完成仍优先使用 update_assistant_success。
        """
        pass

    @abstractmethod
    def update_conversation_title(
        self,
        chat_id: str,
        first_message: str,
    ) -> bool:
        """
        根据首条消息更新会话标题

        Args:
            chat_id: 会话ID
            first_message: 首条用户消息

        Returns:
            bool: 是否更新成功
        """
        pass

    @abstractmethod
    def is_first_message(self, chat_id: str) -> bool:
        """
        判断是否为会话的首条消息

        Args:
            chat_id: 会话ID

        Returns:
            bool: 是否为首条消息
        """
        pass


class NullPersistenceAdapter(PersistenceAdapter):
    """
    空适配器 - 不做任何持久化

    用途：
    - 测试环境不需要数据库
    - 调试时临时禁用持久化
    """

    def save_user_message(
        self,
        chat_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
        is_first_message: bool = False,
    ) -> str:
        logger.debug(f"[NullAdapter] save_user_message: chat_id={chat_id}")
        return "null-msg-id"

    def create_assistant_placeholder(
        self,
        chat_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        logger.debug(f"[NullAdapter] create_assistant_placeholder: chat_id={chat_id}")
        return "null-assistant-id"

    def prepare_normal_turn(
        self,
        chat_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
        is_first_message: bool = False,
    ) -> Dict[str, str]:
        logger.debug(f"[NullAdapter] prepare_normal_turn: chat_id={chat_id}")
        return {"user_message_id": "null-msg-id", "assistant_message_id": "null-assistant-id"}

    def prepare_edit_resend_turn(
        self,
        chat_id: str,
        source_message_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        logger.debug(f"[NullAdapter] prepare_edit_resend_turn: chat_id={chat_id}")
        return {"user_message_id": "null-msg-id", "assistant_message_id": "null-assistant-id"}

    def prepare_regenerate_turn(
        self,
        chat_id: str,
        source_assistant_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        logger.debug(f"[NullAdapter] prepare_regenerate_turn: chat_id={chat_id}")
        return {"assistant_message_id": "null-assistant-id"}

    def update_assistant_success(
        self,
        message_id: str,
        content: str,
        token_used: Optional[int] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        logger.debug(f"[NullAdapter] update_assistant_success: message_id={message_id}")
        return True

    def update_assistant_failed(
        self,
        message_id: str,
        error_message: str,
    ) -> bool:
        logger.debug(f"[NullAdapter] update_assistant_failed: message_id={message_id}")
        return True

    def update_assistant_final_status(
        self,
        message_id: str,
        status: str,
        content: str,
        error_message: Optional[str] = None,
        token_used: Optional[int] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        logger.debug(
            f"[NullAdapter] update_assistant_final_status: message_id={message_id}, status={status}"
        )
        return True

    def update_conversation_title(
        self,
        chat_id: str,
        first_message: str,
    ) -> bool:
        logger.debug(f"[NullAdapter] update_conversation_title: chat_id={chat_id}")
        return True

    def is_first_message(self, chat_id: str) -> bool:
        return True


class InMemoryPersistenceAdapter(PersistenceAdapter):
    """
    内存适配器 - 用于单元测试

    所有消息存储在内存中，可用于断言验证
    """

    def __init__(self):
        self.messages: Dict[str, Dict[str, Any]] = {}
        self.conversations: Dict[str, Dict[str, Any]] = {}
        self._message_counter: Dict[str, int] = {}

    def save_user_message(
        self,
        chat_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
        is_first_message: bool = False,
    ) -> str:
        import uuid
        message_id = str(uuid.uuid4())

        self.messages[message_id] = {
            "id": message_id,
            "chat_id": chat_id,
            "content": content,
            "sender_id": sender_id,
            "message_type": "user",
            "context": context,
            "status": "success",
            "is_first_message": is_first_message,
        }

        self._message_counter[chat_id] = self._message_counter.get(chat_id, 0) + 1

        if is_first_message:
            self.update_conversation_title(chat_id, content)

        return message_id

    def create_assistant_placeholder(
        self,
        chat_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        import uuid
        message_id = str(uuid.uuid4())

        self.messages[message_id] = {
            "id": message_id,
            "chat_id": chat_id,
            "content": "",
            "message_type": "assistant",
            "context": context,
            "status": "running",
        }

        return message_id

    def prepare_normal_turn(
        self,
        chat_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
        is_first_message: bool = False,
    ) -> Dict[str, str]:
        user_message_id = self.save_user_message(
            chat_id=chat_id,
            content=content,
            sender_id=sender_id,
            context=context,
            is_first_message=is_first_message,
        )
        assistant_message_id = self.create_assistant_placeholder(chat_id=chat_id, context=context)
        return {"user_message_id": user_message_id, "assistant_message_id": assistant_message_id}

    def prepare_edit_resend_turn(
        self,
        chat_id: str,
        source_message_id: str,
        content: str,
        sender_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        return self.prepare_normal_turn(chat_id, content, sender_id, context, False)

    def prepare_regenerate_turn(
        self,
        chat_id: str,
        source_assistant_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        assistant_message_id = self.create_assistant_placeholder(chat_id=chat_id, context=context)
        return {"assistant_message_id": assistant_message_id}

    def update_assistant_success(
        self,
        message_id: str,
        content: str,
        token_used: Optional[int] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if message_id not in self.messages:
            return False

        self.messages[message_id].update({
            "content": content,
            "status": "success",
            "token_used": token_used,
            "tool_results": tool_results,
            "citations": citations,
        })

        if context:
            self.messages[message_id]["context"] = context

        # 更新消息计数
        chat_id = self.messages[message_id]["chat_id"]
        self._message_counter[chat_id] = self._message_counter.get(chat_id, 0) + 1

        return True

    def update_assistant_failed(
        self,
        message_id: str,
        error_message: str,
    ) -> bool:
        if message_id not in self.messages:
            return False

        self.messages[message_id].update({
            "status": "failed",
            "error_message": error_message,
        })

        return True

    def update_assistant_final_status(
        self,
        message_id: str,
        status: str,
        content: str,
        error_message: Optional[str] = None,
        token_used: Optional[int] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if message_id not in self.messages:
            return False

        self.messages[message_id].update({
            "content": content,
            "status": status,
            "token_used": token_used,
            "tool_results": tool_results,
            "citations": citations,
            "error_message": error_message,
        })

        if context:
            self.messages[message_id]["context"] = context

        return True

    def update_conversation_title(
        self,
        chat_id: str,
        first_message: str,
    ) -> bool:
        title = first_message[:20] + "..." if len(first_message) > 20 else first_message
        self.conversations[chat_id] = {"title": title}
        return True

    def is_first_message(self, chat_id: str) -> bool:
        return self._message_counter.get(chat_id, 0) == 0

    # 测试辅助方法
    def get_messages_by_chat(self, chat_id: str) -> List[Dict[str, Any]]:
        """获取会话的所有消息（测试用）"""
        return [m for m in self.messages.values() if m["chat_id"] == chat_id]

    def clear(self):
        """清空所有数据（测试用）"""
        self.messages.clear()
        self.conversations.clear()
        self._message_counter.clear()
