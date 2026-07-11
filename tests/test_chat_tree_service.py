import unittest
import uuid
import json
import warnings
from contextvars import copy_context
from datetime import datetime

from domain.models.chat_entity import ChatConversationEntity, ChatMessageEntity, MessageContext
from application.services.chat_persistence_service import (
    ChatPersistenceService,
    LegacyBranchSourceInvalidError,
)
from application.services.legacy_text_turn_authority import (
    build_legacy_text_turn_authority,
)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from agents.graph.mysql_persistence_adapter import MySQLPersistenceAdapter


RESEARCH_TURN_CONFIGURATION = {
    "protocol_version": 2,
    "agent_type": "research",
    "attachment_scope": "research",
    "research_options": {
        "enable_institution_data": True,
        "enable_web_search": True,
        "types": ["general", "pubmed"],
    },
}


def research_text_context() -> MessageContext:
    return MessageContext(
        metadata={
            "agent_type": "research",
            "patient_id": None,
            "turn_configuration": RESEARCH_TURN_CONFIGURATION,
            "attachment_ids": [],
        },
    )


class ChatTreeEntityTest(unittest.TestCase):
    def test_entities_expose_tree_fields(self):
        conv = ChatConversationEntity(
            id="c1",
            user_type="doctor",
            host_id="doctor-1",
            title="新对话",
            active_node_id="root-1",
        )
        msg = ChatMessageEntity(
            id="u1",
            chat_id="c1",
            parent_id="root-1",
            siblings_group_id="sg-user-root-1",
            message_order=2,
            message_content="眼睛干涩",
            message_type="user",
            create_time=datetime.now(),
            update_time=datetime.now(),
        )

        self.assertEqual(conv.active_node_id, "root-1")
        self.assertEqual(msg.parent_id, "root-1")
        self.assertEqual(msg.siblings_group_id, "sg-user-root-1")


class FakeConversationRepo:
    def __init__(self):
        self.items = {}

    def create(self, conversation):
        self.items[conversation.id] = conversation
        return conversation

    def get_by_id(self, conversation_id):
        return self.items.get(conversation_id)

    def update_active_node(self, conversation_id, active_node_id):
        self.items[conversation_id].active_node_id = active_node_id
        return True

    def update_title(self, conversation_id, title):
        self.items[conversation_id].title = title
        return True

    def update_summary_and_count(self, conversation_id, summary, total_messages):
        self.items[conversation_id].summary = summary
        self.items[conversation_id].total_messages = total_messages
        return True


class FakeMessageRepo:
    def __init__(self):
        self.items = {}

    def create(self, message):
        self.items[message.id] = message
        return message

    def get_by_id(self, message_id):
        return self.items.get(message_id)

    def update(self, message_id, updates):
        msg = self.items[message_id]
        for key, value in updates.items():
            setattr(msg, key, value)
        return True

    def get_by_chat_id(self, chat_id, limit=100, offset=0):
        values = [m for m in self.items.values() if m.chat_id == chat_id and not m.deleted]
        return sorted(values, key=lambda m: m.message_order)

    def get_by_ids(self, chat_id, ids):
        return [self.items[mid] for mid in ids if mid in self.items and self.items[mid].chat_id == chat_id]

    def get_children(self, chat_id, parent_id):
        values = [
            m for m in self.items.values()
            if m.chat_id == chat_id and m.parent_id == parent_id and not m.deleted
        ]
        return sorted(values, key=lambda m: m.message_order)

    def get_latest_order(self, chat_id):
        values = [m.message_order for m in self.items.values() if m.chat_id == chat_id]
        return max(values, default=0)

    def get_latest_sibling_order(self, chat_id, parent_id, message_type):
        values = [
            m.message_order for m in self.items.values()
            if m.chat_id == chat_id and m.parent_id == parent_id and m.message_type == message_type
        ]
        return max(values, default=0)

    def count_by_chat_id(self, chat_id):
        return len([m for m in self.items.values() if m.chat_id == chat_id and m.message_type != "root"])


