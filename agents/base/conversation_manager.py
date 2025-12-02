"""
对话管理器 - 管理对话历史和上下文
支持可选的数据库持久化
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from domain.models.conversation import Conversation, Message
from domain.enums.agent_type import AgentType
from domain.enums.conversation_stage import ConversationStage
from domain.models.chat_entity import MessageContext
import logging

if TYPE_CHECKING:
    from application.services.chat_persistence_service import ChatPersistenceService

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    对话管理器

    职责：
    - 管理对话历史
    - 格式化对话上下文
    - 维护对话元数据
    - 可选：持久化到数据库
    """

    def __init__(
        self,
        conversation: Conversation,
        persistence_service: Optional["ChatPersistenceService"] = None,
        db_conversation_id: Optional[str] = None
    ):
        """
        初始化对话管理器

        Args:
            conversation: Conversation领域模型
            persistence_service: 持久化服务（可选）
            db_conversation_id: 数据库会话ID（可选）
        """
        self.conversation = conversation
        self.persistence_service = persistence_service
        self.db_conversation_id = db_conversation_id
        self._is_first_user_message = True  # 标记是否为首条用户消息
        self._current_context: Optional[MessageContext] = None  # 当前上下文
        logger.info(f"[ConversationManager] 初始化: session={conversation.session_id}, db_id={db_conversation_id}")

    def set_persistence_service(
        self,
        service: "ChatPersistenceService",
        db_conversation_id: str
    ):
        """
        设置持久化服务

        Args:
            service: 持久化服务实例
            db_conversation_id: 数据库会话ID
        """
        self.persistence_service = service
        self.db_conversation_id = db_conversation_id
        logger.info(f"[ConversationManager] 设置持久化: db_id={db_conversation_id}")

    def set_context(self, context: MessageContext):
        """
        设置当前消息上下文（用于下次保存）

        Args:
            context: 消息上下文
        """
        self._current_context = context

    def add_user_message(self, content: str, sender_id: Optional[str] = None):
        """
        添加用户消息

        Args:
            content: 消息内容
            sender_id: 发送者ID
        """
        self.conversation.add_message("user", content)
        logger.debug(f"[ConversationManager] 添加用户消息: {content[:50]}...")

        # 持久化到数据库
        if self.persistence_service and self.db_conversation_id:
            try:
                self.persistence_service.save_message(
                    chat_id=self.db_conversation_id,
                    role="user",
                    content=content,
                    sender_id=sender_id,
                    context=self._current_context
                )

                # 首条用户消息时更新标题
                if self._is_first_user_message:
                    self.persistence_service.update_conversation_title(
                        self.db_conversation_id,
                        content
                    )
                    self._is_first_user_message = False

            except Exception as e:
                logger.error(f"[ConversationManager] 保存用户消息失败: {e}")

        # 清除上下文
        self._current_context = None

    def add_assistant_message(self, content: str, token_used: Optional[int] = None):
        """
        添加助手消息

        Args:
            content: 消息内容
            token_used: 使用的token数
        """
        self.conversation.add_message("assistant", content)
        logger.debug(f"[ConversationManager] 添加助手消息: {content[:50]}...")

        # 持久化到数据库
        if self.persistence_service and self.db_conversation_id:
            try:
                self.persistence_service.save_message(
                    chat_id=self.db_conversation_id,
                    role="assistant",
                    content=content,
                    sender_id=None,
                    context=self._current_context,
                    token_used=token_used
                )
            except Exception as e:
                logger.error(f"[ConversationManager] 保存助手消息失败: {e}")

        # 清除上下文
        self._current_context = None

    def get_history_text(self) -> str:
        """获取格式化的对话历史文本"""
        return self.conversation.get_history_text()

    def get_recent_messages(self, count: int = 5) -> List[Message]:
        """
        获取最近N条消息

        Args:
            count: 消息数量

        Returns:
            Message列表
        """
        return self.conversation.history[-count:] if self.conversation.history else []

    def get_message_count(self) -> int:
        """获取消息总数"""
        return len(self.conversation.history)

    def update_stage(self, new_stage: ConversationStage):
        """
        更新对话阶段

        Args:
            new_stage: 新阶段
        """
        old_stage = self.conversation.stage
        self.conversation.stage = new_stage
        logger.info(f"[ConversationManager] 阶段转换: {old_stage} -> {new_stage}")

    def mark_completed(self):
        """标记对话为已完成"""
        self.conversation.is_completed = True
        self.conversation.stage = ConversationStage.COMPLETED
        logger.info("[ConversationManager] 对话已完成")

    def is_completed(self) -> bool:
        """检查对话是否完成"""
        return self.conversation.is_completed

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self.conversation.metadata.get(key, default)

    def set_metadata(self, key: str, value: Any):
        """设置元数据"""
        self.conversation.metadata[key] = value

    def load_from_database(self, chat_id: str) -> bool:
        """
        从数据库加载历史对话

        Args:
            chat_id: 数据库会话ID

        Returns:
            bool: 是否加载成功
        """
        if not self.persistence_service:
            logger.warning("[ConversationManager] 未配置持久化服务，无法加载")
            return False

        try:
            conversation_entity, messages = self.persistence_service.load_conversation(chat_id)

            if not conversation_entity:
                logger.warning(f"[ConversationManager] 会话不存在: {chat_id}")
                return False

            # 恢复历史消息
            for msg in messages:
                self.conversation.add_message(msg.message_type, msg.message_content)

            # 更新状态
            self.db_conversation_id = chat_id
            self._is_first_user_message = len(messages) == 0

            logger.info(f"[ConversationManager] 加载历史对话: {chat_id}, 消息数={len(messages)}")
            return True

        except Exception as e:
            logger.error(f"[ConversationManager] 加载历史对话失败: {e}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.conversation.session_id,
            "patient_id": self.conversation.patient_id,
            "agent_type": self.conversation.agent_type.value,
            "stage": self.conversation.stage.value,
            "is_completed": self.conversation.is_completed,
            "message_count": self.get_message_count(),
            "metadata": self.conversation.metadata,
            "db_conversation_id": self.db_conversation_id,
        }
