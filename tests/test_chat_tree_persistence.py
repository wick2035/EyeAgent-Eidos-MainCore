import unittest
from datetime import datetime
from typing import cast

from application.services.chat_persistence_service import ChatPersistenceService
from domain.models.chat_entity import ChatMessageEntity
from infrastructure.database.mysql_connection import MySQLConnectionPool
from infrastructure.repositories.chat_repository_impl import (
    ChatConversationRepositoryImpl,
    ChatMessageRepositoryImpl,
)


class FakeConversationRepo:
    def __init__(self):
        self.updated_counts = []

    def update_summary_and_count(self, chat_id, summary, total_messages):
        self.updated_counts.append((chat_id, summary, total_messages))
        return True


class FakeMessageRepo:
    def __init__(self, anchor=None):
        self.anchor = anchor
        self.created = []

    def get_latest_order(self, chat_id):
        return 7

    def get_by_id(self, message_id):
        return self.anchor if self.anchor and self.anchor.id == message_id else None

    def create(self, message):
        self.created.append(message)
        return message

    def count_by_chat_id(self, chat_id):
        return len(self.created)


class FakeDb:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return 1


class ChatTreePersistenceTest(unittest.TestCase):
    def test_save_message_validates_parent_anchor_and_persists_parent_id(self):
        anchor = message_entity("anchor-1", chat_id="chat-1")
        message_repo = FakeMessageRepo(anchor=anchor)
        service = ChatPersistenceService(
            cast(ChatConversationRepositoryImpl, FakeConversationRepo()),
            cast(ChatMessageRepositoryImpl, message_repo),
        )

        message = service.save_message(
            chat_id="chat-1",
            role="assistant",
            content="answer",
            parent_anchor_id="anchor-1",
        )

        self.assertEqual("anchor-1", message.parent_id)
        self.assertEqual("anchor-1", message_repo.created[0].parent_id)

    def test_save_message_rejects_parent_anchor_from_other_chat(self):
        anchor = message_entity("anchor-1", chat_id="other-chat")
        service = ChatPersistenceService(
            cast(ChatConversationRepositoryImpl, FakeConversationRepo()),
            cast(ChatMessageRepositoryImpl, FakeMessageRepo(anchor=anchor)),
        )

        with self.assertRaises(ValueError):
            service.save_message(
                chat_id="chat-1",
                role="assistant",
                content="answer",
                parent_anchor_id="anchor-1",
            )

    def test_chat_message_entity_carries_siblings_group_id(self):
        message = message_entity("msg-1", siblings_group_id="siblings-group-1")

        self.assertEqual("siblings-group-1", message.siblings_group_id)

    def test_repository_maps_siblings_group_id_from_rows(self):
        repo = ChatMessageRepositoryImpl.__new__(ChatMessageRepositoryImpl)

        message = repo._row_to_entity(row("msg-1", siblings_group_id="siblings-group-1"))

        self.assertEqual("siblings-group-1", message.siblings_group_id)

    def test_repository_create_persists_siblings_group_id(self):
        repo = ChatMessageRepositoryImpl.__new__(ChatMessageRepositoryImpl)
        fake_db = FakeDb()
        repo.db = cast(MySQLConnectionPool, fake_db)
        message = message_entity("msg-1", siblings_group_id="siblings-group-1")

        repo.create(message)

        insert_sql, params = fake_db.calls[0]
        self.assertIn("siblings_group_id", insert_sql)
        self.assertIn("siblings-group-1", params)


def message_entity(message_id, chat_id="chat-1", siblings_group_id=None):
    return ChatMessageEntity(
        id=message_id,
        chat_id=chat_id,
        siblings_group_id=siblings_group_id,
        parent_id=None,
        message_order=1,
        message_content="hello",
        message_type="user",
        sender_id="doctor-1",
        context=None,
        token_used=None,
        status="success",
        error_message=None,
        create_time=datetime(2026, 1, 1),
        create_by="doctor-1",
        update_time=datetime(2026, 1, 1),
        update_by="doctor-1",
        deleted=False,
        version=1,
    )


def row(message_id, siblings_group_id=None):
    return {
        "id": message_id,
        "chat_id": "chat-1",
        "siblings_group_id": siblings_group_id,
        "parent_id": None,
        "message_order": 1,
        "message_content": "hello",
        "message_type": "user",
        "sender_id": "doctor-1",
        "context": None,
        "token_used": None,
        "status": "success",
        "error_message": None,
        "create_time": datetime(2026, 1, 1),
        "create_by": "doctor-1",
        "update_time": datetime(2026, 1, 1),
        "update_by": "doctor-1",
        "deleted": 0,
        "version": 1,
    }


if __name__ == "__main__":
    unittest.main()
