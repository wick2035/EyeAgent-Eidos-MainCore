import asyncio
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from application.services.chat_turn_watchdog import ChatTurnWatchdog
from domain.models.chat_turn_request import ChatTurnRequestEntity
from infrastructure.repositories.chat_turn_request_repository_impl import (
    ChatTurnRequestRepositoryImpl,
)


_NOW = datetime(2026, 7, 11, 12, 0, 0)


def _turn(
    *,
    request_id: str,
    status: str,
    create_time: datetime | None = None,
    deadline_at: datetime | None = None,
) -> ChatTurnRequestEntity:
    return ChatTurnRequestEntity(
        doctor_id="doctor-1",
        request_id=request_id,
        request_fingerprint="a" * 64,
        operation="normal",
        conversation_id=f"conversation-{request_id}",
        session_id=f"session-{request_id}",
        patient_id="patient-1",
        attachment_ids_json="[]",
        user_message_id=f"user-{request_id}",
        assistant_message_id=f"assistant-{request_id}",
        previous_active_node_id=f"previous-{request_id}",
        status=status,
        deadline_at=deadline_at,
        create_time=create_time or _NOW,
        update_time=create_time or _NOW,
    )


class _DB:
    def __init__(self):
        self.depth = 0
        self.transactions = 0

    @contextmanager
    def transaction(self):
        self.depth += 1
        self.transactions += 1
        try:
            yield
        finally:
            self.depth -= 1


class _TurnRepository:
    def __init__(self, turns, db):
        self.items = {(item.doctor_id, item.request_id): item for item in turns}
        self.db = db
        self.locked = []

    def list_stale(self, _now):
        return list(self.items.values())

    def get_for_update(self, doctor_id, request_id):
        if self.db.depth != 1:
            raise AssertionError("turn row lock must be acquired inside transaction")
        self.locked.append((doctor_id, request_id))
        return self.items.get((doctor_id, request_id))

    def compare_and_set_status(
        self,
        doctor_id,
        request_id,
        expected_status,
        new_status,
        error_code=None,
        **_kwargs,
    ):
        if self.db.depth != 1:
            raise AssertionError("turn CAS must run inside transaction")
        entity = self.items.get((doctor_id, request_id))
        expected = (
            {expected_status}
            if isinstance(expected_status, str)
            else set(expected_status)
        )
        if entity is None or entity.status not in expected:
            return False
        entity.status = new_status
        entity.error_code = error_code
        entity.update_time = _NOW
        return True


class _ConversationRepository:
    def __init__(self, conversations, db):
        self.items = {item.id: item for item in conversations}
        self.db = db
        self.locked = []
        self.cas_calls = []

    def lock_by_id(self, conversation_id):
        if self.db.depth != 1:
            raise AssertionError("conversation row lock must be inside transaction")
        self.locked.append(conversation_id)
        return self.items.get(conversation_id)

    def compare_and_set_active_node(
        self,
        conversation_id,
        expected_node_id,
        active_node_id,
    ):
        if self.db.depth != 1:
            raise AssertionError("active-node CAS must run inside transaction")
        self.cas_calls.append(
            (conversation_id, expected_node_id, active_node_id)
        )
        conversation = self.items[conversation_id]
        if conversation.active_node_id != expected_node_id:
            return False
        conversation.active_node_id = active_node_id
        return True


class _MessageRepository:
    def __init__(self, messages, db):
        self.items = {item.id: item for item in messages}
        self.db = db
        self.updates = []

    def update(self, message_id, updates):
        if self.db.depth != 1:
            raise AssertionError("message update must run inside turn transaction")
        self.updates.append((message_id, dict(updates)))
        message = self.items.get(message_id)
        if message is None:
            return False
        for key, value in updates.items():
            setattr(message, key, value)
        return True


def _message(message_id, status="success"):
    return SimpleNamespace(
        id=message_id,
        status=status,
        deleted=False,
        error_message=None,
    )


def _watchdog(*turns, active_overrides=None):
    db = _DB()
    active_overrides = active_overrides or {}
    conversations = [
        SimpleNamespace(
            id=item.conversation_id,
            active_node_id=active_overrides.get(
                item.conversation_id,
                item.assistant_message_id,
            ),
        )
        for item in turns
    ]
    messages = [
        message
        for item in turns
        for message in (
            _message(item.user_message_id),
            _message(
                item.assistant_message_id,
                "streaming" if item.status == "streaming" else "prepared",
            ),
        )
    ]
    turn_repo = _TurnRepository(turns, db)
    conversation_repo = _ConversationRepository(conversations, db)
    message_repo = _MessageRepository(messages, db)
    watchdog = ChatTurnWatchdog(
        db=db,
        turn_repo=turn_repo,
        conversation_repo=conversation_repo,
        message_repo=message_repo,
    )
    return watchdog, turn_repo, conversation_repo, message_repo, db


