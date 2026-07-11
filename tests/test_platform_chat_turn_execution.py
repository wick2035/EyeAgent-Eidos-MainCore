import asyncio
import json
import threading
import unittest
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from types import SimpleNamespace

from agents.graph_manager import PreparedGraphTerminal
from application.services.chat_turn_execution_registry import (
    ChatTurnExecutionRegistry,
)
from application.services.platform_attachment_analyzer import (
    AttachmentStatusUpdate,
)
from application.services.platform_chat_turn_execution_service import (
    ATTACHMENT_EXECUTE_MISMATCH,
    PlatformChatTurnExecutionService,
)
from domain.models.chat_turn_request import ChatTurnRequestEntity
from domain.security.principal import CurrentPrincipal
from infrastructure.attachments.config import (
    AllowedAttachmentEndpoint,
    AttachmentDownloadSettings,
)
from presentation.schemas.platform_chat_turn_schemas import (
    ExecutePlatformChatTurnRequest,
)
from utils.transient_attachment_context import (
    AttachmentAnalysis,
    get_attachment_analysis,
)


class FakeDB:
    def __init__(self):
        self.depth = 0
        self.commits = 0

    @contextmanager
    def transaction(self):
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1
            if self.depth == 0:
                self.commits += 1


class FakeTurnRepository:
    def __init__(self, turns):
        self.items = {(turn.doctor_id, turn.request_id): turn for turn in turns}
        self._lock = threading.Lock()

    def get(self, doctor_id, request_id):
        return self.items.get((doctor_id, request_id))

    def get_for_update(self, doctor_id, request_id):
        return self.get(doctor_id, request_id)

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
            turn = self.get(doctor_id, request_id)
            if turn is None or turn.status not in expected:
                return False
            turn.status = new_status
            turn.error_code = error_code
            turn.execute_started_at = execute_started_at or turn.execute_started_at
            turn.deadline_at = deadline_at or turn.deadline_at
            turn.update_time = datetime.now()
            return True


class FakeMessageRepository:
    def __init__(self, messages):
        self.items = {message.id: message for message in messages}
        self.create_calls = 0

    def get_by_id(self, message_id):
        return self.items.get(message_id)

    def update(self, message_id, updates):
        message = self.items.get(message_id)
        if message is None:
            return False
        for key, value in updates.items():
            setattr(message, key, value)
        return True

    def get_by_chat_id(self, chat_id, limit=100, offset=0):
        return [
            item
            for item in self.items.values()
            if item.chat_id == chat_id and not getattr(item, "deleted", False)
        ][offset:offset + limit]

    def count_by_chat_id(self, chat_id):
        return len(self.get_by_chat_id(chat_id))


class FakeConversationRepository:
    def __init__(self, conversations):
        self.items = {item.id: item for item in conversations}

    def get_by_id(self, conversation_id):
        return self.items.get(conversation_id)

    def lock_by_id(self, conversation_id):
        return self.get_by_id(conversation_id)

    def update_summary_and_count(self, conversation_id, summary, total_messages):
        conversation = self.get_by_id(conversation_id)
        conversation.summary = summary
        conversation.total_messages = total_messages
        return True


class FakeDownloader:
    def __init__(self, settings):
        self._settings = settings

    @asynccontextmanager
    async def download_all(self, descriptors, request_id):
        yield list(descriptors)


class FakeAnalyzer:
    def __init__(self, *, fail=False):
        self.fail = fail

    async def analyze_all(self, downloaded, on_status):
        analyses = []
        for item in downloaded:
            await on_status(AttachmentStatusUpdate(item.attachment_id, "processing"))
            if self.fail:
                await on_status(
                    AttachmentStatusUpdate(
                        item.attachment_id,
                        "failed",
                        "ATTACHMENT_ANALYSIS_FAILED",
                    )
                )
                error = RuntimeError("sensitive parser detail")
                error.error_code = "ATTACHMENT_ANALYSIS_FAILED"
                raise error
            await on_status(AttachmentStatusUpdate(item.attachment_id, "ready"))
            analyses.append(
                AttachmentAnalysis(
                    attachment_id=item.attachment_id,
                    untrusted_text=f"private-{item.attachment_id}",
                )
            )
        return analyses


class BlockingAnalyzer:
    async def analyze_all(self, downloaded, on_status):
        await on_status(
            AttachmentStatusUpdate(downloaded[0].attachment_id, "processing")
        )
        await asyncio.Event().wait()


