import asyncio
import json
import threading
import unittest
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from agents.graph_manager import GraphManager, PreparedGraphTerminal
from application.services.research_document_context_selector import (
    ResearchCitationCandidate,
    ResearchContextBlock,
    ResearchDocumentContextSelection,
)
from application.services.chat_turn_execution_registry import (
    ChatTurnExecutionRegistry,
)
from application.services.chat_turn_watchdog import ChatTurnWatchdog
from application.services.platform_attachment_analyzer import (
    AttachmentStatusUpdate,
)
from application.services.platform_chat_turn_execution_service import (
    ATTACHMENT_EXECUTE_MISMATCH,
    PlatformChatTurnExecutionService,
    PlatformPrincipalError,
    _ExecutionStopped,
)
from domain.models.chat_turn_request import ChatTurnRequestEntity
from domain.security.principal import CurrentPrincipal
from domain.models.chat_entity import MessageContext
from infrastructure.attachments.config import (
    AllowedAttachmentEndpoint,
    AttachmentConfigurationError,
    AttachmentDownloadSettings,
)
from infrastructure.repositories.chat_turn_request_repository_impl import (
    ChatTurnRequestRepositoryImpl,
)
from presentation.schemas.platform_chat_turn_schemas import (
    ExecutePlatformChatTurnRequest,
)
from utils.transient_attachment_context import (
    AttachmentAnalysis,
    get_attachment_analysis,
    get_research_document_context,
)


TXT_SECRET_SENTINEL = "TXT_SECRET_SENTINEL_7f9c"
SAFE_CITATION_EXCERPT = "可公开引用的独立摘要文本"


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
        self.ingestion_cas_calls = []
        self.ingestion_cas_result = True

    def get(self, doctor_id, request_id):
        return self.items.get((doctor_id, request_id))

    def get_for_update(self, doctor_id, request_id):
        return self.get(doctor_id, request_id)

    def list_stale(self, now):
        prepared_before = now - timedelta(minutes=10)
        return [
            turn
            for turn in self.items.values()
            if (
                turn.status == "prepared"
                and turn.create_time <= prepared_before
            )
            or (
                turn.status == "streaming"
                and turn.deadline_at is not None
                and turn.deadline_at <= now
            )
        ]

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

    def compare_and_set_ingestion_ids(
        self,
        doctor_id,
        request_id,
        expected_status,
        ingestion_ids,
    ):
        self.ingestion_cas_calls.append(
            (doctor_id, request_id, expected_status, list(ingestion_ids))
        )
        turn = self.get(doctor_id, request_id)
        if (
            not self.ingestion_cas_result
            or turn is None
            or turn.status != expected_status
        ):
            return False
        turn.ingestion_ids_json = json.dumps(
            list(ingestion_ids),
            ensure_ascii=False,
            separators=(",", ":"),
        )
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
        self.calls = []

    async def analyze_all(self, downloaded, on_status):
        self.calls.append(list(downloaded))
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


class FakeResearchIngestion:
    def __init__(self, *, fail=False, block=False, on_call=None):
        self.fail = fail
        self.block = block
        self.on_call = on_call
        self.calls = []
        self.started = asyncio.Event()
        self.cancelled = False

    async def ingest(self, doctor_id, downloaded, *, deadline=None):
        self.calls.append((doctor_id, list(downloaded), deadline))
        self.started.set()
        if self.on_call is not None:
            self.on_call()
        try:
            if self.block:
                await asyncio.Event().wait()
            if self.fail:
                error = RuntimeError("private ingestion failure")
                error.error_code = "RESEARCH_DOCUMENT_INGESTION_FAILED"
                raise error
            entities = tuple(
                SimpleNamespace(id=f"ingestion-{item.attachment_id}")
                for item in downloaded
            )
            return SimpleNamespace(
                entities=entities,
                ingestion_ids=tuple(entity.id for entity in entities),
            )
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class FakeResearchSelector:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    async def select(self, explicit_ingestion_ids, ready_entities, question):
        self.calls.append(
            (tuple(explicit_ingestion_ids), dict(ready_entities), question)
        )
        if self.fail:
            error = RuntimeError("private selector failure")
            error.error_code = "RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE"
            raise error
        return ResearchDocumentContextSelection(
            context_blocks=(
                ResearchContextBlock(
                    content="PRIVATE_RESEARCH_CONTEXT",
                    supporting_segment_ids=("segment-1",),
                    estimated_tokens=10,
                ),
            ),
            citation_candidates=(),
            mode="focused",
            estimated_tokens=10,
        )


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
            if kwargs.get("agent_type") == "research":
                self.contexts.append(
                    get_research_document_context(kwargs["runnable_config"])
                )
            else:
                self.contexts.append(
                    get_attachment_analysis(kwargs["runnable_config"])
                )
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
                agent_type=kwargs.get("agent_type", "health"),
                stage="collecting_info",
            )
        finally:
            self.closed += 1