class ChatTreeServiceTest(unittest.TestCase):
    def make_service(self):
        conv_repo = FakeConversationRepo()
        msg_repo = FakeMessageRepo()
        return ChatPersistenceService(conv_repo, msg_repo), conv_repo, msg_repo

    def test_create_conversation_creates_root_and_sets_active_node(self):
        service, conv_repo, msg_repo = self.make_service()

        chat_id = service.create_conversation("doctor-1", "doctor", "新对话")

        conv = conv_repo.get_by_id(chat_id)
        roots = [m for m in msg_repo.items.values() if m.chat_id == chat_id and m.message_type == "root"]
        self.assertEqual(len(roots), 1)
        self.assertEqual(conv.active_node_id, roots[0].id)
        self.assertTrue(service.is_first_message(chat_id))

    def test_normal_turn_appends_user_under_active_leaf_and_assistant_under_user(self):
        service, conv_repo, _ = self.make_service()
        chat_id = service.create_conversation("doctor-1", "doctor", "新对话")
        root_id = conv_repo.get_by_id(chat_id).active_node_id

        user, assistant = service.create_turn(chat_id, "眼睛干涩", "doctor-1")

        self.assertEqual(user.parent_id, root_id)
        self.assertEqual(assistant.parent_id, user.id)
        self.assertEqual(conv_repo.get_by_id(chat_id).active_node_id, assistant.id)

    def test_normal_turn_bootstraps_root_for_external_empty_conversation(self):
        service, conv_repo, msg_repo = self.make_service()
        now = datetime.now()
        conversation = ChatConversationEntity(
            id="external-chat",
            user_type="doctor",
            host_id="doctor-1",
            title="新对话",
            total_messages=0,
            active_node_id=None,
            create_time=now,
            update_time=now,
        )
        conv_repo.create(conversation)

        user, assistant = service.create_turn("external-chat", "第一条问题", "doctor-1")

        roots = [
            m for m in msg_repo.items.values()
            if m.chat_id == "external-chat" and m.message_type == "root"
        ]
        self.assertEqual(len(roots), 1)
        self.assertEqual(user.parent_id, roots[0].id)
        self.assertEqual(assistant.parent_id, user.id)
        self.assertEqual(conv_repo.get_by_id("external-chat").active_node_id, assistant.id)

    def test_sibling_group_id_fits_db_uuid_column(self):
        service, _, _ = self.make_service()
        parent_id = "12345678-1234-1234-1234-123456789012"

        group_id = service._sibling_group_id(parent_id, "assistant")

        self.assertLessEqual(len(group_id), 36)
        self.assertEqual(str(uuid.UUID(group_id)), group_id)
        self.assertEqual(group_id, service._sibling_group_id(parent_id, "assistant"))
        self.assertNotEqual(group_id, service._sibling_group_id(parent_id, "user"))

    def test_edit_resend_creates_user_sibling_under_original_parent(self):
        service, _, _ = self.make_service()
        chat_id = service.create_conversation("doctor-1", "doctor", "新对话")
        original_user, original_assistant = service.create_turn(chat_id, "旧问题", "doctor-1")

        edited_user, edited_assistant = service.create_turn(
            chat_id,
            "新问题",
            "doctor-1",
            source_message_id=original_user.id,
            mode="edit",
        )

        self.assertEqual(edited_user.parent_id, original_user.parent_id)
        self.assertEqual(edited_user.siblings_group_id, original_user.siblings_group_id)
        self.assertEqual(edited_assistant.parent_id, edited_user.id)
        self.assertNotEqual(edited_assistant.id, original_assistant.id)

    def test_invalid_edit_parent_never_reaches_real_write_path(self):
        service, conv_repo, msg_repo = self.make_service()
        chat_id = service.create_conversation("doctor-1", "doctor", "科研对话")
        source, _assistant = service.create_turn(
            chat_id,
            "原问题",
            "doctor-1",
            context=research_text_context(),
        )
        source.parent_id = "foreign-or-missing-parent"
        before_count = len(msg_repo.items)
        before_active = conv_repo.get_by_id(chat_id).active_node_id

        try:
            service.assert_legacy_branch_authority(
                chat_id=chat_id,
                source_message_id=source.id,
                branch_mode="edit",
                doctor_id="doctor-1",
                agent_type="research",
                patient_id=None,
            )
        except LegacyBranchSourceInvalidError:
            pass
        else:
            service.create_turn(
                chat_id,
                "篡改后的问题",
                "doctor-1",
                context=research_text_context(),
                source_message_id=source.id,
                mode="edit",
            )

        self.assertEqual(len(msg_repo.items), before_count)
        self.assertEqual(
            conv_repo.get_by_id(chat_id).active_node_id,
            before_active,
        )

    def test_edit_authority_accepts_successful_assistant_parent_on_active_path(self):
        service, _, _ = self.make_service()
        chat_id = service.create_conversation("doctor-1", "doctor", "科研对话")
        context = research_text_context()
        _first_user, first_assistant = service.create_turn(
            chat_id,
            "第一问",
            "doctor-1",
            context=context,
        )
        first_assistant.status = "success"
        source, active_assistant = service.create_turn(
            chat_id,
            "第二问",
            "doctor-1",
            context=context,
        )
        active_assistant.status = "success"

        configuration = service.assert_legacy_branch_authority(
            chat_id=chat_id,
            source_message_id=source.id,
            branch_mode="edit",
            doctor_id="doctor-1",
            agent_type="research",
            patient_id=None,
        )

        self.assertEqual(
            configuration.to_turn_configuration(),
            RESEARCH_TURN_CONFIGURATION,
        )

    def test_branch_authority_rejects_research_option_drift(self):
        service, _, _ = self.make_service()
        chat_id = service.create_conversation(
            "doctor-1",
            "doctor",
            "科研对话",
        )
        source, assistant = service.create_turn(
            chat_id,
            "原问题",
            "doctor-1",
            context=research_text_context(),
        )
        assistant.status = "success"
        context = json.loads(source.context)
        metadata = next(
            item["metadata"]
            for item in context
            if "metadata" in item
        )
        metadata["turn_configuration"]["research_options"][
            "types"
        ] = ["pubmed", "general"]
        source.context = json.dumps(context)

        with self.assertRaises(LegacyBranchSourceInvalidError):
            service.assert_legacy_branch_authority(
                chat_id=chat_id,
                source_message_id=source.id,
                branch_mode="edit",
                doctor_id="doctor-1",
                agent_type="research",
                patient_id=None,
            )

    def test_branch_authority_rejects_empty_text_source(self):
        service, _, _ = self.make_service()
        chat_id = service.create_conversation(
            "doctor-1",
            "doctor",
            "科研对话",
        )
        source, assistant = service.create_turn(
            chat_id,
            "   ",
            "doctor-1",
            context=research_text_context(),
        )
        assistant.status = "success"

        with self.assertRaises(LegacyBranchSourceInvalidError):
            service.assert_legacy_branch_authority(
                chat_id=chat_id,
                source_message_id=source.id,
                branch_mode="edit",
                doctor_id="doctor-1",
                agent_type="research",
                patient_id=None,
            )

    def test_atomic_edit_revalidates_active_path_before_write(self):
        service, conv_repo, msg_repo = self.make_service()
        chat_id = service.create_conversation(
            "doctor-1",
            "doctor",
            "科研对话",
        )
        root_id = conv_repo.get_by_id(chat_id).active_node_id
        source, assistant = service.create_turn(
            chat_id,
            "原问题",
            "doctor-1",
            context=research_text_context(),
        )
        assistant.status = "success"
        authority = service.assert_legacy_branch_authority(
            chat_id=chat_id,
            source_message_id=source.id,
            branch_mode="edit",
            doctor_id="doctor-1",
            agent_type="research",
            patient_id=None,
        )
        before_count = len(msg_repo.items)

        conv_repo.get_by_id(chat_id).active_node_id = root_id

        with self.assertRaises(LegacyBranchSourceInvalidError):
            service.create_legacy_edit_turn(
                chat_id=chat_id,
                source_message_id=source.id,
                content="编辑后的问题",
                sender_id="doctor-1",
                context=research_text_context(),
                expected_authority=authority,
            )

        self.assertEqual(len(msg_repo.items), before_count)
        self.assertEqual(
            conv_repo.get_by_id(chat_id).active_node_id,
            root_id,
        )

    def test_atomic_regenerate_rejects_authority_drift_before_write(self):
        service, conv_repo, msg_repo = self.make_service()
        chat_id = service.create_conversation(
            "doctor-1",
            "doctor",
            "科研对话",
        )
        source, assistant = service.create_turn(
            chat_id,
            "原问题",
            "doctor-1",
            context=research_text_context(),
        )
        assistant.status = "success"
        authority = service.assert_legacy_branch_authority(
            chat_id=chat_id,
            source_message_id=assistant.id,
            branch_mode="regenerate",
            doctor_id="doctor-1",
            agent_type="research",
            patient_id=None,
        )
        source.context = MessageContext(
            metadata=build_legacy_text_turn_authority(
                agent_type="research",
                patient_id=None,
                enable_institution_data=False,
                enable_web_search=False,
                web_search_types=[],
            ).to_message_metadata(),
        ).to_json()
        before_count = len(msg_repo.items)
        before_active = conv_repo.get_by_id(chat_id).active_node_id

        with self.assertRaises(LegacyBranchSourceInvalidError):
            service.create_legacy_assistant_regeneration(
                chat_id=chat_id,
                source_assistant_id=assistant.id,
                doctor_id="doctor-1",
                expected_authority=authority,
            )

        self.assertEqual(len(msg_repo.items), before_count)
        self.assertEqual(
            conv_repo.get_by_id(chat_id).active_node_id,
            before_active,
        )

    def test_regenerate_creates_assistant_sibling_under_same_user(self):
        service, _, _ = self.make_service()
        chat_id = service.create_conversation("doctor-1", "doctor", "新对话")
        user, assistant = service.create_turn(chat_id, "问题", "doctor-1")

        regenerated = service.create_assistant_regeneration(chat_id, assistant.id)

        self.assertEqual(regenerated.parent_id, user.id)
        self.assertEqual(regenerated.siblings_group_id, assistant.siblings_group_id)
        self.assertNotEqual(regenerated.id, assistant.id)

    def test_unknown_turn_mode_is_rejected(self):
        service, _, _ = self.make_service()
        chat_id = service.create_conversation("doctor-1", "doctor", "新对话")

        with self.assertRaises(ValueError):
            service.create_turn(chat_id, "问题", "doctor-1", mode="unknown")


