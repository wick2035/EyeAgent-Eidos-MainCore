import json
import copy
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from application.services.chat_persistence_service import ChatPersistenceService
from application.services.chat_turn_fingerprint import fingerprint_turn
from application.services.conversation_activity_guard import (
    ConversationActivityGuard,
    ConversationBusyError,
)
from application.services.platform_chat_turn_service import (
    ChatTurnNotFoundError,
    PlatformChatTurnService,
    RequestIdempotencyConflictError,
    TurnAlreadyCompletedError,
)
from domain.models.chat_entity import ChatConversationEntity, ChatMessageEntity
from domain.models.chat_turn_request import ChatTurnRequestEntity
from infrastructure.repositories.chat_turn_request_repository_impl import (
    ChatTurnRequestRepositoryImpl,
    DuplicateChatTurnRequestError,
)
from presentation.schemas.platform_chat_turn_schemas import (
    PreparePlatformChatTurnRequest,
    ResearchOptionsV2,
)


class FakeDB:
    @contextmanager
    def transaction(self):
        yield


class SnapshotFakeDB:
    def __init__(self):
        self.repositories = ()
        self.depth = 0
        self.rollback_calls = 0

    def bind(self, *repositories):
        self.repositories = repositories

    @contextmanager
    def transaction(self):
        if self.depth:
            self.depth += 1
            try:
                yield
            finally:
                self.depth -= 1
            return

        snapshots = [copy.deepcopy(repo.items) for repo in self.repositories]
        self.depth = 1
        try:
            yield
        except Exception:
            for repository, snapshot in zip(self.repositories, snapshots):
                repository.items = snapshot
            self.rollback_calls += 1
            raise
        finally:
            self.depth = 0


class RecordingDB:
    def __init__(self):
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params
        return 1


class FakeConversationRepository:
    def __init__(self):
        self.items = {}
        self.title_updates = []
        self._lock = threading.Lock()
        self.fail_active_node_update = False
        self.lock_calls = []

    def create(self, conversation):
        self.items[conversation.id] = conversation
        return conversation

    def get_by_id(self, conversation_id):
        return self.items.get(conversation_id)

    def lock_by_id(self, conversation_id):
        self.lock_calls.append(conversation_id)
        return self.get_by_id(conversation_id)

    def update_active_node(self, conversation_id, active_node_id):
        if self.fail_active_node_update:
            return False
        with self._lock:
            self.items[conversation_id].active_node_id = active_node_id
        return True

    def compare_and_set_active_node(self, conversation_id, expected_node_id, active_node_id):
        with self._lock:
            conversation = self.items[conversation_id]
            if conversation.active_node_id != expected_node_id:
                return False
            conversation.active_node_id = active_node_id
            return True

    def update_title(self, conversation_id, title):
        self.title_updates.append((conversation_id, title))
        self.items[conversation_id].title = title
        return True

    def update_summary_and_count(self, conversation_id, summary, total_messages):
        self.items[conversation_id].summary = summary
        self.items[conversation_id].total_messages = total_messages
        return True


class FakeMessageRepository:
    def __init__(self):
        self.items = {}
        self._lock = threading.Lock()

    def create(self, message):
        with self._lock:
            self.items[message.id] = message
        return message

    def get_by_id(self, message_id):
        return self.items.get(message_id)

    def update(self, message_id, updates):
        with self._lock:
            message = self.items[message_id]
            for key, value in updates.items():
                setattr(message, key, value)
            message.update_time = datetime.now()
        return True

    def get_by_chat_id(self, chat_id, limit=100, offset=0):
        values = [
            message
            for message in self.items.values()
            if message.chat_id == chat_id and not message.deleted
        ]
        return sorted(values, key=lambda message: message.message_order)[offset:offset + limit]

    def get_by_ids(self, chat_id, ids):
        return [
            self.items[message_id]
            for message_id in ids
            if message_id in self.items
            and self.items[message_id].chat_id == chat_id
            and not self.items[message_id].deleted
        ]

    def get_children(self, chat_id, parent_id):
        return sorted(
            [
                message
                for message in self.items.values()
                if message.chat_id == chat_id
                and message.parent_id == parent_id
                and not message.deleted
            ],
            key=lambda message: message.message_order,
        )

    def get_latest_order(self, chat_id):
        with self._lock:
            return max(
                (
                    message.message_order
                    for message in self.items.values()
                    if message.chat_id == chat_id and not message.deleted
                ),
                default=0,
            )

    def count_by_chat_id(self, chat_id):
        return len([
            message
            for message in self.items.values()
            if message.chat_id == chat_id
            and message.message_type != "root"
            and not message.deleted
        ])

    def get_active_assistant_for_conversation(self, conversation_id):
        active = [
            message
            for message in self.items.values()
            if message.chat_id == conversation_id
            and message.message_type == "assistant"
            and message.status in ("running", "streaming")
            and not message.deleted
        ]
        return max(active, key=lambda message: message.message_order, default=None)