class FakeGraphManager:
    def __init__(
        self,
        *,
        fail=False,
        pause=False,
        tool_results=None,
        citations=None,
    ):
        self.fail = fail
        self.pause = pause
        self.tool_results = tool_results or []
        self.citations = citations or []
        self.calls = []
        self.contexts = []
        self.closed = 0

    async def chat_stream_prepared_async(self, **kwargs):
        try:
            self.calls.append(kwargs)
            self.contexts.append(get_attachment_analysis(kwargs["runnable_config"]))
            if self.fail:
                raise RuntimeError("private graph failure")
            yield {"type": "token", "content": f"answer-{kwargs['user_message_id']}"}
            if self.pause:
                await asyncio.Event().wait()
            yield PreparedGraphTerminal(
                content=f"answer-{kwargs['user_message_id']}",
                token_used=7,
                tool_results=self.tool_results,
                citations=self.citations,
                agent_type="health",
                stage="collecting_info",
            )
        finally:
            self.closed += 1


def principal(doctor_id="doctor-1"):
    return CurrentPrincipal(
        issuer="java",
        subject=doctor_id,
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=frozenset({"ai:chat"}),
        institution_id="inst-1",
        tenant_id="tenant-1",
        authorized_party="eye-agent-platform",
        schema_version=1,
        token_id="jwt-1",
        issued_at=1,
        not_before=1,
        expires_at=9999999999,
    )


def execute_request(request_id="request-1", **overrides):
    payload = {
        "request_id": request_id,
        "request_fingerprint": "a" * 64,
        "conversation_id": f"conversation-{request_id}",
        "session_id": f"session-{request_id}",
        "patient_id": f"patient-{request_id}",
        "doctor_id": "doctor-1",
        "user_message_id": f"user-{request_id}",
        "assistant_message_id": f"assistant-{request_id}",
        "attachments": [
            {
                "attachment_id": f"attachment-{request_id}",
                "file_type": "image",
                "filename": "fundus.png",
                "mime_type": "image/png",
                "size_bytes": 128,
                "page_count": None,
                "content_sha256": "b" * 64,
                "document_version": 2,
                "analysis_attempt_id": f"attempt-{request_id}",
                "download_url": "https://storage.example/file",
            }
        ],
    }
    payload.update(overrides)
    return ExecutePlatformChatTurnRequest(**payload)


def turn_for(request):
    return ChatTurnRequestEntity(
        doctor_id=request.doctor_id,
        request_id=request.request_id,
        request_fingerprint=request.request_fingerprint,
        operation="normal",
        conversation_id=request.conversation_id,
        session_id=request.session_id,
        patient_id=request.patient_id,
        implicit_prompt_id=None,
        attachment_ids_json=json.dumps(
            [item.attachment_id for item in request.attachments]
        ),
        user_message_id=request.user_message_id,
        assistant_message_id=request.assistant_message_id,
        status="prepared",
    )


def messages_for(request):
    user = SimpleNamespace(
        id=request.user_message_id,
        chat_id=request.conversation_id,
        message_type="user",
        message_content="请分析附件",
        parent_id="root",
        status="success",
    )
    assistant = SimpleNamespace(
        id=request.assistant_message_id,
        chat_id=request.conversation_id,
        message_type="assistant",
        message_content="",
        parent_id=request.user_message_id,
        status="streaming",
        error_message=None,
    )
    return user, assistant


def make_service(
    requests,
    *,
    analyzer=None,
    graph=None,
    heartbeat_interval=30.0,
):
    turns = [turn_for(item) for item in requests]
    all_messages = [message for item in requests for message in messages_for(item)]
    conversations = [
        SimpleNamespace(
            id=item.conversation_id,
            host_id=item.doctor_id,
            user_type="doctor",
            active_node_id=item.assistant_message_id,
        )
        for item in requests
    ]
    settings = AttachmentDownloadSettings(
        endpoints=(
            AllowedAttachmentEndpoint(
                scheme="https",
                host="storage.example",
                port=443,
                ip="203.0.113.10",
            ),
        )
    )
    db = FakeDB()
    turn_repo = FakeTurnRepository(turns)
    message_repo = FakeMessageRepository(all_messages)
    graph = graph or FakeGraphManager()
    service = PlatformChatTurnExecutionService(
        db=db,
        turn_repo=turn_repo,
        conversation_repo=FakeConversationRepository(conversations),
        message_repo=message_repo,
        downloader=FakeDownloader(settings),
        analyzer=analyzer or FakeAnalyzer(),
        graph_manager=graph,
        registry=ChatTurnExecutionRegistry(),
        download_settings=settings,
        heartbeat_interval=heartbeat_interval,
    )
    return service, turn_repo, message_repo, graph, db


async def collect(generator):
    return [event async for event in generator]


class PlatformChatTurnExecutionContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_execute_mismatch_keeps_turn_prepared(self):
        prepared = execute_request()
        service, turns, _, graph, _ = make_service([prepared])
        mismatched = prepared.model_copy(update={"patient_id": "other-patient"})

        events = await collect(service.stream(mismatched, principal()))

        self.assertEqual(events[-1]["error_code"], ATTACHMENT_EXECUTE_MISMATCH)
        self.assertEqual(turns.get("doctor-1", "request-1").status, "prepared")
        self.assertEqual(graph.calls, [])

    async def test_only_one_concurrent_execute_wins_prepared_to_streaming_cas(self):
        request = execute_request()
        service, turns, _, _, _ = make_service([request])

        first, second = await asyncio.gather(
            collect(service.stream(request, principal())),
            collect(service.stream(request, principal())),
        )

        terminal_codes = [
            events[-1].get("error_code")
            for events in (first, second)
        ]
        self.assertEqual(terminal_codes.count("TURN_EXECUTION_CONFLICT"), 1)
        self.assertEqual(turns.get("doctor-1", request.request_id).status, "completed")

    async def test_execute_uses_prepared_ids_without_creating_messages(self):
        request = execute_request()
        service, _, messages, graph, _ = make_service([request])

        events = await collect(service.stream(request, principal()))

        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(events[0]["event"], "execution_started")
        self.assertFalse(any(event["event"] == "start" for event in events))
        self.assertEqual(messages.create_calls, 0)
        self.assertEqual(graph.calls[0]["user_message_id"], request.user_message_id)
        self.assertEqual(graph.calls[0]["assistant_message_id"], request.assistant_message_id)

    async def test_internal_sse_events_do_not_expose_attachment_transport_fields(self):
        request = execute_request()
        service, _, _, _, _ = make_service([request])

        events = await collect(service.stream(request, principal()))
        captured_sse = "\n\n".join(
            f"data: {json.dumps(event, ensure_ascii=False)}" for event in events
        )

        self.assertIn('"event": "execution_started"', captured_sse)
        for forbidden in (
            "download_url",
            "base64",
            "page_images",
            "storage_key",
            "untrusted_text",
            "https://storage.example/file",
        ):
            self.assertNotIn(forbidden, captured_sse)

    async def test_any_attachment_failure_emits_zero_answer_tokens(self):
        request = execute_request()
        service, turns, _, graph, _ = make_service(
            [request], analyzer=FakeAnalyzer(fail=True)
        )

        events = await collect(service.stream(request, principal()))

        self.assertFalse(any(event["event"] == "token" for event in events))
        self.assertEqual(graph.calls, [])
        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(turns.get("doctor-1", request.request_id).status, "failed")

    async def test_disconnect_finalizes_turn_and_assistant_cancelled(self):
        request = execute_request()
        service, turns, messages, graph, _ = make_service(
            [request], analyzer=BlockingAnalyzer()
        )
        stream = service.stream(request, principal())
        await stream.__anext__()
        await stream.__anext__()
        waiting = asyncio.create_task(stream.__anext__())
        await asyncio.sleep(0)
        waiting.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiting

        self.assertEqual(turns.get("doctor-1", request.request_id).status, "cancelled")
        self.assertEqual(messages.get_by_id(request.assistant_message_id).status, "cancelled")
        self.assertEqual(graph.closed, 0)

    async def test_aclose_finalizes_turn_and_assistant_cancelled(self):
        request = execute_request()
        service, turns, messages, _, _ = make_service([request])
        stream = service.stream(request, principal())

        await stream.__anext__()
        await stream.aclose()

        self.assertEqual(turns.get("doctor-1", request.request_id).status, "cancelled")
        self.assertEqual(messages.get_by_id(request.assistant_message_id).status, "cancelled")

    async def test_aclose_explicitly_closes_prepared_graph_generator(self):
        request = execute_request()
        graph = FakeGraphManager(pause=True)
        service, turns, _, graph, _ = make_service([request], graph=graph)
        stream = service.stream(request, principal())

        while (event := await stream.__anext__())["event"] != "token":
            pass
        await stream.aclose()

        self.assertEqual(graph.closed, 1)
        self.assertEqual(turns.get("doctor-1", request.request_id).status, "cancelled")

    async def test_processing_heartbeat_is_ordered_and_increments_sequence(self):
        first = execute_request()
        second_descriptor = first.attachments[0].model_copy(
            update={
                "attachment_id": "attachment-second",
                "analysis_attempt_id": "attempt-second",
            }
        )
        request = first.model_copy(
            update={"attachments": [first.attachments[0], second_descriptor]}
        )
        service, _, _, _, _ = make_service(
            [request],
            analyzer=BlockingAnalyzer(),
            heartbeat_interval=0.001,
        )
        stream = service.stream(request, principal())
        try:
            started = await stream.__anext__()
            initial = [await stream.__anext__(), await stream.__anext__()]
            heartbeat = [await stream.__anext__(), await stream.__anext__()]
        finally:
            await stream.aclose()

        self.assertEqual(started["event"], "execution_started")
        self.assertEqual(
            [item["attachment_id"] for item in initial],
            ["attachment-request-1", "attachment-second"],
        )
        self.assertEqual([item["sequence"] for item in initial], [1, 1])
        self.assertEqual(
            [item["attachment_id"] for item in heartbeat],
            ["attachment-request-1", "attachment-second"],
        )
        self.assertEqual([item["sequence"] for item in heartbeat], [2, 2])

    async def test_aclose_after_done_does_not_downgrade_completed(self):
        request = execute_request()
        service, turns, messages, _, _ = make_service([request])
        stream = service.stream(request, principal())

        while (event := await stream.__anext__())["event"] != "done":
            pass
        await stream.aclose()

        self.assertEqual(turns.get("doctor-1", request.request_id).status, "completed")
        self.assertEqual(messages.get_by_id(request.assistant_message_id).status, "success")

    async def test_aclose_after_error_does_not_downgrade_failed(self):
        request = execute_request()
        service, turns, messages, _, _ = make_service(
            [request], graph=FakeGraphManager(fail=True)
        )
        stream = service.stream(request, principal())

        while (event := await stream.__anext__())["event"] != "error":
            pass
        await stream.aclose()

        self.assertEqual(turns.get("doctor-1", request.request_id).status, "failed")
        self.assertEqual(messages.get_by_id(request.assistant_message_id).status, "failed")

    async def test_turn_deadline_is_fifteen_minutes(self):
        request = execute_request()
        service, turns, _, _, _ = make_service([request])

        await collect(service.stream(request, principal()))

        turn = turns.get("doctor-1", request.request_id)
        self.assertEqual((turn.deadline_at - turn.execute_started_at).total_seconds(), 900)

    async def test_two_concurrent_transient_contexts_are_isolated(self):
        first = execute_request("one")
        second = execute_request("two")
        graph = FakeGraphManager()
        service, _, _, graph, _ = make_service([first, second], graph=graph)

        await asyncio.gather(
            collect(service.stream(first, principal())),
            collect(service.stream(second, principal())),
        )

        observed = {
            context.analyses[0].attachment_id: context.analyses[0].untrusted_text
            for context in graph.contexts
        }
        self.assertEqual(
            observed,
            {
                "attachment-one": "private-attachment-one",
                "attachment-two": "private-attachment-two",
            },
        )

    async def test_done_is_emitted_after_success_commit(self):
        request = execute_request()
        service, turns, _, _, db = make_service([request])

        events = []
        async for event in service.stream(request, principal()):
            events.append(event)
            if event["event"] == "done":
                self.assertEqual(db.depth, 0)
                self.assertEqual(
                    turns.get("doctor-1", request.request_id).status,
                    "completed",
                )

        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(db.depth, 0)
        self.assertEqual(turns.get("doctor-1", request.request_id).status, "completed")

    async def test_error_is_emitted_after_failure_commit(self):
        request = execute_request()
        service, turns, _, _, db = make_service(
            [request], graph=FakeGraphManager(fail=True)
        )

        events = []
        async for event in service.stream(request, principal()):
            events.append(event)
            if event["event"] == "error":
                self.assertEqual(db.depth, 0)
                self.assertEqual(
                    turns.get("doctor-1", request.request_id).status,
                    "failed",
                )

        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(db.depth, 0)
        self.assertEqual(turns.get("doctor-1", request.request_id).status, "failed")

    async def test_persisted_context_redacts_attachment_transport_fields(self):
        request = execute_request()
        graph = FakeGraphManager(
            tool_results=[
                {
                    "name": "safe_tool",
                    "args": {"download_url": "https://secret", "safe": "ok"},
                    "content": "untrusted_text=private",
                }
            ],
            citations=[{"title": "safe", "storage_key": "secret"}],
        )
        service, _, messages, _, _ = make_service([request], graph=graph)

        events = await collect(service.stream(request, principal()))

        persisted = messages.get_by_id(request.assistant_message_id).context
        self.assertEqual(events[-1]["event"], "done")
        self.assertIn('"safe": "ok"', persisted)
        for forbidden in (
            "download_url",
            "untrusted_text",
            "storage_key",
            "https://secret",
        ):
            self.assertNotIn(forbidden, persisted)


class ChatTurnExecutionRegistryContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_abort_signal_is_visible_to_registered_execution(self):
        registry = ChatTurnExecutionRegistry()
        event = registry.register("request-1")

        self.assertFalse(event.is_set())
        registry.signal("request-1")
        self.assertTrue(event.is_set())
        registry.unregister("request-1", event)


if __name__ == "__main__":
    unittest.main()
