import json
from datetime import datetime
from typing import Optional

from application.services.conversation_activity_guard import (
    ConversationActivityGuard,
)
from domain.models.chat_entity import MessageContext
from domain.models.chat_turn_request import ChatTurnRequestEntity
from infrastructure.database.mysql_connection import get_db_connection
from infrastructure.repositories.chat_repository_impl import (
    get_conversation_repository,
    get_message_repository,
)
from infrastructure.repositories.chat_turn_request_repository_impl import (
    DuplicateChatTurnRequestError,
    get_chat_turn_request_repository,
)
from presentation.schemas.platform_chat_turn_schemas import (
    AbortPlatformChatTurnResponse,
    PlatformChatTurnStatusResponse,
    PreparePlatformChatTurnRequest,
    PreparePlatformChatTurnResponse,
)


class RequestIdempotencyConflictError(ValueError):
    code = "REQUEST_IDEMPOTENCY_CONFLICT"

    def __init__(self):
        super().__init__(self.code)


class ChatTurnNotFoundError(ValueError):
    code = "CHAT_TURN_NOT_FOUND"

    def __init__(self):
        super().__init__(self.code)


class TurnAlreadyCompletedError(ValueError):
    code = "TURN_ALREADY_COMPLETED"

    def __init__(self):
        super().__init__(self.code)


class InvalidTurnStateError(ValueError):
    code = "INVALID_TURN_STATE"

    def __init__(self):
        super().__init__(self.code)