class FakeTreeService:
    def __init__(self):
        self.turns = []
        self.regenerate_context = None
        self.title_updates = []
        self._counter = 0

    def create_turn(self, chat_id, content, sender_id, context=None, source_message_id=None, mode="normal"):
        self._counter += 1
        user = ChatMessageEntity(
            id=f"user-{self._counter}",
            chat_id=chat_id,
            parent_id="root-1",
            siblings_group_id="sg:root-1:user",
            message_order=self._counter * 2,
            message_content=content,
            message_type="user",
            sender_id=sender_id,
        )
        assistant = ChatMessageEntity(
            id=f"assistant-{self._counter}",
            chat_id=chat_id,
            parent_id=user.id,
            siblings_group_id=f"sg:{user.id}:assistant",
            message_order=self._counter * 2 + 1,
            message_content="",
            message_type="assistant",
            status="streaming",
        )
        self.turns.append((user, assistant, context, source_message_id, mode))
        return user, assistant

    def create_assistant_regeneration(self, chat_id, source_assistant_id, context=None):
        self.regenerate_context = context
        return ChatMessageEntity(
            id="assistant-regenerated",
            chat_id=chat_id,
            parent_id="user-1",
            siblings_group_id="sg:user-1:assistant",
            message_order=10,
            message_content="",
            message_type="assistant",
            status="streaming",
        )

    def create_legacy_edit_turn(self, **kwargs):
        return self.create_turn(
            kwargs["chat_id"],
            kwargs["content"],
            kwargs["sender_id"],
            context=kwargs.get("context"),
            source_message_id=kwargs["source_message_id"],
            mode="edit",
        )

    def create_legacy_assistant_regeneration(self, **kwargs):
        return self.create_assistant_regeneration(
            kwargs["chat_id"],
            kwargs["source_assistant_id"],
            context=kwargs.get("context"),
        )

    def update_conversation_title(self, chat_id, first_message):
        self.title_updates.append((chat_id, first_message))
        return True


