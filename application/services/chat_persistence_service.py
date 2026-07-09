"""
对话持久化服务
编排对话和消息的持久化操作
"""
import uuid
import json
import logging
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from domain.models.chat_entity import (
    ChatConversationEntity,
    ChatMessageEntity,
    MessageContext
)
from infrastructure.repositories.chat_repository_impl import (
    get_conversation_repository,
    get_message_repository,
    ChatConversationRepositoryImpl,
    ChatMessageRepositoryImpl
)

logger = logging.getLogger(__name__)


class ChatPersistenceService:
    """
    对话持久化服务

    职责：
    - 协调会话和消息的创建、保存、加载
    - 生成会话标题
    - 序列化/反序列化上下文
    """

    def __init__(
        self,
        conversation_repo: Optional[ChatConversationRepositoryImpl] = None,
        message_repo: Optional[ChatMessageRepositoryImpl] = None
    ):
        """
        初始化服务

        Args:
            conversation_repo: 会话仓储（可选，默认使用单例）
            message_repo: 消息仓储（可选，默认使用单例）
        """
        self.conversation_repo = conversation_repo or get_conversation_repository()
        self.message_repo = message_repo or get_message_repository()
        logger.info("[ChatPersistenceService] 初始化完成")

    def create_conversation(
        self,
        host_id: str,
        user_type: str = "patient",
        title: str = "新对话"
    ) -> str:
        """
        创建新会话

        Args:
            host_id: 用户ID（患者/医生UUID）
            user_type: 用户类型 (patient/doctor)
            title: 初始标题

        Returns:
            str: 新创建的会话ID
        """
        conversation_id = str(uuid.uuid4())
        now = datetime.now()

        conversation = ChatConversationEntity(
            id=conversation_id,
            user_type=user_type,
            host_id=host_id,
            title=title,
            summary=None,
            total_messages=0,
            create_time=now,
            create_by=host_id,
            update_time=now,
            update_by=host_id,
            deleted=False,
            version=1
        )

        self.conversation_repo.create(conversation)
        root_id = str(uuid.uuid4())
        root = ChatMessageEntity(
            id=root_id,
            chat_id=conversation_id,
            parent_id=None,
            siblings_group_id=None,
            message_order=1,
            message_content="",
            message_type="root",
            sender_id=None,
            context=None,
            token_used=None,
            status="success",
            error_message=None,
            create_time=now,
            create_by=host_id,
            update_time=now,
            update_by=host_id,
            deleted=False,
            version=1,
        )
        self.message_repo.create(root)
        self.conversation_repo.update_active_node(conversation_id, root_id)
        logger.info(f"[ChatPersistenceService] 创建会话: {conversation_id}")
        return conversation_id

    def _sibling_group_id(self, parent_id: str, message_type: str) -> str:
        return f"sg:{parent_id}:{message_type}"

    def _next_order(self, chat_id: str) -> int:
        return self.message_repo.get_latest_order(chat_id) + 1

    def _count_visible_messages(self, chat_id: str) -> int:
        messages = self.message_repo.get_by_chat_id(chat_id)
        total = self.message_repo.count_by_chat_id(chat_id)
        root_count = len([m for m in messages if m.message_type == "root"])
        if root_count and total >= len(messages):
            return max(total - root_count, 0)
        return total

    def _must_get_conversation(self, chat_id: str) -> ChatConversationEntity:
        conversation = self.conversation_repo.get_by_id(chat_id)
        if not conversation:
            raise ValueError(f"会话不存在: {chat_id}")
        return conversation

    def _must_get_message(self, message_id: str) -> ChatMessageEntity:
        message = self.message_repo.get_by_id(message_id)
        if not message:
            raise ValueError(f"消息不存在: {message_id}")
        return message

    def _ensure_active_root(
        self,
        conversation: ChatConversationEntity,
        actor_id: Optional[str],
        now: datetime,
    ) -> str:
        if conversation.active_node_id:
            return conversation.active_node_id

        roots = [
            message
            for message in self.message_repo.get_by_chat_id(conversation.id)
            if message.message_type == "root"
        ]
        if roots:
            root_id = roots[0].id
        else:
            root_id = str(uuid.uuid4())
            root = ChatMessageEntity(
                id=root_id,
                chat_id=conversation.id,
                parent_id=None,
                siblings_group_id=None,
                message_order=self._next_order(conversation.id),
                message_content="",
                message_type="root",
                sender_id=None,
                context=None,
                token_used=None,
                status="success",
                error_message=None,
                create_time=now,
                create_by=actor_id,
                update_time=now,
                update_by=actor_id,
                deleted=False,
                version=1,
            )
            self.message_repo.create(root)

        self.conversation_repo.update_active_node(conversation.id, root_id)
        conversation.active_node_id = root_id
        return root_id

    def create_turn(
        self,
        chat_id: str,
        content: str,
        sender_id: Optional[str],
        context: Optional[MessageContext] = None,
        source_message_id: Optional[str] = None,
        mode: str = "normal",
    ) -> Tuple[ChatMessageEntity, ChatMessageEntity]:
        conversation = self._must_get_conversation(chat_id)
        now = datetime.now()

        if mode not in ("normal", "edit"):
            raise ValueError(f"不支持的消息创建模式: {mode}")

        if mode == "edit":
            if not source_message_id:
                raise ValueError("编辑重发必须提供 source_message_id")
            source = self._must_get_message(source_message_id)
            if source.chat_id != chat_id or source.message_type != "user":
                raise ValueError("source_message_id 必须是当前会话的用户消息")
            user_parent_id = source.parent_id
            user_group_id = source.siblings_group_id or self._sibling_group_id(user_parent_id, "user")
            if not source.siblings_group_id:
                self.message_repo.update(source.id, {"siblings_group_id": user_group_id})
        else:
            user_parent_id = self._ensure_active_root(conversation, sender_id, now)
            user_group_id = self._sibling_group_id(user_parent_id, "user")

        user = ChatMessageEntity(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            parent_id=user_parent_id,
            siblings_group_id=user_group_id,
            message_order=self._next_order(chat_id),
            message_content=content,
            message_type="user",
            sender_id=sender_id,
            context=context.to_json() if context else None,
            token_used=None,
            status="success",
            create_time=now,
            create_by=sender_id,
            update_time=now,
            update_by=sender_id,
            deleted=False,
            version=1,
        )
        self.message_repo.create(user)

        assistant = ChatMessageEntity(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            parent_id=user.id,
            siblings_group_id=self._sibling_group_id(user.id, "assistant"),
            message_order=self._next_order(chat_id),
            message_content="",
            message_type="assistant",
            sender_id=None,
            context=None,
            token_used=None,
            status="streaming",
            create_time=now,
            create_by=sender_id,
            update_time=now,
            update_by=sender_id,
            deleted=False,
            version=1,
        )
        self.message_repo.create(assistant)
        self.conversation_repo.update_active_node(chat_id, assistant.id)
        return user, assistant

    def create_assistant_regeneration(
        self,
        chat_id: str,
        source_assistant_id: str,
        context: Optional[MessageContext] = None,
    ) -> ChatMessageEntity:
        source = self._must_get_message(source_assistant_id)
        if source.chat_id != chat_id or source.message_type != "assistant":
            raise ValueError("source_assistant_id 必须是当前会话的助手消息")
        group_id = source.siblings_group_id or self._sibling_group_id(source.parent_id, "assistant")
        if not source.siblings_group_id:
            self.message_repo.update(source.id, {"siblings_group_id": group_id})
        now = datetime.now()
        assistant = ChatMessageEntity(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            parent_id=source.parent_id,
            siblings_group_id=group_id,
            message_order=self._next_order(chat_id),
            message_content="",
            message_type="assistant",
            sender_id=None,
            context=context.to_json() if context else None,
            token_used=None,
            status="streaming",
            create_time=now,
            create_by=None,
            update_time=now,
            update_by=None,
            deleted=False,
            version=1,
        )
        self.message_repo.create(assistant)
        self.conversation_repo.update_active_node(chat_id, assistant.id)
        return assistant

    def _path_to_root(self, chat_id: str, leaf_id: str) -> List[ChatMessageEntity]:
        path = []
        current = self._must_get_message(leaf_id)
        while current:
            if current.chat_id != chat_id:
                raise ValueError("active_node_id 不属于当前会话")
            path.append(current)
            if not current.parent_id:
                break
            current = self._must_get_message(current.parent_id)
        path.reverse()
        return path

    def load_active_path(self, chat_id: str):
        conversation = self._must_get_conversation(chat_id)
        if not conversation.active_node_id:
            return conversation, [], {}
        path = self._path_to_root(chat_id, conversation.active_node_id)
        visible = [m for m in path if m.message_type != "root"]
        sibling_map = {}
        for message in visible:
            if message.parent_id:
                siblings = [
                    m for m in self.message_repo.get_children(chat_id, message.parent_id)
                    if m.message_type == message.message_type
                ]
                sibling_map[message.id] = siblings
        return conversation, visible, sibling_map

    def switch_active_branch(self, chat_id: str, through_message_id: str) -> bool:
        message = self._must_get_message(through_message_id)
        if message.chat_id != chat_id:
            raise ValueError("消息不属于当前会话")
        leaf = self._resolve_branch_leaf(chat_id, message)
        return self.conversation_repo.update_active_node(chat_id, leaf.id)

    def _resolve_branch_leaf(self, chat_id: str, message: ChatMessageEntity) -> ChatMessageEntity:
        current = message
        while True:
            children = [
                m for m in self.message_repo.get_children(chat_id, current.id)
                if m.status in ("success", "done", "streaming", "error", "failed", "cancelled")
            ]
            if not children:
                return current
            current = children[-1]

    def save_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        sender_id: Optional[str] = None,
        context: Optional[MessageContext] = None,
        token_used: Optional[int] = None,
        status: str = "success",
    ) -> ChatMessageEntity:
        """
        保存消息

        Args:
            chat_id: 会话ID
            role: 消息角色 (user/assistant/system)
            content: 消息内容
            sender_id: 发送者ID
            context: 上下文信息
            token_used: 使用的token数
            status: 消息状态 (running/success/failed/cancelled)

        Returns:
            ChatMessageEntity: 保存的消息实体
        """
        # 获取下一个消息序号
        latest_order = self.message_repo.get_latest_order(chat_id)
        message_order = latest_order + 1

        message_id = str(uuid.uuid4())
        now = datetime.now()

        # 序列化上下文
        context_json = None
        if context:
            context_json = context.to_json()

        message = ChatMessageEntity(
            id=message_id,
            chat_id=chat_id,
            message_order=message_order,
            message_content=content,
            message_type=role,
            sender_id=sender_id,
            context=context_json,
            token_used=token_used,
            status=status,
            error_message=None,
            create_time=now,
            create_by=sender_id,
            update_time=now,
            update_by=sender_id,
            deleted=False,
            version=1
        )

        self.message_repo.create(message)

        # 只有成功的消息才更新会话的消息数量（running 状态不计入）
        if status == "success":
            total_messages = self._count_visible_messages(chat_id)
            self.conversation_repo.update_summary_and_count(chat_id, None, total_messages)

        logger.debug(f"[ChatPersistenceService] 保存消息: {message_id}, order={message_order}, status={status}")
        return message

    def update_conversation_title(self, chat_id: str, first_user_message: str) -> bool:
        """
        根据首条用户消息更新会话标题

        Args:
            chat_id: 会话ID
            first_user_message: 首条用户消息

        Returns:
            bool: 是否更新成功
        """
        title = self.generate_title(first_user_message)
        success = self.conversation_repo.update_title(chat_id, title)
        if success:
            logger.info(f"[ChatPersistenceService] 更新会话标题: {chat_id} -> {title}")
        return success

    def load_conversation(
        self,
        chat_id: str
    ) -> Tuple[Optional[ChatConversationEntity], List[ChatMessageEntity]]:
        """
        加载会话和所有消息

        Args:
            chat_id: 会话ID

        Returns:
            Tuple[Optional[ChatConversationEntity], List[ChatMessageEntity]]:
                (会话实体, 消息列表)
        """
        conversation = self.conversation_repo.get_by_id(chat_id)
        if not conversation:
            logger.warning(f"[ChatPersistenceService] 会话不存在: {chat_id}")
            return None, []

        messages = self.message_repo.get_by_chat_id(chat_id)
        logger.info(f"[ChatPersistenceService] 加载会话: {chat_id}, 消息数={len(messages)}")
        return conversation, messages

    def get_conversation(self, chat_id: str) -> Optional[ChatConversationEntity]:
        """
        获取会话信息

        Args:
            chat_id: 会话ID

        Returns:
            Optional[ChatConversationEntity]: 会话实体
        """
        return self.conversation_repo.get_by_id(chat_id)

    def list_conversations(
        self,
        host_id: str,
        user_type: str = "patient",
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[ChatConversationEntity], int, bool]:
        """
        获取用户的会话列表

        Args:
            host_id: 用户ID
            user_type: 用户类型
            limit: 返回数量
            offset: 偏移量

        Returns:
            Tuple[List[ChatConversationEntity], int, bool]:
                (会话列表, 总数, 是否还有更多)
        """
        conversations = self.conversation_repo.list_by_host(
            host_id, user_type, limit, offset
        )
        total = self.conversation_repo.count_by_host(host_id, user_type)
        has_more = (offset + len(conversations)) < total

        logger.info(
            f"[ChatPersistenceService] 获取会话列表: host={host_id}, "
            f"count={len(conversations)}, total={total}"
        )
        return conversations, total, has_more

    def delete_conversation(self, chat_id: str) -> bool:
        """
        删除会话及其所有消息

        Args:
            chat_id: 会话ID

        Returns:
            bool: 是否删除成功
        """
        # 先删除消息
        self.message_repo.soft_delete_by_chat_id(chat_id)
        # 再删除会话
        success = self.conversation_repo.soft_delete(chat_id)
        if success:
            logger.info(f"[ChatPersistenceService] 删除会话: {chat_id}")
        return success

    def generate_title(self, content: str, max_length: int = 20) -> str:
        """
        根据消息内容生成会话标题

        规则：
        1. 去除末尾标点
        2. 截取前 max_length 个字符
        3. 超出部分添加 "..."
        4. 空消息默认 "新对话"

        Args:
            content: 消息内容
            max_length: 最大长度

        Returns:
            str: 生成的标题
        """
        if not content or not content.strip():
            return "新对话"

        # 去除首尾空白
        content = content.strip()

        # 去除末尾标点
        punctuation = "。，！？,.!?、；;：:"
        content = content.rstrip(punctuation)

        if not content:
            return "新对话"

        if len(content) <= max_length:
            return content

        return content[:max_length] + "..."

    def build_context(
        self,
        patient_info: Optional[Dict[str, Any]] = None,
        conversation_stage: Optional[str] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MessageContext:
        """
        构建消息上下文

        Args:
            patient_info: 患者信息
            conversation_stage: 对话阶段
            tool_results: 工具调用结果
            citations: 前端 CitationBlock 引用来源
            metadata: 其他元数据

        Returns:
            MessageContext: 上下文对象
        """
        return MessageContext(
            patient_info=patient_info,
            conversation_stage=conversation_stage,
            tool_results=tool_results,
            citations=citations,
            metadata=metadata
        )

    def update_message(
        self,
        message_id: str,
        content: Optional[str] = None,
        status: Optional[str] = None,
        token_used: Optional[int] = None,
        context: Optional[MessageContext] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        更新消息（用于两阶段写入）

        Args:
            message_id: 消息ID
            content: 消息内容
            status: 消息状态
            token_used: Token 消耗
            context: 上下文信息
            error_message: 错误信息

        Returns:
            bool: 是否更新成功
        """
        try:
            # 构建更新字段
            updates: Dict[str, Any] = {}

            if content is not None:
                updates["message_content"] = content
            if status is not None:
                updates["status"] = status
            if token_used is not None:
                updates["token_used"] = token_used
            if error_message is not None:
                updates["error_message"] = error_message
            if context is not None:
                updates["context"] = context.to_json()

            if not updates:
                logger.warning(f"[ChatPersistenceService] 更新消息无字段: {message_id}")
                return False

            success = self.message_repo.update(message_id, updates)

            # 如果状态从 running 变为 success，更新会话的消息数量
            if success and status == "success":
                # 获取消息所属的会话ID
                message = self.message_repo.get_by_id(message_id)
                if message:
                    total_messages = self._count_visible_messages(message.chat_id)
                    self.conversation_repo.update_summary_and_count(
                        message.chat_id, None, total_messages
                    )

            logger.debug(f"[ChatPersistenceService] 更新消息: {message_id}, updates={list(updates.keys())}")
            return success

        except Exception as e:
            logger.error(f"[ChatPersistenceService] 更新消息失败: {e}", exc_info=True)
            return False

    def is_first_message(self, chat_id: str) -> bool:
        """
        判断是否为会话的首条消息

        Args:
            chat_id: 会话ID

        Returns:
            bool: 是否为首条消息
        """
        return self._count_visible_messages(chat_id) == 0


# 单例实例
_persistence_service: Optional[ChatPersistenceService] = None


def get_chat_persistence_service() -> ChatPersistenceService:
    """获取对话持久化服务单例"""
    global _persistence_service
    if _persistence_service is None:
        _persistence_service = ChatPersistenceService()
    return _persistence_service
