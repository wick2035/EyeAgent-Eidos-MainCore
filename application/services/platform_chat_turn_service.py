import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pydantic import ValidationError

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
    ResearchOptionsV2,
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


class SourceTurnAuthorityError(ValueError):
    code = "SOURCE_TURN_AUTHORITY_MISMATCH"

    def __init__(self):
        super().__init__(self.code)


_SAFE_SOURCE_TURN_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


@dataclass(frozen=True)
class _TurnAuthoritySnapshot:
    protocol_version: int
    agent_type: str
    attachment_scope: str
    patient_id: Optional[str]
    research_options: Optional[dict[str, Any]]
    attachment_ids: tuple[str, ...]
    attachment_only: bool
    implicit_prompt_id: Optional[str]


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
                self._assert_conversation_owner(
                    conversation,
                    request.doctor_id,
                )
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
                authority = self._resolve_turn_authority(request)
                ids = self._prepare_tree_nodes(request, authority)
                now = datetime.now()
                entity = ChatTurnRequestEntity(
                    doctor_id=request.doctor_id,
                    request_id=request.request_id,
                    request_fingerprint=request.request_fingerprint,
                    protocol_version=authority.protocol_version,
                    agent_type=authority.agent_type,
                    attachment_scope=authority.attachment_scope,
                    research_options_json=(
                        json.dumps(
                            authority.research_options,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        if authority.research_options is not None
                        else None
                    ),
                    operation=request.operation,
                    conversation_id=request.conversation_id,
                    session_id=request.session_id,
                    patient_id=authority.patient_id,
                    source_message_id=request.source_message_id,
                    implicit_prompt_id=request.implicit_prompt_id,
                    attachment_ids_json=json.dumps(
                        authority.attachment_ids,
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
        conversation = self.conversation_repo.get_by_id(entity.conversation_id)
        self._assert_conversation_owner(conversation, doctor_id)
        return self._project_status_response(entity)

    def abort(
        self,
        doctor_id: str,
        request_id: str,
        conversation_id: Optional[str] = None,
    ):
        prefetched = self.assert_turn_conversation(
            doctor_id,
            request_id,
            conversation_id,
        )

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

    def assert_turn_conversation(
        self,
        doctor_id: str,
        request_id: str,
        conversation_id: Optional[str],
    ):
        entity = self._get_turn(doctor_id, request_id)
        if entity is None:
            raise ChatTurnNotFoundError()
        self._assert_conversation_owner(
            self.conversation_repo.get_by_id(entity.conversation_id),
            doctor_id,
        )
        if conversation_id is not None and entity.conversation_id != conversation_id:
            raise ChatTurnNotFoundError()
        return entity

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

    def _prepare_tree_nodes(
        self,
        request,
        authority: _TurnAuthoritySnapshot,
    ) -> dict[str, str]:
        metadata = {
            "attachment_ids": list(authority.attachment_ids),
            "turn_configuration": {
                "protocol_version": authority.protocol_version,
                "agent_type": authority.agent_type,
                "attachment_scope": authority.attachment_scope,
                "research_options": authority.research_options,
            },
        }
        if request.attachment_only:
            metadata.update({
                "attachment_only": True,
                "implicit_prompt_id": request.implicit_prompt_id,
            })

        if request.operation in ("normal", "edit_resend"):
            first_message = (
                request.operation == "normal"
                and self.chat_persistence_service.is_first_message(
                    request.conversation_id
                )
            )
            initialize_first_question = (
                first_message
                and bool(request.message.strip())
                and not request.attachment_only
            )
            if initialize_first_question:
                metadata["conversation_first_question"] = True
            context = MessageContext(metadata=metadata)
            user, assistant = self.chat_persistence_service.create_turn(
                request.conversation_id,
                request.message,
                request.doctor_id,
                context=context,
                source_message_id=request.source_message_id,
                mode="edit" if request.operation == "edit_resend" else "normal",
                initialize_first_question=initialize_first_question,
            )
            return {
                "user_message_id": user.id,
                "assistant_message_id": assistant.id,
            }

        context = MessageContext(metadata=metadata)
        assistant = self.chat_persistence_service.create_assistant_regeneration(
            request.conversation_id,
            request.source_message_id,
            context=context,
        )
        return {
            "user_message_id": assistant.parent_id,
            "assistant_message_id": assistant.id,
        }

    def _resolve_turn_authority(
        self,
        request: PreparePlatformChatTurnRequest,
    ) -> _TurnAuthoritySnapshot:
        requested = self._snapshot_from_request(request)
        if request.operation == "normal":
            return requested

        source_user, source_turn = self._resolve_source_user_and_turn(request)
        context_snapshot = self._parse_source_user_snapshot(source_user.context)
        if context_snapshot is None or source_turn is None:
            raise SourceTurnAuthorityError()
        if (
            not isinstance(source_user.message_content, str)
            or (not bool(source_user.message_content))
            != context_snapshot.attachment_only
        ):
            raise SourceTurnAuthorityError()

        authoritative = _TurnAuthoritySnapshot(
            protocol_version=context_snapshot.protocol_version,
            agent_type=context_snapshot.agent_type,
            attachment_scope=context_snapshot.attachment_scope,
            patient_id=source_turn.patient_id,
            research_options=context_snapshot.research_options,
            attachment_ids=context_snapshot.attachment_ids,
            attachment_only=context_snapshot.attachment_only,
            implicit_prompt_id=context_snapshot.implicit_prompt_id,
        )
        if not self._source_turn_matches_snapshot(
            source_turn,
            authoritative,
            allow_failed=(
                request.operation == "regenerate"
                and source_turn.status == "failed"
            ),
        ):
            raise SourceTurnAuthorityError()
        if not self._same_turn_configuration(authoritative, requested):
            raise SourceTurnAuthorityError()
        # edit_resend 按定义会产生新正文；regenerate 则必须逐字复用源问题，
        # 并保持文字/纯附件模式与隐式提示三方一致。
        if request.operation == "regenerate" and (
            authoritative.attachment_only != requested.attachment_only
            or authoritative.implicit_prompt_id
            != requested.implicit_prompt_id
            or source_user.message_content != request.message
        ):
            raise SourceTurnAuthorityError()
        return authoritative

    def _resolve_source_user_and_turn(self, request):
        source = self.message_repo.get_by_id(request.source_message_id)

        if request.operation == "edit_resend":
            if not self._is_visible_success_message(
                source,
                request.conversation_id,
            ):
                raise SourceTurnAuthorityError()
            if (
                source.message_type != "user"
                or source.sender_id != request.doctor_id
            ):
                raise SourceTurnAuthorityError()
            source_user = source
            source_turn = self.turn_repo.get_origin_by_user_message_id_for_update(
                request.doctor_id,
                request.conversation_id,
                source_user.id,
            )
            if source_turn is not None:
                assistant = self.message_repo.get_by_id(
                    source_turn.assistant_message_id
                )
                if not self._is_visible_success_message(
                    assistant,
                    request.conversation_id,
                ) or assistant.parent_id != source_user.id:
                    raise SourceTurnAuthorityError()
            elif not any(
                self._is_visible_success_message(
                    child,
                    request.conversation_id,
                ) and child.message_type == "assistant"
                for child in self.message_repo.get_children(
                    request.conversation_id,
                    source_user.id,
                )
            ):
                raise SourceTurnAuthorityError()
            return source_user, source_turn

        if (
            source is None
            or source.chat_id != request.conversation_id
            or source.deleted
            or source.message_type != "assistant"
            or not source.parent_id
        ):
            raise SourceTurnAuthorityError()
        source_user = self.message_repo.get_by_id(source.parent_id)
        if not self._is_visible_success_message(
            source_user,
            request.conversation_id,
            request.doctor_id,
        ) or source_user.message_type != "user":
            raise SourceTurnAuthorityError()
        source_turn = self.turn_repo.get_by_assistant_message_id_for_update(
            request.doctor_id,
            request.conversation_id,
            source.id,
        )
        if (
            source_turn is None
            or source_turn.doctor_id != request.doctor_id
            or source_turn.conversation_id != request.conversation_id
            or source_turn.user_message_id != source_user.id
            or source_turn.assistant_message_id != source.id
            or source_turn.operation
            not in {"normal", "edit_resend", "regenerate"}
        ):
            raise SourceTurnAuthorityError()

        if source_turn.status == "completed":
            if (
                source.status != "success"
                or source_turn.error_code is not None
                or source.error_message is not None
            ):
                raise SourceTurnAuthorityError()
        elif source_turn.status == "failed":
            if (
                source.status != "failed"
                or not self._is_safe_source_turn_error_code(
                    source_turn.error_code
                )
                or source.error_message != source_turn.error_code
            ):
                raise SourceTurnAuthorityError()
        else:
            raise SourceTurnAuthorityError()
        return source_user, source_turn

    @staticmethod
    def _is_visible_success_message(
        message,
        conversation_id: str,
        doctor_id: Optional[str] = None,
    ) -> bool:
        return bool(
            message is not None
            and message.chat_id == conversation_id
            and message.status == "success"
            and not message.deleted
            and (doctor_id is None or message.sender_id == doctor_id)
        )

    @staticmethod
    def _is_safe_source_turn_error_code(value: Any) -> bool:
        return bool(
            isinstance(value, str)
            and _SAFE_SOURCE_TURN_ERROR_CODE.fullmatch(value)
        )

    @classmethod
    def _parse_source_user_snapshot(
        cls,
        raw_context: Optional[str],
    ) -> Optional[_TurnAuthoritySnapshot]:
        if raw_context is None:
            return None
        if not isinstance(raw_context, str) or not raw_context.strip():
            raise SourceTurnAuthorityError()
        try:
            context = json.loads(
                raw_context,
                object_pairs_hook=cls._strict_json_object,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            raise SourceTurnAuthorityError() from None
        if not isinstance(context, list) or not all(
            isinstance(item, dict) for item in context
        ):
            raise SourceTurnAuthorityError()
        metadata_entries = [
            item["metadata"] for item in context if "metadata" in item
        ]
        if not metadata_entries:
            return None
        if len(metadata_entries) != 1 or not isinstance(
            metadata_entries[0],
            dict,
        ):
            raise SourceTurnAuthorityError()
        metadata = metadata_entries[0]
        has_configuration = "turn_configuration" in metadata
        has_attachments = "attachment_ids" in metadata
        if not has_configuration and not has_attachments:
            return None
        if not has_configuration or not has_attachments:
            raise SourceTurnAuthorityError()
        if set(metadata) - {
            "turn_configuration",
            "attachment_ids",
            "attachment_only",
            "implicit_prompt_id",
            "conversation_first_question",
        }:
            raise SourceTurnAuthorityError()
        if (
            "conversation_first_question" in metadata
            and metadata["conversation_first_question"] is not True
        ):
            raise SourceTurnAuthorityError()

        has_attachment_only = "attachment_only" in metadata
        has_implicit_prompt = "implicit_prompt_id" in metadata
        if has_attachment_only != has_implicit_prompt:
            raise SourceTurnAuthorityError()
        if has_attachment_only and metadata["attachment_only"] is not True:
            raise SourceTurnAuthorityError()

        configuration = metadata["turn_configuration"]
        if not isinstance(configuration, dict) or set(configuration) != {
            "protocol_version",
            "agent_type",
            "attachment_scope",
            "research_options",
        }:
            raise SourceTurnAuthorityError()
        protocol_version = configuration["protocol_version"]
        agent_type = configuration["agent_type"]
        attachment_scope = configuration["attachment_scope"]
        research_options = configuration["research_options"]
        if type(protocol_version) is not int or protocol_version not in (1, 2):
            raise SourceTurnAuthorityError()
        if (agent_type, attachment_scope) not in {
            ("health", "patient"),
            ("research", "research"),
        }:
            raise SourceTurnAuthorityError()
        if protocol_version == 1 and (agent_type, attachment_scope) != (
            "health",
            "patient",
        ):
            raise SourceTurnAuthorityError()
        if agent_type == "health":
            if research_options is not None:
                raise SourceTurnAuthorityError()
            canonical_options = None
        else:
            if protocol_version != 2 or not isinstance(research_options, dict):
                raise SourceTurnAuthorityError()
            try:
                parsed_options = ResearchOptionsV2.model_validate(
                    research_options,
                    strict=True,
                )
            except (TypeError, ValueError, ValidationError):
                raise SourceTurnAuthorityError() from None
            canonical_options = parsed_options.model_dump(mode="json")
            if canonical_options != research_options:
                raise SourceTurnAuthorityError()

        if has_implicit_prompt:
            expected_prompt = (
                "research-document-analysis-v1"
                if agent_type == "research"
                else "attachment-analysis-v1"
            )
            if metadata["implicit_prompt_id"] != expected_prompt:
                raise SourceTurnAuthorityError()

        attachment_ids = metadata["attachment_ids"]
        if (
            not isinstance(attachment_ids, list)
            or not 1 <= len(attachment_ids) <= 4
            or not all(
                isinstance(item, str) and item.strip() == item and item
                for item in attachment_ids
            )
            or len(set(attachment_ids)) != len(attachment_ids)
        ):
            raise SourceTurnAuthorityError()
        return _TurnAuthoritySnapshot(
            protocol_version=protocol_version,
            agent_type=agent_type,
            attachment_scope=attachment_scope,
            patient_id=None,
            research_options=canonical_options,
            attachment_ids=tuple(attachment_ids),
            attachment_only=has_attachment_only,
            implicit_prompt_id=(
                metadata["implicit_prompt_id"]
                if has_implicit_prompt
                else None
            ),
        )

    @staticmethod
    def _strict_json_object(pairs):
        value = {}
        for key, item in pairs:
            if not isinstance(key, str) or key in value:
                raise SourceTurnAuthorityError()
            value[key] = item
        return value

    @staticmethod
    def _snapshot_from_request(
        request: PreparePlatformChatTurnRequest,
    ) -> _TurnAuthoritySnapshot:
        return _TurnAuthoritySnapshot(
            protocol_version=request.version,
            agent_type=request.agent_type or "health",
            attachment_scope=request.attachment_scope or "patient",
            patient_id=request.patient_id,
            research_options=(
                request.research_options.model_dump(mode="json")
                if request.research_options is not None
                else None
            ),
            attachment_ids=tuple(request.attachment_ids),
            attachment_only=request.attachment_only,
            implicit_prompt_id=request.implicit_prompt_id,
        )

    @staticmethod
    def _same_turn_configuration(
        source: _TurnAuthoritySnapshot,
        requested: _TurnAuthoritySnapshot,
    ) -> bool:
        return bool(
            source.protocol_version == requested.protocol_version
            and source.agent_type == requested.agent_type
            and source.attachment_scope == requested.attachment_scope
            and source.patient_id == requested.patient_id
            and source.research_options == requested.research_options
            and source.attachment_ids == requested.attachment_ids
        )

    @staticmethod
    def _source_turn_matches_snapshot(
        source_turn,
        snapshot: _TurnAuthoritySnapshot,
        *,
        allow_failed: bool = False,
    ) -> bool:
        try:
            return bool(
                (
                    (
                        source_turn.status == "completed"
                        and source_turn.error_code is None
                    )
                    or (
                        allow_failed
                        and source_turn.status == "failed"
                        and PlatformChatTurnService._is_safe_source_turn_error_code(
                            source_turn.error_code
                        )
                    )
                )
                and source_turn.protocol_version == snapshot.protocol_version
                and source_turn.agent_type == snapshot.agent_type
                and source_turn.attachment_scope == snapshot.attachment_scope
                and source_turn.patient_id == snapshot.patient_id
                and source_turn.research_options == snapshot.research_options
                and tuple(source_turn.attachment_ids) == snapshot.attachment_ids
                and source_turn.attachment_only == snapshot.attachment_only
                and source_turn.implicit_prompt_id
                == snapshot.implicit_prompt_id
                and (
                    snapshot.agent_type != "research"
                    or snapshot.patient_id is None
                )
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return False

    def _lock_conversation(self, conversation_id: str):
        lock_by_id = getattr(self.conversation_repo, "lock_by_id", None)
        if lock_by_id is not None:
            conversation = lock_by_id(conversation_id)
        else:
            conversation = self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise ValueError(f"会话不存在: {conversation_id}")
        return conversation

    @staticmethod
    def _assert_conversation_owner(conversation, doctor_id: str) -> None:
        if (
            conversation is None
            or getattr(conversation, "user_type", None) != "doctor"
            or getattr(conversation, "host_id", None) != doctor_id
        ):
            raise ChatTurnNotFoundError()

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