class ChatTurnWatchdogTest(unittest.TestCase):
    def test_prepared_turn_expires_after_ten_minutes(self):
        turn = _turn(
            request_id="prepared",
            status="prepared",
            create_time=_NOW - timedelta(minutes=10),
        )
        watchdog, _, conversations, messages, db = _watchdog(turn)

        result = watchdog.reconcile_once(_NOW)

        self.assertEqual(result.scanned, 1)
        self.assertEqual(result.prepared_cancelled, 1)
        self.assertEqual(result.streaming_failed, 0)
        self.assertEqual(turn.status, "cancelled")
        self.assertEqual(turn.error_code, "TURN_EXPIRED")
        self.assertTrue(messages.items[turn.user_message_id].deleted)
        self.assertTrue(messages.items[turn.assistant_message_id].deleted)
        self.assertEqual(messages.items[turn.user_message_id].status, "cancelled")
        self.assertEqual(
            messages.items[turn.assistant_message_id].status,
            "cancelled",
        )
        self.assertEqual(
            conversations.items[turn.conversation_id].active_node_id,
            turn.previous_active_node_id,
        )
        self.assertEqual(db.depth, 0)

    def test_streaming_turn_fails_at_deadline(self):
        turn = _turn(
            request_id="streaming",
            status="streaming",
            create_time=_NOW - timedelta(minutes=15),
            deadline_at=_NOW,
        )
        watchdog, _, conversations, messages, db = _watchdog(turn)

        result = watchdog.reconcile_once(_NOW)

        self.assertEqual(result.prepared_cancelled, 0)
        self.assertEqual(result.streaming_failed, 1)
        self.assertEqual(turn.status, "failed")
        self.assertEqual(turn.error_code, "ATTACHMENT_ANALYSIS_TIMEOUT")
        assistant = messages.items[turn.assistant_message_id]
        self.assertEqual(assistant.status, "failed")
        self.assertEqual(
            assistant.error_message,
            "ATTACHMENT_ANALYSIS_TIMEOUT",
        )
        self.assertFalse(messages.items[turn.user_message_id].deleted)
        self.assertEqual(
            conversations.items[turn.conversation_id].active_node_id,
            turn.assistant_message_id,
        )
        self.assertEqual(db.transactions, 1)
        self.assertEqual(db.depth, 0)

    def test_watchdog_does_not_overwrite_newer_active_node(self):
        turn = _turn(
            request_id="old-prepared",
            status="prepared",
            create_time=_NOW - timedelta(minutes=11),
        )
        newer_node = "assistant-newer"
        watchdog, _, conversations, messages, _ = _watchdog(
            turn,
            active_overrides={turn.conversation_id: newer_node},
        )

        result = watchdog.reconcile_once(_NOW)

        self.assertEqual(result.prepared_cancelled, 1)
        self.assertEqual(
            conversations.items[turn.conversation_id].active_node_id,
            newer_node,
        )
        self.assertTrue(messages.items[turn.assistant_message_id].deleted)

    def test_watchdog_does_not_overwrite_existing_terminal_state(self):
        turn = _turn(
            request_id="completed",
            status="completed",
            create_time=_NOW - timedelta(hours=1),
            deadline_at=_NOW - timedelta(minutes=30),
        )
        watchdog, _, conversations, messages, _ = _watchdog(turn)

        result = watchdog.reconcile_once(_NOW)

        self.assertEqual(result.prepared_cancelled, 0)
        self.assertEqual(result.streaming_failed, 0)
        self.assertEqual(turn.status, "completed")
        self.assertFalse(messages.items[turn.assistant_message_id].deleted)
        self.assertEqual(
            conversations.items[turn.conversation_id].active_node_id,
            turn.assistant_message_id,
        )

    def test_poisoned_candidate_does_not_block_later_expired_turn(self):
        poison = _turn(
            request_id="sensitive-poison-record",
            status="streaming",
            create_time=_NOW - timedelta(minutes=20),
            deadline_at=_NOW - timedelta(minutes=5),
        )
        healthy = _turn(
            request_id="healthy-streaming",
            status="streaming",
            create_time=_NOW - timedelta(minutes=20),
            deadline_at=_NOW,
        )
        watchdog, _, conversations, messages, db = _watchdog(poison, healthy)
        del conversations.items[poison.conversation_id]

        with self.assertLogs(
            "application.services.chat_turn_watchdog",
            level="ERROR",
        ) as captured:
            try:
                result = watchdog.reconcile_once(_NOW)
            except Exception as error:
                self.fail(f"poisoned candidate escaped reconciliation: {error!r}")

        self.assertEqual(result.scanned, 2)
        self.assertEqual(result.streaming_failed, 1)
        self.assertEqual(poison.status, "streaming")
        self.assertEqual(healthy.status, "failed")
        self.assertEqual(
            messages.items[healthy.assistant_message_id].error_message,
            "ATTACHMENT_ANALYSIS_TIMEOUT",
        )
        self.assertEqual(db.transactions, 2)
        self.assertEqual(db.depth, 0)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("RuntimeError", captured.output[0])
        self.assertNotIn(poison.request_id, captured.output[0])
        self.assertNotIn(poison.conversation_id, captured.output[0])

    def test_prepared_turn_younger_than_ten_minutes_is_unchanged(self):
        turn = _turn(
            request_id="fresh",
            status="prepared",
            create_time=_NOW - timedelta(minutes=9, seconds=59),
        )
        watchdog, _, _, messages, _ = _watchdog(turn)

        result = watchdog.reconcile_once(_NOW)

        self.assertEqual(result.prepared_cancelled, 0)
        self.assertEqual(turn.status, "prepared")
        self.assertFalse(messages.items[turn.assistant_message_id].deleted)