class PlatformChatTurnService:
    """附件回合 prepare、状态与终态持久化编排。"""

    def __init__(
        self,
        db=None,
        turn_repo=None,
        conversation_repo=None,
        message_repo=None,
        chat_persistence_service=None,
        activity_guard: Optional[ConversationActivityGuard] = None,
    ):
        self.db = db or get_db_connection()
        self.turn_repo = turn_repo or get_chat_turn_request_repository()
        self.conversation_repo = (
            conversation_repo or get_conversation_repository()
        )
        self.message_repo = message_repo or get_message_repository()
        if activity_guard is None:
            activity_guard = ConversationActivityGuard(
                self.turn_repo,
                self.message_repo,
            )
        self.activity_guard = activity_guard
        if chat_persistence_service is None:
            from application.services.chat_persistence_service import (
                ChatPersistenceService,
            )

            chat_persistence_service = ChatPersistenceService(
                self.conversation_repo,
                self.message_repo,
                db=self.db,
                activity_guard=self.activity_guard,
            )
        self.chat_persistence_service = chat_persistence_service

    def prepare(
        self,
        request: PreparePlatformChatTurnRequest,
    ) -> PreparePlatformChatTurnResponse:
        try:
            with self.db.transaction():
                conversation = self._lock_conversation(request.conversation_id)
                existing = self.turn_repo.get_for_update(
                    request.doctor_id,
                    request.request_id,
                )
                if existing is not None:
                    return self._assert_same_fingerprint_and_project(
                        existing,
                        request.request_fingerprint,
                    )

                self.activity_guard.assert_idle_locked(
                    request.conversation_id,
                )
                previous_active_node_id = conversation.active_node_id
                ids = self._prepare_tree_nodes(request)
                now = datetime.now()
                entity = ChatTurnRequestEntity(
                    doctor_id=request.doctor_id,
                    request_id=request.request_id,
                    request_fingerprint=request.request_fingerprint,
                    operation=request.operation,
                    conversation_id=request.conversation_id,
                    session_id=request.session_id,
                    patient_id=request.patient_id,
                    source_message_id=request.source_message_id,
                    implicit_prompt_id=request.implicit_prompt_id,
                    attachment_ids_json=json.dumps(
                        request.attachment_ids,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    user_message_id=ids["user_message_id"],
                    assistant_message_id=ids["assistant_message_id"],
                    previous_active_node_id=previous_active_node_id,
                    status="prepared",
                    create_time=now,
                    update_time=now,
                )
                self.turn_repo.insert(entity)
                stored = self.turn_repo.get_for_update(
                    request.doctor_id,
                    request.request_id,
                )
                if stored is None:
                    raise ChatTurnNotFoundError()
                return self._project_prepare_response(stored)
        except DuplicateChatTurnRequestError:
            # 不同会话锁不能序列化同一幂等键；唯一键败者必须先回滚，
            # 再在新事务中重读胜者，不能把 duplicate key 暴露为 500。
            with self.db.transaction():
                winner = self.turn_repo.get_for_update(
                    request.doctor_id,
                    request.request_id,
                )
                if winner is None:
                    raise
                return self._assert_same_fingerprint_and_project(
                    winner,
                    request.request_fingerprint,
                )

    def status(
        self,
        doctor_id: str,
        request_id: str,
    ) -> PlatformChatTurnStatusResponse:
        entity = self._get_turn(doctor_id, request_id)
        if entity is None:
            raise ChatTurnNotFoundError()
        return self._project_status_response(entity)

    def abort(
        self,
        doctor_id: str,
        request_id: str,
        conversation_id: Optional[str] = None,
    ):
        prefetched = self._get_turn(doctor_id, request_id)
        if prefetched is None:
            raise ChatTurnNotFoundError()
        if conversation_id is not None and prefetched.conversation_id != conversation_id:
            raise ChatTurnNotFoundError()

        with self.db.transaction():
            self._lock_conversation(prefetched.conversation_id)
            entity = self.turn_repo.get_for_update(doctor_id, request_id)
            if entity is None:
                raise ChatTurnNotFoundError()

            if entity.status == "completed":
                raise TurnAlreadyCompletedError()
            if entity.status == "cancelled":
                return self._project_abort_response(entity)
            if entity.status == "failed":
                return self._project_status_response(entity)

            current_status = entity.status
            if current_status not in ("prepared", "streaming"):
                raise InvalidTurnStateError()
            changed = self.turn_repo.compare_and_set_status(
                doctor_id,
                request_id,
                current_status,
                "cancelled",
            )
            if not changed:
                latest = self.turn_repo.get_for_update(doctor_id, request_id)
                if latest is None:
                    raise ChatTurnNotFoundError()
                if latest.status == "completed":
                    raise TurnAlreadyCompletedError()
                if latest.status == "cancelled":
                    return self._project_abort_response(latest)
                return self._project_status_response(latest)

            if current_status == "prepared":
                if entity.operation != "regenerate":
                    self._require_message_update(
                        entity.user_message_id,
                        {"status": "cancelled", "deleted": True},
                    )
                self._require_message_update(
                    entity.assistant_message_id,
                    {"status": "cancelled", "deleted": True},
                )
                self._restore_active_node_with_cas(entity)
            else:
                # 用户主动停止 streaming：用户节点与附件绑定保持可见。
                self._require_message_update(
                    entity.assistant_message_id,
                    {"status": "cancelled"},
                )

            latest = self.turn_repo.get_for_update(doctor_id, request_id) or entity
            return self._project_abort_response(latest)

    def mark_failed(
        self,
        doctor_id: str,
        request_id: str,
        error_code: str,
    ) -> PlatformChatTurnStatusResponse:
        return self._mark_terminal(
            doctor_id,
            request_id,
            new_status="failed",
            error_code=error_code,
        )

    def mark_completed(
        self,
        doctor_id: str,
        request_id: str,
    ) -> PlatformChatTurnStatusResponse:
        return self._mark_terminal(
            doctor_id,
            request_id,
            new_status="completed",
            error_code=None,
        )

    def expire_stale_turns(self, now: Optional[datetime] = None) -> int:
        """在会话行锁下修复过期回合及其消息树。"""
        now = now or datetime.now()
        expired_count = 0
        for candidate in self.turn_repo.list_stale(now):
            with self.db.transaction():
                self._lock_conversation(candidate.conversation_id)
                entity = self.turn_repo.get_for_update(
                    candidate.doctor_id,
                    candidate.request_id,
                )
                if (
                    entity is None
                    or entity.status not in ("prepared", "streaming")
                    or entity.deadline_at is None
                    or entity.deadline_at > now
                ):
                    continue
                current_status = entity.status
                changed = self.turn_repo.compare_and_set_status(
                    entity.doctor_id,
                    entity.request_id,
                    current_status,
                    "cancelled",
                    error_code="TURN_EXPIRED",
                )
                if not changed:
                    continue

                if current_status == "prepared":
                    if entity.operation != "regenerate":
                        self._require_message_update(
                            entity.user_message_id,
                            {"status": "cancelled", "deleted": True},
                        )
                    self._require_message_update(
                        entity.assistant_message_id,
                        {"status": "cancelled", "deleted": True},
                    )
                    self._restore_active_node_with_cas(entity)
                else:
                    self._require_message_update(
                        entity.assistant_message_id,
                        {
                            "status": "cancelled",
                            "error_message": "TURN_EXPIRED",
                        },
                    )
                expired_count += 1
        return expired_count

    def _mark_terminal(
        self,
        doctor_id: str,
        request_id: str,
        new_status: str,
        error_code: Optional[str],
    ) -> PlatformChatTurnStatusResponse:
        prefetched = self._get_turn(doctor_id, request_id)
        if prefetched is None:
            raise ChatTurnNotFoundError()
        with self.db.transaction():
            self._lock_conversation(prefetched.conversation_id)
            entity = self.turn_repo.get_for_update(doctor_id, request_id)
            if entity is None:
                raise ChatTurnNotFoundError()
            if entity.status == new_status:
                return self._project_status_response(entity)
            if entity.status in ("completed", "failed", "cancelled"):
                raise InvalidTurnStateError()
            changed = self.turn_repo.compare_and_set_status(
                doctor_id,
                request_id,
                ("prepared", "streaming"),
                new_status,
                error_code=error_code,
            )
            if not changed:
                latest = self.turn_repo.get_for_update(doctor_id, request_id)
                if latest is None:
                    raise ChatTurnNotFoundError()
                return self._project_status_response(latest)
            if new_status == "failed":
                self._require_message_update(
                    entity.assistant_message_id,
                    {"status": "failed", "error_message": error_code},
                )
            latest = self.turn_repo.get_for_update(doctor_id, request_id) or entity
            return self._project_status_response(latest)

    def _prepare_tree_nodes(self, request) -> dict[str, str]:
        metadata = {"attachment_ids": list(request.attachment_ids)}
        if request.attachment_only:
            metadata.update({
                "attachment_only": True,
                "implicit_prompt_id": request.implicit_prompt_id,
            })
        context = MessageContext(metadata=metadata)

        if request.operation in ("normal", "edit_resend"):
            first_message = (
                request.operation == "normal"
                and self.chat_persistence_service.is_first_message(
                    request.conversation_id
                )
            )
            user, assistant = self.chat_persistence_service.create_turn(
                request.conversation_id,
                request.message,
                request.doctor_id,
                context=context,
                source_message_id=request.source_message_id,
                mode="edit" if request.operation == "edit_resend" else "normal",
            )
            if first_message and request.message:
                self.chat_persistence_service.update_conversation_title(
                    request.conversation_id,
                    request.message,
                )
            return {
                "user_message_id": user.id,
                "assistant_message_id": assistant.id,
            }

        assistant = self.chat_persistence_service.create_assistant_regeneration(
            request.conversation_id,
            request.source_message_id,
            context=context,
        )
        return {
            "user_message_id": assistant.parent_id,
            "assistant_message_id": assistant.id,
        }

    def _lock_conversation(self, conversation_id: str):
        lock_by_id = getattr(self.conversation_repo, "lock_by_id", None)
        if lock_by_id is not None:
            conversation = lock_by_id(conversation_id)
        else:
            conversation = self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise ValueError(f"会话不存在: {conversation_id}")
        return conversation

    def _get_turn(self, doctor_id: str, request_id: str):
        get = getattr(self.turn_repo, "get", None)
        if get is not None:
            return get(doctor_id, request_id)
        return self.turn_repo.get_for_update(doctor_id, request_id)

    def _restore_active_node_with_cas(self, entity) -> None:
        compare_and_set = getattr(
            self.conversation_repo,
            "compare_and_set_active_node",
            None,
        )
        if compare_and_set is not None:
            compare_and_set(
                entity.conversation_id,
                entity.assistant_message_id,
                entity.previous_active_node_id,
            )
            return
        conversation = self.conversation_repo.get_by_id(entity.conversation_id)
        if conversation and conversation.active_node_id == entity.assistant_message_id:
            self.conversation_repo.update_active_node(
                entity.conversation_id,
                entity.previous_active_node_id,
            )

    def _require_message_update(self, message_id: str, updates: dict) -> None:
        if not self.message_repo.update(message_id, updates):
            raise RuntimeError(f"更新消息失败: {message_id}")

    def _assert_same_fingerprint_and_project(
        self,
        entity,
        request_fingerprint: str,
    ) -> PreparePlatformChatTurnResponse:
        if entity.request_fingerprint != request_fingerprint:
            raise RequestIdempotencyConflictError()
        return self._project_prepare_response(entity)

    @staticmethod
    def _project_prepare_response(entity) -> PreparePlatformChatTurnResponse:
        return PreparePlatformChatTurnResponse(
            request_id=entity.request_id,
            request_fingerprint=entity.request_fingerprint,
            status=entity.status,
            attachment_only=entity.attachment_only,
            implicit_prompt_id=entity.implicit_prompt_id,
        )

    @staticmethod
    def _project_abort_response(entity) -> AbortPlatformChatTurnResponse:
        return AbortPlatformChatTurnResponse(
            request_id=entity.request_id,
            conversation_id=entity.conversation_id,
            status="cancelled",
        )

    @staticmethod
    def _project_status_response(entity) -> PlatformChatTurnStatusResponse:
        updated_at = entity.update_time
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()
        return PlatformChatTurnStatusResponse(
            request_id=entity.request_id,
            status=entity.status,
            session_id=entity.session_id,
            user_message_id=entity.user_message_id,
            assistant_message_id=entity.assistant_message_id,
            error_code=entity.error_code,
            updated_at=str(updated_at),
        )