class FakeChatTurnRequestRepository:
    def __init__(self):
        self.items = {}
        self.insert_barrier = None
        self._lock = threading.Lock()

    def get_for_update(self, doctor_id, request_id):
        with self._lock:
            return self.items.get((doctor_id, request_id))

    def insert(self, entity):
        if self.insert_barrier is not None:
            self.insert_barrier.wait(timeout=5)
        key = (entity.doctor_id, entity.request_id)
        with self._lock:
            if key in self.items:
                raise DuplicateChatTurnRequestError(entity.doctor_id, entity.request_id)
            if any(
                item.assistant_message_id == entity.assistant_message_id
                for item in self.items.values()
            ):
                raise DuplicateChatTurnRequestError(entity.doctor_id, entity.request_id)
            self.items[key] = entity
        return entity

    def compare_and_set_status(
        self,
        doctor_id,
        request_id,
        expected_status,
        new_status,
        error_code=None,
        execute_started_at=None,
        deadline_at=None,
    ):
        expected = {expected_status} if isinstance(expected_status, str) else set(expected_status)
        with self._lock:
            entity = self.items.get((doctor_id, request_id))
            if entity is None or entity.status not in expected:
                return False
            entity.status = new_status
            entity.error_code = error_code
            if execute_started_at is not None:
                entity.execute_started_at = execute_started_at
            if deadline_at is not None:
                entity.deadline_at = deadline_at
            entity.update_time = datetime.now()
            return True

    def get_active_for_conversation(self, conversation_id, ignore_request_id=None):
        with self._lock:
            active = [
                entity
                for entity in self.items.values()
                if entity.conversation_id == conversation_id
                and entity.status in ("prepared", "streaming")
                and entity.request_id != ignore_request_id
            ]
            return max(active, key=lambda entity: entity.create_time, default=None)

    def list_stale(self, now=None):
        now = now or datetime.now()
        with self._lock:
            return [
                entity
                for entity in self.items.values()
                if (
                    entity.status in ("prepared", "streaming")
                    and entity.deadline_at is not None
                    and entity.deadline_at <= now
                )
            ]