def principal(doctor_id="doctor-1", scopes=None):
    return CurrentPrincipal(
        issuer="java",
        subject=doctor_id,
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=frozenset(scopes or {"ai:chat"}),
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


def text_descriptor(attachment_id):
    return {
        "attachment_id": attachment_id,
        "file_type": "text",
        "filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 128,
        "page_count": None,
        "content_sha256": "e" * 64,
        "document_version": 3,
        "analysis_attempt_id": f"attempt-{attachment_id}",
        "download_url": f"https://storage.example/{attachment_id}",
    }


def image_descriptor(attachment_id):
    return {
        "attachment_id": attachment_id,
        "file_type": "image",
        "filename": "fundus.png",
        "mime_type": "image/png",
        "size_bytes": 128,
        "page_count": None,
        "content_sha256": "d" * 64,
        "document_version": 2,
        "analysis_attempt_id": f"attempt-{attachment_id}",
        "download_url": f"https://storage.example/{attachment_id}",
    }


def turn_for(request):
    return ChatTurnRequestEntity(
        doctor_id=request.doctor_id,
        request_id=request.request_id,
        request_fingerprint=request.request_fingerprint,
        protocol_version=request.version,
        agent_type=request.agent_type or "health",
        attachment_scope=request.attachment_scope or "patient",
        research_options_json=(
            json.dumps(
                request.research_options.model_dump(mode="json"),
                separators=(",", ":"),
            )
            if request.research_options is not None
            else None
        ),
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
    research_ingestion=None,
    research_selector=None,
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
    analyzer = analyzer or FakeAnalyzer()
    service = PlatformChatTurnExecutionService(
        db=db,
        turn_repo=turn_repo,
        conversation_repo=FakeConversationRepository(conversations),
        message_repo=message_repo,
        downloader=FakeDownloader(settings),
        analyzer=analyzer,
        research_ingestion_service=(
            research_ingestion or FakeResearchIngestion()
        ),
        research_context_selector=(
            research_selector or FakeResearchSelector()
        ),
        graph_manager=graph,
        registry=ChatTurnExecutionRegistry(),
        download_settings=settings,
        heartbeat_interval=heartbeat_interval,
    )
    return service, turn_repo, message_repo, graph, db


async def collect(generator):
    return [event async for event in generator]


class PlatformChatTurnExecutionContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_research_execute_requires_ai_research_scope(self):
        request = execute_request(
            "research-auth",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": True,
                "enable_web_search": False,
                "types": [],
            },
        )
        denied_service, _, _, _, _ = make_service([request])
        with self.assertRaises(PlatformPrincipalError):
            await collect(
                denied_service.stream(
                    request,
                    principal(scopes={"ai:chat"}),
                )
            )

        allowed_service, _, _, _, _ = make_service([request])
        events = await collect(
            allowed_service.stream(
                request,
                principal(scopes={"ai:research"}),
            )
        )
        self.assertEqual(events[-1]["event"], "done")

    async def test_research_uses_ingestion_selector_cas_and_prepared_snapshot(self):
        request = execute_request(
            "research-pipeline",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": True,
                "enable_web_search": True,
                "types": ["pubmed"],
            },
        )
        ingestion = FakeResearchIngestion()

        def mutate_execute_options():
            request.research_options.enable_institution_data = False
            request.research_options.enable_web_search = False
            request.research_options.types = []

        ingestion.on_call = mutate_execute_options
        selector = FakeResearchSelector()
        service, turns, _, graph, _ = make_service(
            [request],
            research_ingestion=ingestion,
            research_selector=selector,
        )

        events = await collect(
            service.stream(request, principal(scopes={"ai:research"}))
        )

        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(service.analyzer.calls, [])
        self.assertEqual(len(ingestion.calls), 1)
        ids, ready_map, question = selector.calls[0]
        self.assertEqual(ids, ("ingestion-attachment-research-pipeline",))
        self.assertEqual(tuple(ready_map), ids)
        self.assertEqual(question, "请分析附件")
        turn = turns.get("doctor-1", request.request_id)
        self.assertEqual(turn.ingestion_ids, list(ids))
        self.assertEqual(
            turns.ingestion_cas_calls,
            [("doctor-1", request.request_id, "streaming", list(ids))],
        )
        call = graph.calls[0]
        self.assertIsNone(call["patient_id"])
        self.assertEqual(call["agent_type"], "research")
        self.assertEqual(
            call["research_options"],
            {
                "enable_institution_data": True,
                "enable_web_search": True,
                "types": ["pubmed"],
            },
        )
        self.assertIsNone(call["health_handle"])
        self.assertIsInstance(call["research_handle"], str)
        statuses = [
            event["status"]
            for event in events
            if event["event"] == "attachment_status"
        ]
        self.assertEqual(statuses, ["processing", "ready"])

    async def test_txt_only_text_txt_and_image_txt_share_research_execution(self):
        cases = (
            (
                "txt-only",
                "",
                [text_descriptor("attachment-txt-only")],
                "research-document-analysis-v1",
            ),
            (
                "text-and-txt",
                "请总结重点",
                [text_descriptor("attachment-text-and-txt")],
                None,
            ),
            (
                "image-and-txt",
                "请结合图像与记录分析",
                [
                    image_descriptor("attachment-image-mixed"),
                    text_descriptor("attachment-txt-mixed"),
                ],
                None,
            ),
        )

        for request_id, question, attachments, implicit_prompt_id in cases:
            with self.subTest(request_id=request_id):
                request = execute_request(
                    request_id,
                    version=2,
                    patient_id=None,
                    agent_type="research",
                    attachment_scope="research",
                    research_options={
                        "enable_institution_data": False,
                        "enable_web_search": False,
                        "types": [],
                    },
                    attachments=attachments,
                )
                citation = {
                    "source_type": "attachment",
                    "attachment_id": attachments[-1]["attachment_id"],
                    "document_version": attachments[-1]["document_version"],
                    "segment_id": f"segment-{request_id}",
                    "locator": {"type": "file"},
                    "excerpt": SAFE_CITATION_EXCERPT,
                }
                ingestion = FakeResearchIngestion()
                selector = FakeResearchSelector()
                graph = FakeGraphManager(citations=[citation])
                service, turns, messages, _, _ = make_service(
                    [request],
                    graph=graph,
                    research_ingestion=ingestion,
                    research_selector=selector,
                )
                turn = turns.get("doctor-1", request.request_id)
                turn.implicit_prompt_id = implicit_prompt_id
                messages.get_by_id(request.user_message_id).message_content = (
                    question
                )

                events = await collect(
                    service.stream(
                        request,
                        principal(scopes={"ai:research"}),
                    )
                )

                self.assertEqual(events[-1]["event"], "done")
                self.assertEqual(events[-1]["citations"], [citation])
                self.assertEqual(service.analyzer.calls, [])
                self.assertEqual(
                    [item.file_type for item in ingestion.calls[0][1]],
                    [item["file_type"] for item in attachments],
                )
                self.assertEqual(selector.calls[0][2], question)
                self.assertEqual(
                    graph.contexts[0].implicit_prompt_id,
                    implicit_prompt_id,
                )

    async def test_txt_content_failure_fails_whole_turn_without_answer_or_body(self):
        request = execute_request(
            "txt-content-failure",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": False,
                "enable_web_search": False,
                "types": [],
            },
            attachments=[text_descriptor("attachment-txt-failure")],
        )

        class FailingTxtIngestion:
            @staticmethod
            async def ingest(_doctor_id, _downloaded, *, deadline=None):
                error = RuntimeError(
                    f"invalid text body: {TXT_SECRET_SENTINEL}"
                )
                error.error_code = "RESEARCH_TXT_CONTENT_LIMIT"
                raise error

        graph = FakeGraphManager()
        service, turns, messages, _, _ = make_service(
            [request],
            graph=graph,
            research_ingestion=FailingTxtIngestion(),
        )

        events = await collect(
            service.stream(request, principal(scopes={"ai:research"}))
        )

        self.assertFalse(any(event["event"] == "token" for event in events))
        self.assertEqual(graph.calls, [])
        self.assertEqual(events[-1]["error_code"], "RESEARCH_TXT_CONTENT_LIMIT")
        self.assertEqual(
            turns.get("doctor-1", request.request_id).status,
            "failed",
        )
        assistant = messages.get_by_id(request.assistant_message_id)
        self.assertEqual(assistant.status, "failed")
        exposed = json.dumps(
            {
                "events": events,
                "turn": turns.get("doctor-1", request.request_id).model_dump(
                    mode="json"
                ),
                "assistant": vars(assistant),
            },
            ensure_ascii=False,
            default=str,
        )
        self.assertNotIn(TXT_SECRET_SENTINEL, exposed)

    async def test_research_regenerate_keeps_canonical_turn_configuration(self):
        request = execute_request(
            "research-regenerate-context",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": True,
                "enable_web_search": True,
                "types": ["pubmed"],
            },
        )
        service, turns, messages, _, _ = make_service([request])
        turn = turns.get("doctor-1", request.request_id)
        turn.operation = "regenerate"
        assistant = messages.get_by_id(request.assistant_message_id)
        assistant.context = json.dumps(
            [
                {
                    "metadata": {
                        "attachment_ids": [
                            item.attachment_id for item in request.attachments
                        ],
                        "turn_configuration": {
                            "protocol_version": 2,
                            "agent_type": "research",
                            "attachment_scope": "research",
                            "research_options": {
                                "enable_institution_data": True,
                                "enable_web_search": True,
                                "types": ["pubmed"],
                            },
                        },
                    }
                }
            ],
            ensure_ascii=False,
        )

        events = await collect(
            service.stream(request, principal(scopes={"ai:research"}))
        )

        self.assertEqual(events[-1]["event"], "done")
        persisted = json.loads(assistant.context)
        metadata = next(
            item["metadata"] for item in persisted if "metadata" in item
        )
        self.assertEqual(
            metadata["turn_configuration"],
            {
                "protocol_version": 2,
                "agent_type": "research",
                "attachment_scope": "research",
                "research_options": {
                    "enable_institution_data": True,
                    "enable_web_search": True,
                    "types": ["pubmed"],
                },
            },
        )
        self.assertEqual(
            metadata["attachment_ids"],
            [item.attachment_id for item in request.attachments],
        )
        serialized = json.dumps(persisted, ensure_ascii=False)
        for forbidden in (
            "patient_id",
            "download_url",
            "handle",
            "PRIVATE_RESEARCH_CONTEXT",
        ):
            self.assertNotIn(forbidden, serialized)

    async def test_health_path_keeps_analyzer_and_never_calls_research_services(self):
        request = execute_request("health-regression")
        ingestion = FakeResearchIngestion()
        selector = FakeResearchSelector()
        analyzer = FakeAnalyzer()
        service, _, _, graph, _ = make_service(
            [request],
            analyzer=analyzer,
            research_ingestion=ingestion,
            research_selector=selector,
        )

        events = await collect(service.stream(request, principal()))

        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(len(analyzer.calls), 1)
        self.assertEqual(ingestion.calls, [])
        self.assertEqual(selector.calls, [])
        call = graph.calls[0]
        self.assertEqual(call["patient_id"], request.patient_id)
        self.assertEqual(call["agent_type"], "health")
        self.assertIsNone(call["research_options"])
        self.assertIsInstance(call["health_handle"], str)
        self.assertIsNone(call["research_handle"])

    async def test_research_ingestion_or_selector_failure_emits_zero_tokens(self):
        for failure in ("ingestion", "selector"):
            with self.subTest(failure=failure):
                request = execute_request(
                    f"research-{failure}-failure",
                    version=2,
                    patient_id=None,
                    agent_type="research",
                    attachment_scope="research",
                    research_options={
                        "enable_institution_data": False,
                        "enable_web_search": False,
                        "types": [],
                    },
                )
                ingestion = FakeResearchIngestion(fail=failure == "ingestion")
                selector = FakeResearchSelector(fail=failure == "selector")
                service, turns, _, graph, _ = make_service(
                    [request],
                    research_ingestion=ingestion,
                    research_selector=selector,
                )

                events = await collect(
                    service.stream(request, principal(scopes={"ai:research"}))
                )

                expected = (
                    "RESEARCH_DOCUMENT_INGESTION_FAILED"
                    if failure == "ingestion"
                    else "RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE"
                )
                self.assertFalse(
                    any(event["event"] == "token" for event in events)
                )
                self.assertEqual(graph.calls, [])
                self.assertEqual(events[-1]["error_code"], expected)
                failed = [
                    event
                    for event in events
                    if event["event"] == "attachment_status"
                    and event["status"] == "failed"
                ]
                self.assertEqual(len(failed), len(request.attachments))
                self.assertTrue(
                    all(event["error_code"] == expected for event in failed)
                )
                self.assertEqual(
                    turns.get("doctor-1", request.request_id).status,
                    "failed",
                )

    async def test_research_abort_cancels_and_joins_ingestion_task(self):
        request = execute_request(
            "research-abort",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": False,
                "enable_web_search": False,
                "types": [],
            },
        )
        ingestion = FakeResearchIngestion(block=True)
        service, turns, _, graph, _ = make_service(
            [request],
            research_ingestion=ingestion,
            heartbeat_interval=0.001,
        )
        stream = service.stream(request, principal(scopes={"ai:research"}))

        self.assertEqual((await stream.__anext__())["event"], "execution_started")
        self.assertEqual((await stream.__anext__())["status"], "processing")
        pending = asyncio.create_task(stream.__anext__())
        await asyncio.wait_for(ingestion.started.wait(), timeout=1)
        service.registry.signal("doctor-1", request.request_id)
        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(pending, timeout=1)
        await stream.aclose()

        self.assertTrue(ingestion.cancelled)
        self.assertEqual(graph.calls, [])
        self.assertEqual(
            turns.get("doctor-1", request.request_id).status,
            "cancelled",
        )

    async def test_txt_abort_cancels_ingestion_and_emits_no_body(self):
        request = execute_request(
            "research-txt-abort",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": False,
                "enable_web_search": False,
                "types": [],
            },
            attachments=[text_descriptor("attachment-txt-abort")],
        )
        ingestion = FakeResearchIngestion(block=True)
        service, turns, messages, graph, _ = make_service(
            [request],
            research_ingestion=ingestion,
            heartbeat_interval=0.001,
        )
        stream = service.stream(request, principal(scopes={"ai:research"}))
        observed = [await stream.__anext__(), await stream.__anext__()]
        pending = asyncio.create_task(stream.__anext__())
        await asyncio.wait_for(ingestion.started.wait(), timeout=1)

        service.registry.signal("doctor-1", request.request_id)
        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(pending, timeout=1)
        await stream.aclose()

        self.assertTrue(ingestion.cancelled)
        self.assertEqual(graph.calls, [])
        self.assertEqual(
            turns.get("doctor-1", request.request_id).status,
            "cancelled",
        )
        self.assertEqual(
            messages.get_by_id(request.assistant_message_id).status,
            "cancelled",
        )
        self.assertNotIn(
            TXT_SECRET_SENTINEL,
            json.dumps(observed, ensure_ascii=False),
        )

    async def test_cancel_race_retrieves_completed_analysis_failure(self):
        request = execute_request()
        service, _, _, _, _ = make_service([request])

        async def fail():
            raise RuntimeError("PRIVATE_ANALYSIS_FAILURE_SENTINEL")

        failed = asyncio.create_task(fail())
        await asyncio.sleep(0)
        self.assertTrue(failed.done())
        cancel_event = asyncio.Event()
        cancel_event.set()

        with self.assertRaises(_ExecutionStopped):
            await service._wait_until_activity(
                failed,
                asyncio.Queue(),
                cancel_event,
                service._clock() + 1,
            )

        self.assertFalse(getattr(failed, "_log_traceback", True))

    async def test_graph_cancel_race_retrieves_completed_next_failure(self):
        request = execute_request()
        service, _, _, _, _ = make_service([request])
        created = []
        real_create_task = asyncio.create_task

        class FailingStream:
            async def __anext__(self):
                raise RuntimeError("PRIVATE_GRAPH_FAILURE_SENTINEL")

        def capture_task(coroutine):
            task = real_create_task(coroutine)
            created.append(task)
            return task

        cancel_event = asyncio.Event()
        cancel_event.set()
        with patch(
            "application.services.platform_chat_turn_execution_service."
            "asyncio.create_task",
            side_effect=capture_task,
        ):
            with self.assertRaises(_ExecutionStopped):
                await service._next_graph_event(
                    FailingStream(),
                    cancel_event,
                    service._clock() + 1,
                )

        self.assertGreaterEqual(len(created), 2)
        self.assertTrue(created[0].done())
        self.assertFalse(getattr(created[0], "_log_traceback", True))

    async def test_research_ingestion_id_cas_miss_fails_before_graph(self):
        request = execute_request(
            "research-cas-miss",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": False,
                "enable_web_search": False,
                "types": [],
            },
        )
        service, turns, _, graph, _ = make_service([request])
        turns.ingestion_cas_result = False

        events = await collect(
            service.stream(request, principal(scopes={"ai:research"}))
        )

        self.assertFalse(any(event["event"] == "token" for event in events))
        self.assertEqual(graph.calls, [])
        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(
            events[-1]["error_code"],
            "RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE",
        )

    async def test_execute_mismatch_keeps_turn_prepared(self):
        prepared = execute_request()
        service, turns, _, graph, _ = make_service([prepared])
        mismatched = prepared.model_copy(update={"patient_id": "other-patient"})

        events = await collect(service.stream(mismatched, principal()))

        self.assertEqual(events[-1]["error_code"], ATTACHMENT_EXECUTE_MISMATCH)
        self.assertEqual(turns.get("doctor-1", "request-1").status, "prepared")
        self.assertEqual(graph.calls, [])

    async def test_missing_download_configuration_finalizes_claimed_turn_as_failed(self):
        request = execute_request("missing-download-configuration")
        service, turns, messages, graph, _ = make_service([request])
        service.downloader = None
        service.download_settings = None

        with patch(
            "application.services.platform_chat_turn_execution_service."
            "AttachmentDownloadSettings.from_env",
            side_effect=AttachmentConfigurationError("missing allowlist"),
        ):
            events = await collect(service.stream(request, principal()))

        self.assertEqual(events, [
            {
                "event": "error",
                "request_id": request.request_id,
                "user_message_id": request.user_message_id,
                "assistant_message_id": request.assistant_message_id,
                "error_code": "ATTACHMENT_ANALYSIS_FAILED",
            }
        ])
        self.assertEqual(
            turns.get("doctor-1", request.request_id).status,
            "failed",
        )
        self.assertEqual(
            messages.get_by_id(request.assistant_message_id).status,
            "failed",
        )
        self.assertEqual(graph.calls, [])

    async def test_execute_rejects_each_authoritative_v2_snapshot_mismatch(self):
        request = execute_request(
            "research",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": True,
                "enable_web_search": True,
                "types": ["general", "pubmed"],
            },
        )
        mismatches = {
            "protocol_version": 1,
            "agent_type": "health",
            "attachment_scope": "patient",
            "research_options_json": (
                '{"enable_institution_data":false,'
                '"enable_web_search":true,'
                '"types":["general","pubmed"]}'
            ),
        }

        for field, value in mismatches.items():
            with self.subTest(field=field):
                service, turns, _, graph, _ = make_service([request])
                setattr(
                    turns.get("doctor-1", request.request_id),
                    field,
                    value,
                )

                events = await collect(
                    service.stream(
                        request,
                        principal(scopes={"ai:chat", "ai:research"}),
                    )
                )

                self.assertEqual(
                    events[-1]["error_code"],
                    ATTACHMENT_EXECUTE_MISMATCH,
                )
                self.assertEqual(
                    turns.get("doctor-1", request.request_id).status,
                    "prepared",
                )
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

    async def test_watchdog_failure_after_stream_start_emits_safe_terminal_error(self):
        sentinel = "SIGNED_URL_SENTINEL_must_not_leak"
        base = execute_request()
        descriptor = base.attachments[0].model_copy(
            update={
                "filename": f"{sentinel}.png",
                "download_url": (
                    "https://storage.example/file?token=" + sentinel
                ),
            }
        )
        request = base.model_copy(update={"attachments": [descriptor]})
        service, turns, messages, _, db = make_service(
            [request],
            analyzer=BlockingAnalyzer(),
            heartbeat_interval=0.001,
        )
        stream = service.stream(request, principal())

        self.assertEqual((await stream.__anext__())["event"], "execution_started")
        self.assertEqual((await stream.__anext__())["event"], "attachment_status")
        turn = turns.get("doctor-1", request.request_id)
        turn.deadline_at = datetime.now() - timedelta(seconds=1)
        watchdog = ChatTurnWatchdog(
            db=db,
            turn_repo=turns,
            conversation_repo=service.conversation_repo,
            message_repo=messages,
        )

        result = watchdog.reconcile_once(datetime.now())
        terminal = await asyncio.wait_for(stream.__anext__(), timeout=1)

        self.assertEqual(result.streaming_failed, 1)
        self.assertEqual(
            terminal,
            {
                "event": "error",
                "request_id": request.request_id,
                "user_message_id": request.user_message_id,
                "assistant_message_id": request.assistant_message_id,
                "error_code": "ATTACHMENT_ANALYSIS_TIMEOUT",
            },
        )
        self.assertNotIn(sentinel, json.dumps(terminal))
        self.assertEqual(turn.status, "failed")
        assistant = messages.get_by_id(request.assistant_message_id)
        self.assertEqual(assistant.status, "failed")
        self.assertEqual(
            assistant.error_message,
            "ATTACHMENT_ANALYSIS_TIMEOUT",
        )
        with self.assertRaises(StopAsyncIteration):
            await stream.__anext__()

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

    async def test_done_and_assistant_history_share_canonical_attachment_citations(self):
        request = execute_request(
            "research-citations",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": False,
                "enable_web_search": False,
                "types": [],
            },
        )
        citation = {
            "source_type": "attachment",
            "attachment_id": "attachment-research-citations",
            "document_version": 2,
            "segment_id": "segment-1",
            "locator": {
                "type": "page",
                "page_start": 4,
                "page_end": 4,
            },
            "excerpt": "受控引用片段",
        }
        graph = FakeGraphManager(citations=[citation])
        service, _, messages, _, _ = make_service([request], graph=graph)

        events = await collect(
            service.stream(request, principal(scopes={"ai:research"}))
        )

        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(events[-1]["citations"], [citation])
        persisted = json.loads(
            messages.get_by_id(request.assistant_message_id).context
        )
        history = MessageContext.from_context_list(persisted)
        self.assertEqual(history.citations, events[-1]["citations"])
        serialized = json.dumps(persisted, ensure_ascii=False).lower()
        self.assertNotIn("filename", serialized)
        self.assertNotIn("url", serialized)

    async def test_research_no_tool_fallback_reaches_done_and_history(self):
        request = execute_request(
            "research-fallback-e2e",
            version=2,
            patient_id=None,
            agent_type="research",
            attachment_scope="research",
            research_options={
                "enable_institution_data": False,
                "enable_web_search": False,
                "types": [],
            },
            attachments=[
                {
                    "attachment_id": "attachment-pdf-e2e",
                    "file_type": "pdf",
                    "filename": "private-report.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 256,
                    "page_count": 2,
                    "content_sha256": "c" * 64,
                    "document_version": 4,
                    "analysis_attempt_id": "attempt-pdf-e2e",
                    "download_url": "https://storage.example/private-pdf",
                },
                {
                    "attachment_id": "attachment-image-e2e",
                    "file_type": "image",
                    "filename": "private-image.png",
                    "mime_type": "image/png",
                    "size_bytes": 128,
                    "page_count": None,
                    "content_sha256": "d" * 64,
                    "document_version": 5,
                    "analysis_attempt_id": "attempt-image-e2e",
                    "download_url": "https://storage.example/private-image",
                },
            ],
        )
        candidates = (
            ResearchCitationCandidate(
                segment_id="segment-pdf-e2e",
                ingestion_id="ingestion-attachment-pdf-e2e",
                attachment_id="attachment-pdf-e2e",
                document_version=4,
                page_start=2,
                page_end=2,
                content="PDF 受控摘录",
                token_count=10,
            ),
            ResearchCitationCandidate(
                segment_id="segment-image-e2e",
                ingestion_id="ingestion-attachment-image-e2e",
                attachment_id="attachment-image-e2e",
                document_version=5,
                page_start=None,
                page_end=None,
                content="图片受控摘录",
                token_count=10,
            ),
        )
        selection = ResearchDocumentContextSelection(
            context_blocks=(
                ResearchContextBlock(
                    content="PRIVATE_FULL_DOCUMENT_BODY",
                    supporting_segment_ids=tuple(
                        candidate.segment_id for candidate in candidates
                    ),
                    estimated_tokens=10,
                ),
            ),
            citation_candidates=candidates,
            mode="focused",
            estimated_tokens=10,
        )

        class StaticSelector:
            async def select(self, *_args, **_kwargs):
                return selection

        class Checkpointer:
            @staticmethod
            def save_thread_mapping(**_kwargs):
                return True

        class StreamingGraph:
            async def astream_events(self, _state, config, version):
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": SimpleNamespace(content="科研回答")},
                }

            @staticmethod
            def get_state(_config):
                return SimpleNamespace(values={})

        manager = object.__new__(GraphManager)
        manager.checkpointer = Checkpointer()
        manager._build_branch_history_messages = lambda **_kwargs: []
        manager._get_state_message_count = lambda *_args: 0
        service, _, messages, _, _ = make_service(
            [request],
            graph=manager,
            research_selector=StaticSelector(),
        )

        with patch(
            "agents.graph.graph_builder.get_streaming_medical_graph",
            return_value=StreamingGraph(),
        ), patch(
            "utils.role_verification.verify_role",
            return_value=("doctor", False),
        ):
            events = await collect(
                service.stream(request, principal(scopes={"ai:research"}))
            )

        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(
            [item["segment_id"] for item in events[-1]["citations"]],
            ["segment-pdf-e2e", "segment-image-e2e"],
        )
        self.assertEqual(
            events[-1]["citations"][0]["locator"],
            {"type": "page", "page_start": 2, "page_end": 2},
        )
        self.assertEqual(
            events[-1]["citations"][1]["locator"],
            {"type": "file"},
        )
        history = MessageContext.from_context_list(
            json.loads(messages.get_by_id(request.assistant_message_id).context)
        )
        self.assertEqual(history.citations, events[-1]["citations"])
        public_and_history = json.dumps(
            {"events": events, "history": history.to_context_list()},
            ensure_ascii=False,
        )
        for forbidden in (
            "PRIVATE_FULL_DOCUMENT_BODY",
            "private-report.pdf",
            "private-image.png",
            "download_url",
            "storage.example",
            "research_document_context_handle",
        ):
            self.assertNotIn(forbidden, public_and_history)

    async def test_finalize_race_restores_citations_from_persisted_assistant(self):
        persisted_citation = {
            "source_type": "attachment",
            "attachment_id": "attachment-persisted",
            "document_version": 1,
            "segment_id": "segment-persisted",
            "locator": {"type": "file"},
            "excerpt": "已落库引用",
        }
        incoming_citation = {
            "source_type": "attachment",
            "attachment_id": "attachment-incoming",
            "document_version": 2,
            "segment_id": "segment-incoming",
            "locator": {"type": "file"},
            "excerpt": "竞态失败 worker 的引用",
        }

        for mode in ("already_terminal", "cas_lost"):
            with self.subTest(mode=mode):
                request = execute_request(f"citation-race-{mode}")
                service, turns, messages, _, _ = make_service([request])
                turn = turns.get("doctor-1", request.request_id)
                assistant = messages.get_by_id(request.assistant_message_id)
                assistant.context = MessageContext(
                    citations=[persisted_citation]
                ).to_json()
                service._active_doctors[
                    (request.request_id, request.assistant_message_id)
                ] = "doctor-1"

                if mode == "already_terminal":
                    turn.status = "completed"
                else:
                    turn.status = "streaming"

                    def lose_cas(*_args, **_kwargs):
                        turn.status = "completed"
                        return False

                    turns.compare_and_set_status = lose_cas

                result = await service.finalize_platform_turn_success(
                    request.request_id,
                    request.assistant_message_id,
                    PreparedGraphTerminal(
                        content="竞态回答",
                        token_used=1,
                        tool_results=[],
                        citations=[incoming_citation],
                        agent_type="research",
                        stage="research_init",
                    ),
                )

                done = service.build_public_terminal_event(result)
                history = MessageContext.from_context_list(
                    json.loads(assistant.context)
                )
                self.assertEqual(done["citations"], [persisted_citation])
                self.assertEqual(done["citations"], history.citations)
                self.assertNotEqual(done["citations"], [incoming_citation])


class ChatTurnExecutionRegistryContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_abort_signal_is_visible_to_registered_execution(self):
        registry = ChatTurnExecutionRegistry()
        event = registry.register("doctor-1", "request-1")

        self.assertFalse(event.is_set())
        registry.signal("doctor-1", "request-1")
        self.assertTrue(event.is_set())
        registry.unregister("doctor-1", "request-1", event)

    async def test_same_request_id_is_isolated_by_doctor(self):
        registry = ChatTurnExecutionRegistry()
        doctor_one = registry.register("doctor-1", "shared-request")
        doctor_two = registry.register("doctor-2", "shared-request")

        registry.signal("doctor-1", "shared-request")

        self.assertTrue(doctor_one.is_set())
        self.assertFalse(doctor_two.is_set())
        registry.unregister("doctor-1", "shared-request", doctor_one)
        registry.unregister("doctor-2", "shared-request", doctor_two)


class ChatTurnRequestIngestionCasTest(unittest.TestCase):
    class _DB:
        def __init__(self, affected=1):
            self.affected = affected
            self.calls = []

        def execute(self, sql, params):
            self.calls.append((" ".join(sql.split()), params))
            return self.affected

    def test_ingestion_ids_cas_uses_canonical_json_and_exact_row_count(self):
        db = self._DB(affected=1)
        repository = ChatTurnRequestRepositoryImpl(db=db)

        changed = repository.compare_and_set_ingestion_ids(
            "doctor-1",
            "request-1",
            "streaming",
            ["ingestion-1", "ingestion-2"],
        )

        self.assertTrue(changed)
        sql, params = db.calls[0]
        self.assertIn("WHERE doctor_id = %s", sql)
        self.assertIn("request_id = %s", sql)
        self.assertIn("status = %s", sql)
        self.assertEqual(params[0], '["ingestion-1","ingestion-2"]')
        self.assertEqual(
            params[1:4],
            ("doctor-1", "request-1", "streaming"),
        )

        duplicate_rows = ChatTurnRequestRepositoryImpl(db=self._DB(affected=2))
        self.assertFalse(
            duplicate_rows.compare_and_set_ingestion_ids(
                "doctor-1",
                "request-1",
                "streaming",
                ["ingestion-1"],
            )
        )


if __name__ == "__main__":
    unittest.main()
