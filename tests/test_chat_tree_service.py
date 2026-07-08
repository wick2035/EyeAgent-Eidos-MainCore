import unittest
import uuid
from datetime import datetime

from domain.models.chat_entity import ChatConversationEntity, ChatMessageEntity
from application.services.chat_persistence_service import ChatPersistenceService


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

    def test_regenerate_creates_assistant_sibling_under_same_user(self):
        service, _, _ = self.make_service()
        chat_id = service.create_conversation("doctor-1", "doctor", "新对话")
        user, assistant = service.create_turn(chat_id, "问题", "doctor-1")

        regenerated = service.create_assistant_regeneration(chat_id, assistant.id)

        self.assertEqual(regenerated.parent_id, user.id)
        self.assertEqual(regenerated.siblings_group_id, assistant.siblings_group_id)
        self.assertNotEqual(regenerated.id, assistant.id)


if __name__ == "__main__":
    unittest.main()
