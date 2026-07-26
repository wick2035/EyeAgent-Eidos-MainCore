"""
对话持久化服务
编排对话和消息的持久化操作
"""
import uuid
import json
import logging
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from contextlib import nullcontext

from domain.models.chat_entity import (
    ChatConversationEntity,
    ChatMessageEntity,
    MessageContext
)
from application.services.legacy_text_turn_authority import (
    LegacyTextTurnAuthority,
    parse_legacy_text_turn_metadata,
)
from infrastructure.repositories.chat_repository_impl import (
    get_conversation_repository,
    get_message_repository,
    ChatConversationRepositoryImpl,
    ChatMessageRepositoryImpl
)

logger = logging.getLogger(__name__)


def generate_provisional_title(content: str, max_length: int = 20) -> str:
    """根据首问生成可用作模型降级结果的短标题。"""
    if not content or not content.strip():
        return "新对话"

    normalized = content.strip().rstrip("。，！？,.!?、；;：:")
    if not normalized:
        return "新对话"
    if len(normalized) <= max_length:
        return normalized
    return normalized[:max_length] + "..."


class LegacyBranchSourceInvalidError(Exception):
    """旧分支源消息缺少可信 canonical 配置。"""


class LegacyBranchForbiddenError(Exception):
    """旧分支会话不属于请求中的医生。"""


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
        message_repo: Optional[ChatMessageRepositoryImpl] = None,
        db=None,
        activity_guard=None,
    ):
        """
        初始化服务

        Args:
            conversation_repo: 会话仓储（可选，默认使用单例）
            message_repo: 消息仓储（可选，默认使用单例）
        """
        self.conversation_repo = conversation_repo or get_conversation_repository()
        self.message_repo = message_repo or get_message_repository()
        self.db = (
            db
            or getattr(self.conversation_repo, "db", None)
            or getattr(self.message_repo, "db", None)
        )
        if activity_guard is None and self.db is not None:
            from application.services.conversation_activity_guard import (
                ConversationActivityGuard,
            )
            from infrastructure.repositories.chat_turn_request_repository_impl import (
                ChatTurnRequestRepositoryImpl,
            )

            activity_guard = ConversationActivityGuard(
                ChatTurnRequestRepositoryImpl(self.db),
                self.message_repo,
            )
        self.activity_guard = activity_guard
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
        self._require_active_node_update(conversation_id, root_id)
        logger.info(f"[ChatPersistenceService] 创建会话: {conversation_id}")
        return conversation_id

    def _sibling_group_id(self, parent_id: str, message_type: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"chat-sibling:{parent_id}:{message_type}"))

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

    def _transaction_context(self):
        if self.db is None:
            return nullcontext()
        return self.db.transaction()

    def _lock_conversation_and_assert_idle(self, chat_id: str):
        lock_by_id = getattr(self.conversation_repo, "lock_by_id", None)
        if lock_by_id is not None:
            conversation = lock_by_id(chat_id)
            if conversation is None:
                raise ValueError(f"会话不存在: {chat_id}")
        else:
            conversation = self._must_get_conversation(chat_id)
        if self.activity_guard is not None:
            self.activity_guard.assert_idle_locked(chat_id)
        return conversation

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

        self._require_active_node_update(conversation.id, root_id)
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
        initialize_first_question: bool = False,
    ) -> Tuple[ChatMessageEntity, ChatMessageEntity]:
        with self._transaction_context():
            conversation = self._lock_conversation_and_assert_idle(chat_id)
            turn = self._create_turn_locked(
                chat_id,
                content,
                sender_id,
                context=context,
                source_message_id=source_message_id,
                mode=mode,
                conversation=conversation,
            )
            if initialize_first_question and content.strip():
                self.update_conversation_title(chat_id, content)
            return turn

    def create_legacy_edit_turn(
        self,
        *,
        chat_id: str,
        source_message_id: str,
        content: str,
        sender_id: str,
        context: Optional[MessageContext],
        expected_authority: LegacyTextTurnAuthority,
    ) -> Tuple[ChatMessageEntity, ChatMessageEntity]:
        """在同一会话锁事务内复核旧文本源权威并创建编辑分支。"""

        with self._transaction_context():
            conversation = self._lock_conversation_and_assert_idle(chat_id)
            authority = self._assert_legacy_branch_authority_locked(
                conversation=conversation,
                chat_id=chat_id,
                source_message_id=source_message_id,
                branch_mode="edit",
                doctor_id=sender_id,
                agent_type=expected_authority.agent_type,
                patient_id=expected_authority.patient_id,
            )
            if authority != expected_authority:
                raise LegacyBranchSourceInvalidError()
            return self._create_turn_locked(
                chat_id,
                content,
                sender_id,
                context=context,
                source_message_id=source_message_id,
                mode="edit",
                conversation=conversation,
            )

    def _create_turn_locked(
        self,
        chat_id: str,
        content: str,
        sender_id: Optional[str],
        context: Optional[MessageContext] = None,
        source_message_id: Optional[str] = None,
        mode: str = "normal",
        conversation: Optional[ChatConversationEntity] = None,
    ) -> Tuple[ChatMessageEntity, ChatMessageEntity]:
        conversation = conversation or self._must_get_conversation(chat_id)
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
        self._require_active_node_update(chat_id, assistant.id)
        return user, assistant

    def create_assistant_regeneration(
        self,
        chat_id: str,
        source_assistant_id: str,
        context: Optional[MessageContext] = None,
    ) -> ChatMessageEntity:
        with self._transaction_context():
            self._lock_conversation_and_assert_idle(chat_id)
            return self._create_assistant_regeneration_locked(
                chat_id,
                source_assistant_id,
                context=context,
            )

    def create_legacy_assistant_regeneration(
        self,
        *,
        chat_id: str,
        source_assistant_id: str,
        doctor_id: str,
        expected_authority: LegacyTextTurnAuthority,
        context: Optional[MessageContext] = None,
    ) -> ChatMessageEntity:
        """在同一会话锁事务内复核旧文本源权威并创建重生分支。"""

        with self._transaction_context():
            conversation = self._lock_conversation_and_assert_idle(chat_id)
            authority = self._assert_legacy_branch_authority_locked(
                conversation=conversation,
                chat_id=chat_id,
                source_message_id=source_assistant_id,
                branch_mode="regenerate",
                doctor_id=doctor_id,
                agent_type=expected_authority.agent_type,
                patient_id=expected_authority.patient_id,
            )
            if authority != expected_authority:
                raise LegacyBranchSourceInvalidError()
            return self._create_assistant_regeneration_locked(
                chat_id,
                source_assistant_id,
                context=context,
            )

    def _create_assistant_regeneration_locked(
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
        self._require_active_node_update(chat_id, assistant.id)
        return assistant

    def _require_active_node_update(
        self,
        conversation_id: str,
        active_node_id: str,
    ) -> None:
        if not self.conversation_repo.update_active_node(
            conversation_id,
            active_node_id,
        ):
            raise RuntimeError(
                f"更新会话 active_node_id 失败: {conversation_id}"
            )

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
        原子初始化首问摘要与降级标题。

        Args:
            chat_id: 会话ID
            first_user_message: 首条用户消息

        Returns:
            bool: 是否更新成功
        """
        summary = first_user_message.strip() if first_user_message else ""
        if not summary:
            return False
        title = self.generate_title(summary)
        success = self.conversation_repo.initialize_first_question(
            chat_id,
            summary,
            title,
        )
        if success:
            logger.info(
                "[ChatPersistenceService] 已初始化首问元数据: chat_id=%s",
                chat_id,
            )
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

    def assert_legacy_branch_authority(
        self,
        *,
        chat_id: str,
        source_message_id: str,
        branch_mode: str,
        doctor_id: str,
        agent_type: str,
        patient_id: Optional[str],
    ) -> LegacyTextTurnAuthority:
        """在旧 edit/regenerate 创建任何节点前验证 owner 与源回合配置。"""

        try:
            with self._transaction_context():
                lock_by_id = getattr(self.conversation_repo, "lock_by_id", None)
                conversation = (
                    lock_by_id(chat_id)
                    if lock_by_id is not None
                    else self.conversation_repo.get_by_id(chat_id)
                )
                return self._assert_legacy_branch_authority_locked(
                    conversation=conversation,
                    chat_id=chat_id,
                    source_message_id=source_message_id,
                    branch_mode=branch_mode,
                    doctor_id=doctor_id,
                    agent_type=agent_type,
                    patient_id=patient_id,
                )
        except (LegacyBranchSourceInvalidError, LegacyBranchForbiddenError):
            raise
        except Exception:
            raise LegacyBranchSourceInvalidError() from None

    def _assert_legacy_branch_authority_locked(
        self,
        *,
        conversation: Optional[ChatConversationEntity],
        chat_id: str,
        source_message_id: str,
        branch_mode: str,
        doctor_id: str,
        agent_type: str,
        patient_id: Optional[str],
    ) -> LegacyTextTurnAuthority:
        if conversation is None:
            raise LegacyBranchSourceInvalidError()
        if (
            conversation.user_type != "doctor"
            or conversation.host_id != doctor_id
        ):
            raise LegacyBranchForbiddenError()

        source = self.message_repo.get_by_id(source_message_id)
        if (
            source is None
            or source.chat_id != chat_id
            or source.deleted
            or source.status != "success"
        ):
            raise LegacyBranchSourceInvalidError()

        if branch_mode == "edit":
            if source.message_type != "user":
                raise LegacyBranchSourceInvalidError()
            source_user = source
        elif branch_mode == "regenerate":
            if source.message_type != "assistant" or not source.parent_id:
                raise LegacyBranchSourceInvalidError()
            source_user = self.message_repo.get_by_id(source.parent_id)
            if (
                source_user is None
                or source_user.chat_id != chat_id
                or source_user.message_type != "user"
                or source_user.deleted
                or source_user.status != "success"
            ):
                raise LegacyBranchSourceInvalidError()
        else:
            raise LegacyBranchSourceInvalidError()

        self._assert_legacy_source_on_active_path(conversation, source)
        if source_user.sender_id != doctor_id:
            raise LegacyBranchForbiddenError()
        if (
            not isinstance(source_user.message_content, str)
            or not source_user.message_content.strip()
        ):
            raise LegacyBranchSourceInvalidError()
        authority = self._legacy_source_configuration(source_user.context)
        if (
            authority.agent_type != agent_type
            or authority.patient_id != patient_id
        ):
            raise LegacyBranchSourceInvalidError()
        return authority

    def _assert_legacy_source_on_active_path(
        self,
        conversation: ChatConversationEntity,
        source: ChatMessageEntity,
    ) -> None:
        """验证 source 位于结构完整的 canonical active path。"""

        active_node_id = conversation.active_node_id
        if not isinstance(active_node_id, str) or not active_node_id:
            raise LegacyBranchSourceInvalidError()

        current = self.message_repo.get_by_id(active_node_id)
        seen: set[str] = set()
        source_seen = False
        while current is not None:
            if (
                current.id in seen
                or current.chat_id != conversation.id
                or current.deleted
                or current.message_type not in {"root", "user", "assistant"}
            ):
                raise LegacyBranchSourceInvalidError()
            seen.add(current.id)
            source_seen = source_seen or current.id == source.id

            if current.message_type == "root":
                if current.parent_id is not None or current.status != "success":
                    raise LegacyBranchSourceInvalidError()
                if not source_seen:
                    raise LegacyBranchSourceInvalidError()
                return

            if not current.parent_id:
                raise LegacyBranchSourceInvalidError()
            parent = self.message_repo.get_by_id(current.parent_id)
            if (
                parent is None
                or parent.chat_id != conversation.id
                or parent.deleted
                or parent.status != "success"
                or current.message_order <= parent.message_order
            ):
                raise LegacyBranchSourceInvalidError()
            if (
                current.message_type == "user"
                and parent.message_type not in {"root", "assistant"}
            ):
                raise LegacyBranchSourceInvalidError()
            if (
                current.message_type == "assistant"
                and parent.message_type != "user"
            ):
                raise LegacyBranchSourceInvalidError()
            current = parent

        raise LegacyBranchSourceInvalidError()

    @staticmethod
    def _reject_duplicate_json_keys(
        pairs: List[Tuple[str, Any]],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise LegacyBranchSourceInvalidError()
            result[key] = value
        return result

    @staticmethod
    def _legacy_source_configuration(
        raw_context: Optional[str],
    ) -> LegacyTextTurnAuthority:
        if not isinstance(raw_context, str) or not raw_context:
            raise LegacyBranchSourceInvalidError()
        try:
            context_list = json.loads(
                raw_context,
                object_pairs_hook=(
                    ChatPersistenceService._reject_duplicate_json_keys
                ),
            )
        except LegacyBranchSourceInvalidError:
            raise
        except (TypeError, ValueError, json.JSONDecodeError):
            raise LegacyBranchSourceInvalidError() from None
        allowed_context_keys = {
            "patient_info",
            "conversation_stage",
            "tool_results",
            "citations",
            "metadata",
        }
        if (
            not isinstance(context_list, list)
            or not context_list
            or not all(
                isinstance(item, dict)
                and len(item) == 1
                and next(iter(item)) in allowed_context_keys
                for item in context_list
            )
        ):
            raise LegacyBranchSourceInvalidError()
        metadata_entries = [
            item["metadata"]
            for item in context_list
            if isinstance(item, dict) and "metadata" in item
        ]
        if len(metadata_entries) != 1 or not isinstance(
            metadata_entries[0],
            dict,
        ):
            raise LegacyBranchSourceInvalidError()
        metadata = metadata_entries[0]
        try:
            return parse_legacy_text_turn_metadata(metadata)
        except (TypeError, ValueError):
            raise LegacyBranchSourceInvalidError()

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
        return generate_provisional_title(content, max_length)

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
            logger.error(
                "chat_persistence_failed operation=update_message "
                "exception_class=%s",
                type(e).__name__,
                exc_info=None,
            )
            return False

    def finalize_platform_assistant(
        self,
        message_id: str,
        *,
        status: str,
        content: Optional[str] = None,
        token_used: Optional[int] = None,
        context: Optional[MessageContext] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """在调用方事务内严格收敛 prepared assistant；失败不得静默。"""
        updates: Dict[str, Any] = {"status": status}
        if content is not None:
            updates["message_content"] = content
        if token_used is not None:
            updates["token_used"] = token_used
        if context is not None:
            updates["context"] = context.to_json()
        if error_message is not None:
            updates["error_message"] = error_message

        if not self.message_repo.update(message_id, updates):
            return False
        if status != "success":
            return True

        message = self.message_repo.get_by_id(message_id)
        if message is None:
            return False
        total_messages = self._count_visible_messages(message.chat_id)
        return bool(
            self.conversation_repo.update_summary_and_count(
                message.chat_id,
                None,
                total_messages,
            )
        )

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