class MySQLPersistenceAdapterTreeTest(unittest.TestCase):
    def test_user_context_persists_canonical_agent_and_patient_binding(self):
        service = FakeTreeService()
        adapter = MySQLPersistenceAdapter(service)

        adapter.prepare_normal_turn(
            "chat-1",
            "科研问题",
            "doctor-1",
            {
                "stage": "research",
                "agent_type": "research",
                "patient_id": None,
                "turn_configuration": RESEARCH_TURN_CONFIGURATION,
                "attachment_ids": [],
            },
        )

        context = service.turns[0][2]
        self.assertIsInstance(context, MessageContext)
        self.assertEqual(
            context.metadata,
            {
                "agent_type": "research",
                "patient_id": None,
                "turn_configuration": RESEARCH_TURN_CONFIGURATION,
                "attachment_ids": [],
            },
        )

    def test_empty_first_message_does_not_update_conversation_title(self):
        service = FakeTreeService()
        adapter = MySQLPersistenceAdapter(service)

        adapter.prepare_normal_turn(
            "chat-1",
            "",
            "doctor-1",
            is_first_message=True,
        )

        self.assertEqual(service.title_updates, [])

    def test_two_step_bridge_keeps_pending_assistant_ids_per_execution_context(self):
        adapter = MySQLPersistenceAdapter(FakeTreeService())
        ctx1 = copy_context()
        ctx2 = copy_context()

        first_user_id = ctx1.run(
            adapter.save_user_message,
            "chat-1",
            "第一条",
            "doctor-1",
            {"stage": "greeting", "agent_type": "health"},
            True,
        )
        second_user_id = ctx2.run(
            adapter.save_user_message,
            "chat-1",
            "第二条",
            "doctor-1",
            {"stage": "health", "agent_type": "health"},
            False,
        )

        self.assertEqual(first_user_id, "user-1")
        self.assertEqual(second_user_id, "user-2")
        self.assertEqual(ctx1.run(adapter.create_assistant_placeholder, "chat-1"), "assistant-1")
        self.assertEqual(ctx2.run(adapter.create_assistant_placeholder, "chat-1"), "assistant-2")

    def test_prepare_regenerate_turn_passes_context_to_service(self):
        service = FakeTreeService()
        adapter = MySQLPersistenceAdapter(service)
        authority = build_legacy_text_turn_authority(
            agent_type="health",
            patient_id="patient-1",
        )

        ids = adapter.prepare_regenerate_turn(
            "chat-1",
            "assistant-1",
            {"stage": "health", "agent_type": "recommendation"},
            doctor_id="doctor-1",
            expected_authority=authority,
        )

        self.assertEqual(ids["assistant_message_id"], "assistant-regenerated")
        self.assertIsInstance(service.regenerate_context, MessageContext)
        context_json = json.loads(service.regenerate_context.to_json())
        self.assertIn({"conversation_stage": "health"}, context_json)
        self.assertIn({"metadata": {"agent_type": "recommendation"}}, context_json)


if __name__ == "__main__":
    unittest.main()