class PlatformChatTurnServiceTest(unittest.TestCase):
    def test_prepare_rejects_conversation_owned_by_other_doctor(self):
        self.conversation_repo.get_by_id("conversation-1").host_id = "doctor-2"

        with self.assertRaises(ChatTurnNotFoundError):
            self.service.prepare(self._request())

        self.assertIsNone(self._stored_turn())

    def setUp(self):
        self.db = FakeDB()
        self.conversation_repo = FakeConversationRepository()
        self.message_repo = FakeMessageRepository()
        self.turn_repo = FakeChatTurnRequestRepository()
        self.guard = ConversationActivityGuard(self.turn_repo, self.message_repo)
        self.chat_service = ChatPersistenceService(
            self.conversation_repo,
            self.message_repo,
            db=self.db,
            activity_guard=self.guard,
        )
        self.service = PlatformChatTurnService(
            db=self.db,
            turn_repo=self.turn_repo,
            conversation_repo=self.conversation_repo,
            message_repo=self.message_repo,
            chat_persistence_service=self.chat_service,
            activity_guard=self.guard,
        )
        self.root_ids = {}
        self._create_conversation("conversation-1")

    def _create_conversation(self, conversation_id):
        now = datetime.now()
        root_id = f"root-{conversation_id}"
        conversation = ChatConversationEntity(
            id=conversation_id,
            user_type="doctor",
            host_id="doctor-1",
            title="新对话",
            active_node_id=root_id,
            create_time=now,
            update_time=now,
        )
        root = ChatMessageEntity(
            id=root_id,
            chat_id=conversation_id,
            parent_id=None,
            siblings_group_id=None,
            message_order=1,
            message_content="",
            message_type="root",
            status="success",
            create_time=now,
            update_time=now,
        )
        self.conversation_repo.create(conversation)
        self.message_repo.create(root)
        self.root_ids[conversation_id] = root_id

    def _request(
        self,
        request_id="request-1",
        conversation_id="conversation-1",
        message="请分析",
        operation="normal",
        source_message_id=None,
        attachment_ids=None,
        implicit_prompt_id=None,
    ):
        attachment_ids = attachment_ids or ["attachment-1"]
        fingerprint = fingerprint_turn(
            version=1,
            operation=operation,
            conversation_id=conversation_id,
            session_id=f"session-{conversation_id}",
            patient_id="patient-1",
            message=message,
            source_message_id=source_message_id,
            implicit_prompt_id=implicit_prompt_id,
            attachment_ids=attachment_ids,
        )
        return PreparePlatformChatTurnRequest(
            version=1,
            request_id=request_id,
            request_fingerprint=fingerprint,
            operation=operation,
            conversation_id=conversation_id,
            session_id=f"session-{conversation_id}",
            patient_id="patient-1",
            doctor_id="doctor-1",
            message=message,
            source_message_id=source_message_id,
            implicit_prompt_id=implicit_prompt_id,
            attachment_ids=attachment_ids,
        )

    def _research_request(self):
        research_options = ResearchOptionsV2(
            enable_institution_data=True,
            enable_web_search=True,
            types=["scholar", "general", "general"],
        )
        payload = {
            "version": 2,
            "request_id": "request-research",
            "operation": "normal",
            "conversation_id": "conversation-1",
            "session_id": "session-conversation-1",
            "patient_id": None,
            "doctor_id": "doctor-1",
            "agent_type": "research",
            "attachment_scope": "research",
            "research_options": research_options,
            "message": "",
            "source_message_id": None,
            "implicit_prompt_id": "research-document-analysis-v1",
            "attachment_ids": ["attachment-1"],
        }
        payload["request_fingerprint"] = fingerprint_turn(
            version=payload["version"],
            operation=payload["operation"],
            conversation_id=payload["conversation_id"],
            session_id=payload["session_id"],
            patient_id=payload["patient_id"],
            message=payload["message"],
            source_message_id=payload["source_message_id"],
            implicit_prompt_id=payload["implicit_prompt_id"],
            attachment_ids=payload["attachment_ids"],
            agent_type=payload["agent_type"],
            attachment_scope=payload["attachment_scope"],
            research_options=research_options,
        )
        return PreparePlatformChatTurnRequest(**payload)

    def _seed_completed_legacy_turn(self):
        user, assistant = self.chat_service.create_turn(
            "conversation-1",
            "旧问题",
            "doctor-1",
        )
        self.message_repo.update(assistant.id, {"status": "success"})
        return user, assistant

    def _stored_turn(self, request_id="request-1"):
        return self.turn_repo.get_for_update("doctor-1", request_id)

    def test_prepare_normal_is_idempotent_for_same_fingerprint(self):
        request = self._request()

        first = self.service.prepare(request)
        second = self.service.prepare(request)

        self.assertEqual(first, second)
        self.assertEqual(first.status, "prepared")
        visible = self.message_repo.get_by_chat_id("conversation-1")
        self.assertEqual(len([item for item in visible if item.message_type == "user"]), 1)
        self.assertEqual(len([item for item in visible if item.message_type == "assistant"]), 1)
        self.assertEqual(len(self.turn_repo.items), 1)

    def test_prepare_persists_authoritative_v2_research_snapshot(self):
        self.service.prepare(self._research_request())

        turn = self._stored_turn("request-research")
        self.assertEqual(turn.protocol_version, 2)
        self.assertEqual(turn.agent_type, "research")
        self.assertEqual(turn.attachment_scope, "research")
        self.assertIsNone(turn.patient_id)
        self.assertEqual(
            turn.research_options,
            {
                "enable_institution_data": True,
                "enable_web_search": True,
                "types": ["general", "scholar"],
            },
        )

    def test_prepare_maps_v1_to_health_patient_snapshot(self):
        self.service.prepare(self._request())

        turn = self._stored_turn()
        self.assertEqual(turn.protocol_version, 1)
        self.assertEqual(turn.agent_type, "health")
        self.assertEqual(turn.attachment_scope, "patient")
        self.assertIsNone(turn.research_options)

    def test_prepare_rejects_same_request_with_different_fingerprint(self):
        self.service.prepare(self._request(message="第一次"))

        with self.assertRaisesRegex(
            RequestIdempotencyConflictError,
            "REQUEST_IDEMPOTENCY_CONFLICT",
        ):
            self.service.prepare(self._request(message="第二次"))

        self.assertEqual(len(self.turn_repo.items), 1)

    def test_concurrent_same_request_across_different_conversations_reloads_winner(self):
        self._create_conversation("conversation-2")
        self.turn_repo.insert_barrier = threading.Barrier(2)
        requests = [
            self._request(conversation_id="conversation-1"),
            self._request(conversation_id="conversation-2"),
        ]

        def prepare(request):
            try:
                return self.service.prepare(request)
            except Exception as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(prepare, requests))

        successes = [result for result in results if not isinstance(result, Exception)]
        conflicts = [
            result
            for result in results
            if isinstance(result, RequestIdempotencyConflictError)
        ]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(str(conflicts[0]), "REQUEST_IDEMPOTENCY_CONFLICT")
        self.assertEqual(len(self.turn_repo.items), 1)

    def test_prepare_edit_creates_user_sibling_and_assistant_child(self):
        original_user, _ = self._seed_completed_legacy_turn()
        request = self._request(
            operation="edit_resend",
            source_message_id=original_user.id,
            message="新问题",
        )

        self.service.prepare(request)

        turn = self._stored_turn()
        edited_user = self.message_repo.get_by_id(turn.user_message_id)
        edited_assistant = self.message_repo.get_by_id(turn.assistant_message_id)
        self.assertEqual(edited_user.parent_id, original_user.parent_id)
        self.assertEqual(edited_user.siblings_group_id, original_user.siblings_group_id)
        self.assertEqual(edited_assistant.parent_id, edited_user.id)

    def test_prepare_regenerate_reuses_parent_user_and_only_creates_assistant(self):
        original_user, original_assistant = self._seed_completed_legacy_turn()
        user_count_before = len([
            item for item in self.message_repo.items.values() if item.message_type == "user"
        ])
        request = self._request(
            operation="regenerate",
            source_message_id=original_assistant.id,
        )

        self.service.prepare(request)

        turn = self._stored_turn()
        regenerated = self.message_repo.get_by_id(turn.assistant_message_id)
        user_count_after = len([
            item for item in self.message_repo.items.values() if item.message_type == "user"
        ])
        self.assertEqual(turn.user_message_id, original_user.id)
        self.assertEqual(regenerated.parent_id, original_user.id)
        self.assertEqual(user_count_after, user_count_before)

    def test_prepare_rejects_when_legacy_text_turn_is_streaming(self):
        _, assistant = self.chat_service.create_turn(
            "conversation-1",
            "仍在生成",
            "doctor-1",
        )
        self.assertEqual(assistant.status, "streaming")

        with self.assertRaisesRegex(ConversationBusyError, "CONVERSATION_BUSY"):
            self.service.prepare(self._request())

    def test_legacy_text_turn_rejects_when_attachment_turn_is_active(self):
        self.service.prepare(self._request())

        with self.assertRaisesRegex(ConversationBusyError, "CONVERSATION_BUSY"):
            self.chat_service.create_turn(
                "conversation-1",
                "另一条纯文本消息",
                "doctor-1",
            )

    def test_abort_prepared_hides_nodes_and_restores_active_node_with_cas(self):
        self.service.prepare(self._request())
        turn = self._stored_turn()

        response = self.service.abort("doctor-1", "request-1")

        self.assertEqual(response.status, "cancelled")
        self.assertEqual(turn.status, "cancelled")
        self.assertTrue(self.message_repo.items[turn.user_message_id].deleted)
        self.assertTrue(self.message_repo.items[turn.assistant_message_id].deleted)
        self.assertEqual(
            self.conversation_repo.get_by_id("conversation-1").active_node_id,
            self.root_ids["conversation-1"],
        )

    def test_cancel_streaming_preserves_user_message(self):
        self.service.prepare(self._request())
        turn = self._stored_turn()
        self.turn_repo.compare_and_set_status(
            "doctor-1",
            "request-1",
            "prepared",
            "streaming",
        )

        self.service.abort("doctor-1", "request-1")

        user = self.message_repo.items[turn.user_message_id]
        assistant = self.message_repo.items[turn.assistant_message_id]
        self.assertEqual(turn.status, "cancelled")
        self.assertFalse(user.deleted)
        self.assertEqual(user.status, "success")
        self.assertFalse(assistant.deleted)
        self.assertEqual(assistant.status, "cancelled")

    def test_older_abort_cannot_overwrite_newer_active_node(self):
        self.service.prepare(self._request())
        turn = self._stored_turn()
        newer_node_id = str(uuid.uuid4())
        self.message_repo.create(ChatMessageEntity(
            id=newer_node_id,
            chat_id="conversation-1",
            parent_id=turn.assistant_message_id,
            siblings_group_id=None,
            message_order=99,
            message_content="newer",
            message_type="assistant",
            status="success",
        ))
        self.conversation_repo.update_active_node("conversation-1", newer_node_id)

        self.service.abort("doctor-1", "request-1")

        self.assertEqual(
            self.conversation_repo.get_by_id("conversation-1").active_node_id,
            newer_node_id,
        )

    def test_pure_attachment_persists_empty_body_and_implicit_prompt_metadata(self):
        request = self._request(
            message="",
            attachment_ids=["attachment-b", "attachment-a"],
            implicit_prompt_id="attachment-analysis-v1",
        )

        self.service.prepare(request)

        turn = self._stored_turn()
        user = self.message_repo.get_by_id(turn.user_message_id)
        metadata = next(
            item["metadata"]
            for item in json.loads(user.context)
            if "metadata" in item
        )
        self.assertEqual(user.message_content, "")
        self.assertEqual(metadata["attachment_only"], True)
        self.assertEqual(metadata["implicit_prompt_id"], "attachment-analysis-v1")
        self.assertEqual(metadata["attachment_ids"], ["attachment-b", "attachment-a"])
        self.assertEqual(turn.attachment_ids, ["attachment-b", "attachment-a"])

    def test_empty_first_message_does_not_update_conversation_title(self):
        request = self._request(
            message="",
            implicit_prompt_id="attachment-analysis-v1",
        )

        self.service.prepare(request)

        self.assertEqual(self.conversation_repo.title_updates, [])
        self.assertEqual(
            self.conversation_repo.get_by_id("conversation-1").title,
            "新对话",
        )

    def test_status_and_mark_completed_project_persisted_turn(self):
        self.service.prepare(self._request())
        turn = self._stored_turn()
        self.turn_repo.compare_and_set_status(
            "doctor-1",
            "request-1",
            "prepared",
            "streaming",
        )

        completed = self.service.mark_completed("doctor-1", "request-1")
        repeated = self.service.mark_completed("doctor-1", "request-1")

        self.assertEqual(completed.status, "completed")
        self.assertEqual(repeated.status, "completed")
        self.assertEqual(completed.user_message_id, turn.user_message_id)
        self.assertEqual(completed.assistant_message_id, turn.assistant_message_id)
        self.assertEqual(
            self.service.status("doctor-1", "request-1").status,
            "completed",
        )
        with self.assertRaisesRegex(TurnAlreadyCompletedError, "TURN_ALREADY_COMPLETED"):
            self.service.abort("doctor-1", "request-1")

    def test_mark_failed_updates_turn_and_assistant(self):
        self.service.prepare(self._request())
        turn = self._stored_turn()
        self.turn_repo.compare_and_set_status(
            "doctor-1",
            "request-1",
            "prepared",
            "streaming",
        )

        failed = self.service.mark_failed(
            "doctor-1",
            "request-1",
            "ATTACHMENT_ANALYSIS_FAILED",
        )

        assistant = self.message_repo.get_by_id(turn.assistant_message_id)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error_code, "ATTACHMENT_ANALYSIS_FAILED")
        self.assertEqual(assistant.status, "failed")
        self.assertEqual(assistant.error_message, "ATTACHMENT_ANALYSIS_FAILED")

    def test_abort_cancelled_turn_is_idempotent(self):
        self.service.prepare(self._request())

        first = self.service.abort("doctor-1", "request-1")
        second = self.service.abort("doctor-1", "request-1")

        self.assertEqual(first, second)

    def test_prepare_active_node_failure_rolls_back_messages_and_turn(self):
        db = SnapshotFakeDB()
        conversation_repo = FakeConversationRepository()
        message_repo = FakeMessageRepository()
        turn_repo = FakeChatTurnRequestRepository()
        db.bind(conversation_repo, message_repo, turn_repo)
        guard = ConversationActivityGuard(turn_repo, message_repo)
        chat_service = ChatPersistenceService(
            conversation_repo,
            message_repo,
            db=db,
            activity_guard=guard,
        )
        service = PlatformChatTurnService(
            db=db,
            turn_repo=turn_repo,
            conversation_repo=conversation_repo,
            message_repo=message_repo,
            chat_persistence_service=chat_service,
            activity_guard=guard,
        )
        now = datetime.now()
        conversation_repo.create(ChatConversationEntity(
            id="conversation-1",
            user_type="doctor",
            host_id="doctor-1",
            title="新对话",
            active_node_id="root-1",
            create_time=now,
            update_time=now,
        ))
        message_repo.create(ChatMessageEntity(
            id="root-1",
            chat_id="conversation-1",
            parent_id=None,
            siblings_group_id=None,
            message_order=1,
            message_content="",
            message_type="root",
            status="success",
            create_time=now,
            update_time=now,
        ))
        conversation_repo.fail_active_node_update = True

        with self.assertRaisesRegex(RuntimeError, "active_node_id"):
            service.prepare(self._request())

        self.assertEqual(
            [item.message_type for item in message_repo.items.values()],
            ["root"],
        )
        self.assertEqual(turn_repo.items, {})
        self.assertEqual(conversation_repo.items["conversation-1"].active_node_id, "root-1")
        self.assertEqual(db.rollback_calls, 1)

    def test_expired_prepared_turn_repairs_tree_and_allows_next_prepare(self):
        self.service.prepare(self._request())
        expired = self._stored_turn()
        now = datetime.now()
        expired.deadline_at = now

        self.assertEqual(self.service.expire_stale_turns(now), 1)

        self.assertEqual(expired.status, "cancelled")
        self.assertEqual(expired.error_code, "TURN_EXPIRED")
        self.assertTrue(self.message_repo.items[expired.user_message_id].deleted)
        self.assertTrue(self.message_repo.items[expired.assistant_message_id].deleted)
        self.assertEqual(
            self.conversation_repo.get_by_id("conversation-1").active_node_id,
            self.root_ids["conversation-1"],
        )
        prepared = self.service.prepare(self._request(request_id="request-2"))
        self.assertEqual(prepared.status, "prepared")
        self.assertGreaterEqual(
            self.conversation_repo.lock_calls.count("conversation-1"),
            2,
        )

    def test_expired_streaming_turn_cancels_assistant_and_unblocks_conversation(self):
        self.service.prepare(self._request())
        expired = self._stored_turn()
        self.turn_repo.compare_and_set_status(
            "doctor-1", "request-1", "prepared", "streaming"
        )
        now = datetime.now()
        expired.deadline_at = now

        self.assertEqual(self.service.expire_stale_turns(now), 1)

        user = self.message_repo.items[expired.user_message_id]
        assistant = self.message_repo.items[expired.assistant_message_id]
        self.assertEqual(expired.status, "cancelled")
        self.assertEqual(expired.error_code, "TURN_EXPIRED")
        self.assertFalse(user.deleted)
        self.assertEqual(assistant.status, "cancelled")
        self.assertEqual(assistant.error_message, "TURN_EXPIRED")
        self.assertEqual(
            self.service.prepare(self._request(request_id="request-2")).status,
            "prepared",
        )

    def test_expired_old_prepared_turn_does_not_replace_newer_active_node(self):
        self.service.prepare(self._request())
        expired = self._stored_turn()
        now = datetime.now()
        expired.deadline_at = now
        newer_node_id = str(uuid.uuid4())
        self.message_repo.create(ChatMessageEntity(
            id=newer_node_id,
            chat_id="conversation-1",
            parent_id=expired.assistant_message_id,
            siblings_group_id=None,
            message_order=99,
            message_content="newer",
            message_type="assistant",
            status="success",
        ))
        self.conversation_repo.update_active_node("conversation-1", newer_node_id)

        self.service.expire_stale_turns(now)
        self.service.abort("doctor-1", "request-1")

        self.assertEqual(
            self.conversation_repo.get_by_id("conversation-1").active_node_id,
            newer_node_id,
        )