class ChatTurnWatchdogRepositoryTest(unittest.TestCase):
    def test_stale_query_covers_prepared_age_and_streaming_deadline(self):
        class RecordingDB:
            def __init__(self):
                self.sql = None
                self.params = None

            def fetch_all(self, sql, params):
                self.sql = " ".join(sql.split())
                self.params = params
                return []

        db = RecordingDB()
        repository = ChatTurnRequestRepositoryImpl(db=db)

        repository.list_stale(_NOW)

        self.assertIn("status = 'prepared'", db.sql)
        self.assertIn("create_time <= %s", db.sql)
        self.assertIn("status = 'streaming'", db.sql)
        self.assertIn("deadline_at <= %s", db.sql)
        self.assertEqual(db.params, (_NOW - timedelta(minutes=10), _NOW))


class ChatTurnWatchdogLifespanTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_exits_promptly_after_stop_signal(self):
        watchdog, *_ = _watchdog()
        watchdog._interval_seconds = 60
        stop = asyncio.Event()
        task = asyncio.create_task(watchdog.run(stop))
        await asyncio.sleep(0)

        stop.set()
        await asyncio.wait_for(task, timeout=1)

        self.assertTrue(task.done())

    async def test_lifespan_starts_and_stops_watchdog(self):
        import main

        class FakeWatchdog:
            def __init__(self):
                self.started = asyncio.Event()
                self.stopped = asyncio.Event()
                self.stop_signal = None

            async def run(self, stop):
                self.stop_signal = stop
                self.started.set()
                await stop.wait()
                self.stopped.set()

        watchdog = FakeWatchdog()
        before = set(asyncio.all_tasks())

        with (
            patch.object(main, "get_db_connection", return_value=object()),
            patch.object(main, "close_db_connection") as close_db,
            patch.object(main, "get_chat_turn_watchdog", return_value=watchdog),
        ):
            async with main.lifespan(SimpleNamespace()):
                await asyncio.wait_for(watchdog.started.wait(), timeout=1)
                self.assertFalse(watchdog.stop_signal.is_set())
                self.assertFalse(watchdog.stopped.is_set())

        self.assertTrue(watchdog.stop_signal.is_set())
        self.assertTrue(watchdog.stopped.is_set())
        self.assertEqual(set(asyncio.all_tasks()), before)
        close_db.assert_called_once_with()

    async def test_lifespan_still_stops_watchdog_and_closes_db_on_app_error(self):
        import main

        class FakeWatchdog:
            def __init__(self):
                self.stopped = asyncio.Event()

            async def run(self, stop):
                await stop.wait()
                self.stopped.set()

        watchdog = FakeWatchdog()
        with (
            patch.object(main, "get_db_connection", return_value=object()),
            patch.object(main, "close_db_connection") as close_db,
            patch.object(main, "get_chat_turn_watchdog", return_value=watchdog),
        ):
            with self.assertRaisesRegex(RuntimeError, "app failed"):
                async with main.lifespan(SimpleNamespace()):
                    await asyncio.sleep(0)
                    raise RuntimeError("app failed")

        self.assertTrue(watchdog.stopped.is_set())
        close_db.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
