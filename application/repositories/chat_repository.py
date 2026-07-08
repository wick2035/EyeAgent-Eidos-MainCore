"""
对话持久化仓储接口
定义对话和消息的 CRUD 操作抽象接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from domain.models.chat_entity import ChatConversationEntity, ChatMessageEntity


class IChatConversationRepository(ABC):
    """
    对话会话仓储接口

    职责：
    - 管理 chat_conversation 表的 CRUD 操作
    """

    @abstractmethod
    def create(self, conversation: ChatConversationEntity) -> ChatConversationEntity:
        """
        创建新会话

        Args:
            conversation: 会话实体

        Returns:
            ChatConversationEntity: 创建后的会话实体
        """
        pass

    @abstractmethod
    def get_by_id(self, conversation_id: str) -> Optional[ChatConversationEntity]:
        """
        根据ID获取会话

        Args:
            conversation_id: 会话UUID

        Returns:
            Optional[ChatConversationEntity]: 会话实体，不存在返回 None
        """
        pass

    @abstractmethod
    def list_by_host(
        self,
        host_id: str,
        user_type: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[ChatConversationEntity]:
        """
        获取用户的会话列表

        Args:
            host_id: 用户ID（患者/医生UUID）
            user_type: 用户类型 (patient/doctor)
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[ChatConversationEntity]: 会话列表，按更新时间降序
        """
        pass

    @abstractmethod
    def count_by_host(self, host_id: str, user_type: str) -> int:
        """
        获取用户的会话总数

        Args:
            host_id: 用户ID
            user_type: 用户类型

        Returns:
            int: 会话总数
        """
        pass

    @abstractmethod
    def update_title(self, conversation_id: str, title: str) -> bool:
        """
        更新会话标题

        Args:
            conversation_id: 会话UUID
            title: 新标题

        Returns:
            bool: 是否更新成功
        """
        pass

    @abstractmethod
    def update_summary_and_count(
        self,
        conversation_id: str,
        summary: Optional[str],
        total_messages: int
    ) -> bool:
        """
        更新会话摘要和消息数量

        Args:
            conversation_id: 会话UUID
            summary: 摘要（可选）
            total_messages: 消息总数

        Returns:
            bool: 是否更新成功
        """
        pass

    @abstractmethod
    def update_active_node(self, conversation_id: str, active_node_id: str) -> bool:
        """
        更新会话当前活跃叶子节点

        Args:
            conversation_id: 会话UUID
            active_node_id: 当前活跃叶子消息ID

        Returns:
            bool: 是否更新成功
        """
        pass

    @abstractmethod
    def soft_delete(self, conversation_id: str) -> bool:
        """
        软删除会话

        Args:
            conversation_id: 会话UUID

        Returns:
            bool: 是否删除成功
        """
        pass


class IChatMessageRepository(ABC):
    """
    对话消息仓储接口

    职责：
    - 管理 chat_message 表的 CRUD 操作
    """

    @abstractmethod
    def create(self, message: ChatMessageEntity) -> ChatMessageEntity:
        """
        创建新消息

        Args:
            message: 消息实体

        Returns:
            ChatMessageEntity: 创建后的消息实体
        """
        pass

    @abstractmethod
    def get_by_chat_id(
        self,
        chat_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[ChatMessageEntity]:
        """
        获取会话的所有消息

        Args:
            chat_id: 会话UUID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[ChatMessageEntity]: 消息列表，按 message_order 升序
        """
        pass

    @abstractmethod
    def get_by_id(self, message_id: str) -> Optional[ChatMessageEntity]:
        """
        根据消息ID获取消息

        Args:
            message_id: 消息UUID

        Returns:
            Optional[ChatMessageEntity]: 消息实体，不存在返回 None
        """
        pass

    @abstractmethod
    def get_by_ids(self, chat_id: str, ids: List[str]) -> List[ChatMessageEntity]:
        """
        按ID列表获取同一会话内的消息

        Args:
            chat_id: 会话UUID
            ids: 消息ID列表

        Returns:
            List[ChatMessageEntity]: 按输入顺序返回存在的消息
        """
        pass

    @abstractmethod
    def get_children(self, chat_id: str, parent_id: str) -> List[ChatMessageEntity]:
        """
        获取某父节点下的直接子消息

        Args:
            chat_id: 会话UUID
            parent_id: 父消息ID

        Returns:
            List[ChatMessageEntity]: 子消息列表
        """
        pass

    @abstractmethod
    def get_latest_sibling_order(self, chat_id: str, parent_id: str, message_type: str) -> int:
        """
        获取同父同角色消息的最大 message_order

        Args:
            chat_id: 会话UUID
            parent_id: 父消息ID
            message_type: 消息类型

        Returns:
            int: 最大排序值，无结果返回 0
        """
        pass

    @abstractmethod
    def get_latest_order(self, chat_id: str) -> int:
        """
        获取会话中最新的消息序号

        Args:
            chat_id: 会话UUID

        Returns:
            int: 最新消息序号，无消息返回 0
        """
        pass

    @abstractmethod
    def count_by_chat_id(self, chat_id: str) -> int:
        """
        获取会话的消息总数

        Args:
            chat_id: 会话UUID

        Returns:
            int: 消息总数
        """
        pass

    @abstractmethod
    def batch_create(self, messages: List[ChatMessageEntity]) -> List[ChatMessageEntity]:
        """
        批量创建消息

        Args:
            messages: 消息实体列表

        Returns:
            List[ChatMessageEntity]: 创建后的消息列表
        """
        pass

    @abstractmethod
    def soft_delete_by_chat_id(self, chat_id: str) -> int:
        """
        软删除会话的所有消息

        Args:
            chat_id: 会话UUID

        Returns:
            int: 删除的消息数量
        """
        pass