class ChatTurnRequestRepositoryTest(unittest.TestCase):
    def test_table_scripts_define_v2_snapshot_columns_and_nullable_patient(self):
        project_root = Path(__file__).resolve().parents[1]
        create_sql = (
            project_root / "scripts/create_chat_turn_request_table.sql"
        ).read_text(encoding="utf-8")
        upgrade_path = (
            project_root / "scripts/upgrade_chat_turn_request_v2_research.sql"
        )
        self.assertTrue(upgrade_path.exists())
        upgrade_sql = upgrade_path.read_text(encoding="utf-8")

        for column in (
            "protocol_version",
            "agent_type",
            "attachment_scope",
            "research_options_json",
        ):
            with self.subTest(column=column):
                self.assertIn(column, create_sql)
                self.assertIn(column, upgrade_sql)
        self.assertIn("patient_id VARCHAR(36) NULL", create_sql)
        self.assertIn("MODIFY COLUMN patient_id VARCHAR(36) NULL", upgrade_sql)

    def test_insert_persists_v2_snapshot_columns(self):
        db = RecordingDB()
        repository = ChatTurnRequestRepositoryImpl(db)
        entity = ChatTurnRequestEntity(
            doctor_id="doctor-1",
            request_id="request-1",
            request_fingerprint="a" * 64,
            protocol_version=2,
            agent_type="research",
            attachment_scope="research",
            research_options_json=(
                '{"enable_institution_data":true,'
                '"enable_web_search":true,"types":["general"]}'
            ),
            operation="normal",
            conversation_id="conversation-1",
            session_id="session-1",
            patient_id=None,
            attachment_ids_json='["attachment-1"]',
            user_message_id="user-1",
            assistant_message_id="assistant-1",
        )

        repository.insert(entity)

        normalized_sql = " ".join(db.sql.split())
        self.assertIn(
            "protocol_version, agent_type, attachment_scope, research_options_json",
            normalized_sql,
        )
        self.assertIn(
            (2, "research", "research", entity.research_options_json),
            tuple(
                db.params[index:index + 4]
                for index in range(len(db.params) - 3)
            ),
        )

    def test_compare_and_set_status_puts_expected_statuses_in_where(self):
        db = RecordingDB()
        repository = ChatTurnRequestRepositoryImpl(db)

        changed = repository.compare_and_set_status(
            "doctor-1",
            "request-1",
            ("prepared", "streaming"),
            "cancelled",
        )

        normalized_sql = " ".join(db.sql.split())
        self.assertTrue(changed)
        self.assertIn("status IN (%s, %s)", normalized_sql)
        self.assertEqual(
            db.params[-4:],
            ("doctor-1", "request-1", "prepared", "streaming"),
        )


if __name__ == "__main__":
    unittest.main()
