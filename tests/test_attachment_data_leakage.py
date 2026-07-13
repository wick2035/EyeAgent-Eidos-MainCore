import asyncio
import hashlib
import io
import json
import logging
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from pydantic import ValidationError
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.graph_manager import GraphManager, PreparedGraphTerminal
from agents.graph.state import MedicalState
from application.services.research_document_context_selector import (
    ResearchCitationCandidate,
    ResearchContextBlock,
    ResearchDocumentContextSelection,
)
from application.services.chat_turn_execution_registry import (
    ChatTurnExecutionRegistry,
)
from application.services.platform_attachment_analyzer import (
    PlatformAttachmentAnalyzer,
)
from application.services.platform_chat_turn_execution_service import (
    PlatformChatTurnExecutionService,
)
from application.services.platform_chat_turn_service import (
    PlatformChatTurnService,
    TurnAlreadyCompletedError,
)
from domain.models.chat_turn_request import ChatTurnRequestEntity
from domain.security.principal import CurrentPrincipal
from infrastructure.attachments.config import (
    AllowedAttachmentEndpoint,
    AttachmentDownloadSettings,
)
from infrastructure.attachments.parser_sandbox import AttachmentParserSandbox
from infrastructure.attachments.secure_downloader import DownloadedAttachment
from infrastructure.repositories.chat_repository_impl import (
    ChatMessageRepositoryImpl,
)
from presentation.schemas.platform_chat_turn_schemas import (
    ExecutePlatformChatTurnRequest,
)
from utils.transient_attachment_context import (
    get_attachment_analysis,
    get_research_document_context,
    inject_untrusted_research_documents,
)


_IMAGE = "eyeagent/attachment-parser:research-c1"
_URL_SENTINEL = "URL_QUERY_SENTINEL_7f3f7b"
_BASE64_SENTINEL = "BASE64_SENTINEL_c2Vuc2l0aXZl"
_PARSED_SENTINEL = "PARSED_BODY_SENTINEL_0d81d9"
_FILENAME_SENTINEL = "FILENAME_SENTINEL_51e697"
_TXT_SECRET_SENTINEL = "TXT_SECRET_SENTINEL_7f9c"
_SAFE_CITATION_EXCERPT = "可公开引用的独立摘要文本"
_SENTINELS = (
    _URL_SENTINEL,
    _BASE64_SENTINEL,
    _PARSED_SENTINEL,
    _FILENAME_SENTINEL,
    _TXT_SECRET_SENTINEL,
)


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), color=(20, 40, 60)).save(
        output,
        format="PNG",
    )
    return output.getvalue()


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.entries = []

    def emit(self, record):
        text = record.getMessage()
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        self.entries.append(text)

    @staticmethod
    def formatException(exc_info):
        return logging.Formatter().formatException(exc_info)


class _DB:
    @contextmanager
    def transaction(self):
        yield


class _TurnRepository:
    def __init__(self, turn):
        self.turn = turn

    def get(self, doctor_id, request_id):
        if (doctor_id, request_id) == (
            self.turn.doctor_id,
            self.turn.request_id,
        ):
            return self.turn
        return None

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
        turn = self.get(doctor_id, request_id)
        expected = (
            {expected_status}
            if isinstance(expected_status, str)
            else set(expected_status)
        )
        if turn is None or turn.status not in expected:
            return False
        turn.status = new_status
        turn.error_code = error_code
        if execute_started_at is not None:
            turn.execute_started_at = execute_started_at
        if deadline_at is not None:
            turn.deadline_at = deadline_at
        return True

    def compare_and_set_ingestion_ids(
        self,
        doctor_id,
        request_id,
        expected_status,
        ingestion_ids,
    ):
        turn = self.get(doctor_id, request_id)
        if turn is None or turn.status != expected_status:
            return False
        turn.ingestion_ids_json = json.dumps(
            list(ingestion_ids),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return True


class _TerminalRaceTurnRepository(_TurnRepository):
    def __init__(self, turn, *, winner, winner_finished):
        super().__init__(turn)
        self.winner = winner
        self.winner_finished = winner_finished
        self.terminal_barrier = threading.Barrier(2)
        self.abort_arrived = threading.Event()
        self._cas_lock = threading.Lock()
        self.terminal_calls = []

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
        expected = (
            {expected_status}
            if isinstance(expected_status, str)
            else set(expected_status)
        )
        terminal_race = (
            expected == {"streaming"}
            and new_status in {"completed", "cancelled"}
        )
        if terminal_race:
            self.terminal_calls.append(("arrived", new_status))
            if new_status == "cancelled":
                self.abort_arrived.set()
            self.terminal_barrier.wait(timeout=3)
            if (
                new_status != self.winner
                and not self.winner_finished.wait(timeout=3)
            ):
                raise TimeoutError("terminal winner did not finish")

        with self._cas_lock:
            turn = self.get(doctor_id, request_id)
            if turn is None or turn.status not in expected:
                if terminal_race:
                    self.terminal_calls.append(
                        ("lost", new_status, getattr(turn, "status", None))
                    )
                return False
            turn.status = new_status
            turn.error_code = error_code
            if execute_started_at is not None:
                turn.execute_started_at = execute_started_at
            if deadline_at is not None:
                turn.deadline_at = deadline_at
            if terminal_race:
                self.terminal_calls.append(("won", new_status))
            return True


class _MessageRepository:
    def __init__(self, messages):
        self.items = {item.id: item for item in messages}
        self.update_calls = []

    def get_by_id(self, message_id):
        return self.items.get(message_id)

    def update(self, message_id, updates):
        message = self.items.get(message_id)
        if message is None:
            return False
        self.update_calls.append((message_id, dict(updates)))
        for key, value in updates.items():
            setattr(message, key, value)
        return True

    def get_by_chat_id(self, chat_id, limit=100, offset=0):
        messages = [
            item
            for item in self.items.values()
            if item.chat_id == chat_id and not getattr(item, "deleted", False)
        ]
        return messages[offset:offset + limit]

    def count_by_chat_id(self, chat_id):
        return len(self.get_by_chat_id(chat_id))


class _ConversationRepository:
    def __init__(self, conversation):
        self.conversation = conversation

    def get_by_id(self, conversation_id):
        if conversation_id == self.conversation.id:
            return self.conversation
        return None

    def lock_by_id(self, conversation_id):
        return self.get_by_id(conversation_id)

    def update_summary_and_count(self, conversation_id, summary, count):
        conversation = self.get_by_id(conversation_id)
        if conversation is None:
            return False
        conversation.summary = summary
        conversation.total_messages = count
        return True


class _DownloadedContext:
    def __init__(self, downloaded, settings):
        self.downloaded = downloaded
        self._settings = settings

    @asynccontextmanager
    async def download_all(self, _descriptors, _request_id):
        yield [self.downloaded]


class _CheckpointGraph:
    def __init__(self):
        self.checkpoint = None
        self.observed_analysis = None

    async def chat_stream_prepared_async(self, **kwargs):
        self.observed_analysis = get_attachment_analysis(
            kwargs["runnable_config"]
        )
        self.checkpoint = {
            "attachments": kwargs["safe_attachment_refs"],
            "attachment_analysis": None,
        }
        yield {"type": "token", "content": "安全回答"}
        yield PreparedGraphTerminal(
            content="安全回答",
            token_used=3,
            tool_results=[
                {
                    "download_url": (
                        "https://storage.example/file?token="
                        + _URL_SENTINEL
                    ),
                    "base64_payload": _BASE64_SENTINEL,
                    "untrusted_text": _PARSED_SENTINEL,
                    "filename": _FILENAME_SENTINEL,
                    "safe": "保留",
                }
            ],
            citations=[],
            agent_type="health",
            stage="collecting_info",
        )


class _ResearchTextIngestion:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    async def ingest(self, doctor_id, downloaded, *, deadline=None):
        self.calls.append((doctor_id, list(downloaded), deadline))
        if self.fail:
            error = RuntimeError(
                "RESEARCH_TXT_PARSE_FAILED: " + _TXT_SECRET_SENTINEL
            )
            error.error_code = "RESEARCH_TXT_PARSE_FAILED"
            raise error
        ingestion_id = "ingestion-txt-safe-id"
        return SimpleNamespace(
            entities=(SimpleNamespace(id=ingestion_id),),
            ingestion_ids=(ingestion_id,),
        )


class _ResearchTextSelector:
    async def select(self, _ingestion_ids, _entities, _question):
        return ResearchDocumentContextSelection(
            context_blocks=(
                ResearchContextBlock(
                    content=_TXT_SECRET_SENTINEL,
                    supporting_segment_ids=("segment-txt-safe-id",),
                    estimated_tokens=8,
                ),
            ),
            citation_candidates=(
                ResearchCitationCandidate(
                    segment_id="segment-txt-safe-id",
                    ingestion_id="ingestion-txt-safe-id",
                    attachment_id="attachment-txt-safe-id",
                    document_version=9,
                    page_start=None,
                    page_end=None,
                    content=_SAFE_CITATION_EXCERPT,
                    token_count=8,
                ),
            ),
            mode="focused",
            estimated_tokens=8,
        )


class _RecordingMemorySaver(MemorySaver):
    def __init__(self):
        super().__init__()
        self.put_calls = 0
        self.mapping_calls = []

    def put(self, config, checkpoint, metadata, new_versions):
        self.put_calls += 1
        return super().put(config, checkpoint, metadata, new_versions)

    def save_thread_mapping(self, **kwargs):
        self.mapping_calls.append(dict(kwargs))
        return True


def _build_checkpointed_research_graph(checkpointer, observed):
    builder = StateGraph(MedicalState)

    async def research_node(state, config):
        context = get_research_document_context()
        injected_messages = inject_untrusted_research_documents(
            list(state["messages"]),
            context,
        )
        observed["context"] = context
        observed["secret_seen_in_node_local"] = (
            _TXT_SECRET_SENTINEL in injected_messages[-1].content
        )
        observed["thread_id"] = config["configurable"]["thread_id"]
        return {
            "last_response": "安全科研回答",
            "current_agent": "research",
            "stage": "research_complete",
        }

    builder.add_node("research", research_node)
    builder.add_edge(START, "research")
    builder.add_edge("research", END)
    return builder.compile(checkpointer=checkpointer)


def _serialize_all_checkpoint_tuples(checkpointer):
    listed = tuple(checkpointer.list(None))
    serialized = []
    restored = []
    for checkpoint_tuple in listed:
        restored_tuple = checkpointer.get_tuple(checkpoint_tuple.config)
        restored.append(restored_tuple)
        for candidate in (checkpoint_tuple, restored_tuple):
            format_name, payload = checkpointer.serde.dumps_typed(candidate)
            serialized.append(
                format_name.encode("utf-8")
                + (
                    payload
                    if isinstance(payload, bytes)
                    else str(payload).encode("utf-8")
                )
            )
    return listed, tuple(restored), tuple(serialized)


class _SQLRecorder:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((" ".join(sql.split()), params))
        return 1


def _principal(
    scopes: frozenset[str] = frozenset({"ai:chat"}),
) -> CurrentPrincipal:
    return CurrentPrincipal(
        issuer="java",
        subject="doctor-1",
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=scopes,
        institution_id="institution-1",
        tenant_id="tenant-1",
        authorized_party="eye-agent-platform",
        schema_version=1,
        token_id="jwt-1",
        issued_at=1,
        not_before=1,
        expires_at=9999999999,
    )


async def _collect(stream):
    return [item async for item in stream]


def _research_txt_fixture(root, *, ingestion, graph):
    payload = _TXT_SECRET_SENTINEL.encode("utf-8")
    source = Path(root) / "notes.txt"
    source.write_bytes(payload)
    source.chmod(0o600)
    downloaded = DownloadedAttachment(
        attachment_id="attachment-txt-safe-id",
        analysis_attempt_id="attempt-txt-safe-id",
        file_type="text",
        filename="notes.txt",
        mime_type="text/plain",
        size_bytes=len(payload),
        content_sha256=hashlib.sha256(payload).hexdigest(),
        page_count=None,
        path=source,
        document_version=9,
    )
    request = ExecutePlatformChatTurnRequest(
        version=2,
        request_id="request-txt-safe-id",
        request_fingerprint="a" * 64,
        conversation_id="conversation-txt-safe-id",
        session_id="session-txt-safe-id",
        patient_id=None,
        doctor_id="doctor-1",
        agent_type="research",
        attachment_scope="research",
        research_options={
            "enable_institution_data": False,
            "enable_web_search": False,
            "types": [],
        },
        user_message_id="user-txt-safe-id",
        assistant_message_id="assistant-txt-safe-id",
        attachments=[
            {
                "attachment_id": downloaded.attachment_id,
                "file_type": "text",
                "filename": downloaded.filename,
                "mime_type": downloaded.mime_type,
                "size_bytes": downloaded.size_bytes,
                "page_count": None,
                "content_sha256": downloaded.content_sha256,
                "document_version": downloaded.document_version,
                "analysis_attempt_id": downloaded.analysis_attempt_id,
                "download_url": "https://storage.example/text-file",
            }
        ],
    )
    turn = ChatTurnRequestEntity(
        doctor_id=request.doctor_id,
        request_id=request.request_id,
        request_fingerprint=request.request_fingerprint,
        protocol_version=2,
        agent_type="research",
        attachment_scope="research",
        research_options_json=json.dumps(
            request.research_options.model_dump(mode="json"),
            separators=(",", ":"),
        ),
        operation="normal",
        conversation_id=request.conversation_id,
        session_id=request.session_id,
        patient_id=None,
        attachment_ids_json=json.dumps([downloaded.attachment_id]),
        user_message_id=request.user_message_id,
        assistant_message_id=request.assistant_message_id,
        status="prepared",
    )
    user = SimpleNamespace(
        id=request.user_message_id,
        chat_id=request.conversation_id,
        message_type="user",
        message_content="请总结科研记录",
        parent_id="root",
        status="success",
        deleted=False,
    )
    assistant = SimpleNamespace(
        id=request.assistant_message_id,
        chat_id=request.conversation_id,
        message_type="assistant",
        message_content="",
        parent_id=request.user_message_id,
        status="streaming",
        deleted=False,
        error_message=None,
    )
    conversation = SimpleNamespace(
        id=request.conversation_id,
        host_id=request.doctor_id,
        user_type="doctor",
        active_node_id=request.assistant_message_id,
        summary=None,
        total_messages=0,
    )
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
    turn_repo = _TurnRepository(turn)
    message_repo = _MessageRepository([user, assistant])
    conversation_repo = _ConversationRepository(conversation)
    service = PlatformChatTurnExecutionService(
        db=_DB(),
        turn_repo=turn_repo,
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        downloader=_DownloadedContext(downloaded, settings),
        analyzer=SimpleNamespace(),
        research_ingestion_service=ingestion,
        research_context_selector=_ResearchTextSelector(),
        graph_manager=graph,
        registry=ChatTurnExecutionRegistry(),
        download_settings=settings,
    )
    return SimpleNamespace(
        request=request,
        turn=turn,
        user=user,
        assistant=assistant,
        turn_repo=turn_repo,
        message_repo=message_repo,
        conversation_repo=conversation_repo,
        service=service,
    )


class AttachmentDataLeakageTest(unittest.IsolatedAsyncioTestCase):
    async def test_sensitive_attachment_data_never_reaches_observation_surfaces(self):
        # 安全回归必须使用真实 production parser image；不可用时测试直接失败。
        subprocess.run(
            ["docker", "image", "inspect", _IMAGE],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=10,
        )

        payload = _png_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / f"{_FILENAME_SENTINEL}.png"
            source.write_bytes(payload)
            downloaded = DownloadedAttachment(
                attachment_id="attachment-safe-id",
                analysis_attempt_id="attempt-safe-id",
                file_type="image",
                filename=f"{_FILENAME_SENTINEL}.png",
                mime_type="image/png",
                size_bytes=len(payload),
                content_sha256=hashlib.sha256(payload).hexdigest(),
                page_count=None,
                path=source,
            )

            request = ExecutePlatformChatTurnRequest(
                request_id="request-safe-id",
                request_fingerprint="a" * 64,
                conversation_id="conversation-safe-id",
                session_id="session-safe-id",
                patient_id="patient-safe-id",
                doctor_id="doctor-1",
                user_message_id="user-safe-id",
                assistant_message_id="assistant-safe-id",
                attachments=[
                    {
                        "attachment_id": downloaded.attachment_id,
                        "file_type": "image",
                        "filename": downloaded.filename,
                        "mime_type": downloaded.mime_type,
                        "size_bytes": downloaded.size_bytes,
                        "page_count": None,
                        "content_sha256": downloaded.content_sha256,
                        "document_version": 7,
                        "analysis_attempt_id": downloaded.analysis_attempt_id,
                        "download_url": (
                            "https://storage.example/file?token="
                            + _URL_SENTINEL
                        ),
                    }
                ],
            )
            turn = ChatTurnRequestEntity(
                doctor_id=request.doctor_id,
                request_id=request.request_id,
                request_fingerprint=request.request_fingerprint,
                operation="normal",
                conversation_id=request.conversation_id,
                session_id=request.session_id,
                patient_id=request.patient_id,
                attachment_ids_json=json.dumps([downloaded.attachment_id]),
                user_message_id=request.user_message_id,
                assistant_message_id=request.assistant_message_id,
                status="prepared",
            )
            user = SimpleNamespace(
                id=request.user_message_id,
                chat_id=request.conversation_id,
                message_type="user",
                message_content="请分析附件",
                parent_id="root",
                status="success",
                deleted=False,
            )
            assistant = SimpleNamespace(
                id=request.assistant_message_id,
                chat_id=request.conversation_id,
                message_type="assistant",
                message_content="",
                parent_id=request.user_message_id,
                status="streaming",
                deleted=False,
                error_message=None,
            )
            conversation = SimpleNamespace(
                id=request.conversation_id,
                host_id=request.doctor_id,
                user_type="doctor",
                active_node_id=request.assistant_message_id,
                summary=None,
                total_messages=0,
            )
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
            analyzer = PlatformAttachmentAnalyzer(
                AttachmentParserSandbox(),
                analyze_parsed=lambda parsed: (
                    _PARSED_SENTINEL
                    if parsed.pages and parsed.attachment_id == downloaded.attachment_id
                    else ""
                ),
                timeout_seconds=30,
            )
            graph = _CheckpointGraph()
            turn_repo = _TurnRepository(turn)
            message_repo = _MessageRepository([user, assistant])
            conversation_repo = _ConversationRepository(conversation)
            service = PlatformChatTurnExecutionService(
                db=_DB(),
                turn_repo=turn_repo,
                conversation_repo=conversation_repo,
                message_repo=message_repo,
                downloader=_DownloadedContext(downloaded, settings),
                analyzer=analyzer,
                graph_manager=graph,
                registry=ChatTurnExecutionRegistry(),
                download_settings=settings,
            )

            handler = _LogCapture()
            root_logger = logging.getLogger()
            previous_level = root_logger.level
            root_logger.setLevel(logging.DEBUG)
            root_logger.addHandler(handler)
            try:
                events = await _collect(service.stream(request, _principal()))
                status = PlatformChatTurnService(
                    db=_DB(),
                    turn_repo=turn_repo,
                    conversation_repo=conversation_repo,
                    message_repo=message_repo,
                ).status(request.doctor_id, request.request_id)
            finally:
                root_logger.removeHandler(handler)
                root_logger.setLevel(previous_level)

        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(turn.status, "completed")
        self.assertIsNotNone(graph.observed_analysis)
        self.assertEqual(
            graph.observed_analysis.analyses[0].untrusted_text,
            _PARSED_SENTINEL,
        )

        sql_db = _SQLRecorder()
        sql_repository = object.__new__(ChatMessageRepositoryImpl)
        sql_repository.db = sql_db
        for message_id, updates in message_repo.update_calls:
            self.assertTrue(sql_repository.update(message_id, updates))

        surfaces = {
            "message SQL params": json.dumps(
                sql_db.calls,
                ensure_ascii=False,
                default=str,
            ),
            "checkpoint": json.dumps(
                graph.checkpoint,
                ensure_ascii=False,
                default=str,
            ),
            "SSE": "\n\n".join(
                f"data: {json.dumps(event, ensure_ascii=False)}"
                for event in events
            ),
            "status response": status.model_dump_json(),
            "log": "\n".join(handler.entries),
        }
        for surface_name, observed in surfaces.items():
            for sentinel in _SENTINELS:
                with self.subTest(surface=surface_name, sentinel=sentinel):
                    self.assertNotIn(sentinel, observed)

        self.assertEqual(
            graph.checkpoint,
            {
                "attachments": [
                    {
                        "attachment_id": "attachment-safe-id",
                        "document_version": 7,
                        "content_sha256": hashlib.sha256(payload).hexdigest(),
                        "page_count": None,
                    }
                ],
                "attachment_analysis": None,
            },
        )

    async def test_research_txt_body_is_transient_while_safe_excerpt_survives(self):
        observed = {}

        checkpointer = _RecordingMemorySaver()
        checkpointed_graph = _build_checkpointed_research_graph(
            checkpointer,
            observed,
        )

        manager = object.__new__(GraphManager)
        manager.checkpointer = checkpointer
        manager._build_branch_history_messages = lambda **_kwargs: []
        manager._get_state_message_count = lambda *_args: 0
        ingestion = _ResearchTextIngestion()
        handler = _LogCapture()
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(handler)
        try:
            with tempfile.TemporaryDirectory() as temporary:
                fixture = _research_txt_fixture(
                    temporary,
                    ingestion=ingestion,
                    graph=manager,
                )
                with patch(
                    "agents.graph.graph_builder.get_streaming_medical_graph",
                    return_value=checkpointed_graph,
                ), patch(
                    "utils.role_verification.verify_role",
                    return_value=("doctor", False),
                ):
                    events = await _collect(
                        fixture.service.stream(
                            fixture.request,
                            _principal(frozenset({"ai:research"})),
                        )
                    )
                status = PlatformChatTurnService(
                    db=_DB(),
                    turn_repo=fixture.turn_repo,
                    conversation_repo=fixture.conversation_repo,
                    message_repo=fixture.message_repo,
                ).status("doctor-1", fixture.request.request_id)
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(previous_level)

        self.assertEqual(events[-1]["event"], "done")
        self.assertEqual(
            events[-1]["citations"][0]["excerpt"],
            _SAFE_CITATION_EXCERPT,
        )
        self.assertEqual(
            observed["context"].selection.context_blocks[0].content,
            _TXT_SECRET_SENTINEL,
        )
        self.assertTrue(observed["secret_seen_in_node_local"])
        self.assertEqual(
            [item.file_type for item in ingestion.calls[0][1]],
            ["text"],
        )

        sql_db = _SQLRecorder()
        sql_repository = object.__new__(ChatMessageRepositoryImpl)
        sql_repository.db = sql_db
        for message_id, updates in fixture.message_repo.update_calls:
            self.assertTrue(sql_repository.update(message_id, updates))

        (
            checkpoint_tuples,
            restored_checkpoint_tuples,
            serialized_checkpoint_tuples,
        ) = _serialize_all_checkpoint_tuples(checkpointer)
        self.assertGreater(checkpointer.put_calls, 0)
        self.assertGreater(len(checkpoint_tuples), 0)
        self.assertEqual(len(checkpointer.mapping_calls), 1)
        self.assertTrue(all(restored_checkpoint_tuples))
        secret_bytes = _TXT_SECRET_SENTINEL.encode("utf-8")
        self.assertTrue(
            all(
                secret_bytes not in serialized
                for serialized in serialized_checkpoint_tuples
            )
        )
        self.assertTrue(
            all(
                b"research_document_context_handle" not in serialized
                for serialized in serialized_checkpoint_tuples
            )
        )

        surfaces = {
            "SSE": json.dumps(events, ensure_ascii=False, default=str),
            "history": json.dumps(
                [
                    vars(message)
                    for message in fixture.message_repo.get_by_chat_id(
                        fixture.request.conversation_id
                    )
                ],
                ensure_ascii=False,
                default=str,
            ),
            "message context": str(
                getattr(fixture.assistant, "context", None)
            ),
            "message SQL params": json.dumps(
                sql_db.calls,
                ensure_ascii=False,
                default=str,
            ),
            "checkpoint tuples": b"\n".join(
                serialized_checkpoint_tuples
            ).decode("utf-8", errors="replace"),
            "status": status.model_dump_json(),
            "log": "\n".join(handler.entries),
        }
        for surface_name, surface in surfaces.items():
            with self.subTest(surface=surface_name):
                self.assertNotIn(_TXT_SECRET_SENTINEL, surface)
        self.assertIn(
            _SAFE_CITATION_EXCERPT,
            surfaces["SSE"] + surfaces["message context"],
        )

    async def test_research_txt_completion_abort_race_keeps_body_transient(self):
        for winner in ("completed", "cancelled"):
            with self.subTest(winner=winner):
                observed = {}
                checkpointer = _RecordingMemorySaver()
                checkpointed_graph = _build_checkpointed_research_graph(
                    checkpointer,
                    observed,
                )
                manager = object.__new__(GraphManager)
                manager.checkpointer = checkpointer
                manager._build_branch_history_messages = lambda **_kwargs: []
                manager._get_state_message_count = lambda *_args: 0
                handler = _LogCapture()
                root_logger = logging.getLogger()
                previous_level = root_logger.level
                root_logger.setLevel(logging.DEBUG)
                root_logger.addHandler(handler)
                try:
                    with tempfile.TemporaryDirectory() as temporary:
                        fixture = _research_txt_fixture(
                            temporary,
                            ingestion=_ResearchTextIngestion(),
                            graph=manager,
                        )
                        winner_finished = threading.Event()
                        race_repo = _TerminalRaceTurnRepository(
                            fixture.turn,
                            winner=winner,
                            winner_finished=winner_finished,
                        )
                        fixture.turn_repo = race_repo
                        fixture.service.turn_repo = race_repo
                        abort_service = PlatformChatTurnService(
                            db=fixture.service.db,
                            turn_repo=race_repo,
                            conversation_repo=fixture.conversation_repo,
                            message_repo=fixture.message_repo,
                            chat_persistence_service=(
                                fixture.service.chat_persistence_service
                            ),
                        )
                        finalizer_entered = asyncio.Event()
                        allow_completion_cas = asyncio.Event()
                        real_finalize = (
                            fixture.service.finalize_platform_turn_success
                        )

                        async def wrapped_finalize(*args):
                            finalizer_entered.set()
                            await allow_completion_cas.wait()
                            result = await real_finalize(*args)
                            if winner == "completed":
                                winner_finished.set()
                            return result

                        fixture.service.finalize_platform_turn_success = (
                            wrapped_finalize
                        )

                        def run_abort():
                            try:
                                return abort_service.abort(
                                    "doctor-1",
                                    fixture.request.request_id,
                                    fixture.request.conversation_id,
                                )
                            except Exception as error:
                                return error
                            finally:
                                if winner == "cancelled":
                                    winner_finished.set()

                        with patch(
                            "agents.graph.graph_builder."
                            "get_streaming_medical_graph",
                            return_value=checkpointed_graph,
                        ), patch(
                            "utils.role_verification.verify_role",
                            return_value=("doctor", False),
                        ):
                            stream_task = asyncio.create_task(
                                _collect(
                                    fixture.service.stream(
                                        fixture.request,
                                        _principal(
                                            frozenset({"ai:research"})
                                        ),
                                    )
                                )
                            )
                            await asyncio.wait_for(
                                finalizer_entered.wait(),
                                timeout=3,
                            )
                            self.assertTrue(
                                observed["secret_seen_in_node_local"]
                            )
                            self.assertEqual(
                                observed["context"]
                                .selection.context_blocks[0].content,
                                _TXT_SECRET_SENTINEL,
                            )
                            fixture.service.registry.signal(
                                "doctor-1",
                                fixture.request.request_id,
                            )
                            with ThreadPoolExecutor(
                                max_workers=1
                            ) as executor:
                                abort_future = executor.submit(run_abort)
                                abort_arrived = await asyncio.wait_for(
                                    asyncio.to_thread(
                                        race_repo.abort_arrived.wait,
                                        3,
                                    ),
                                    timeout=4,
                                )
                                self.assertTrue(abort_arrived)
                                allow_completion_cas.set()
                                events = await asyncio.wait_for(
                                    stream_task,
                                    timeout=4,
                                )
                                abort_result = await asyncio.wrap_future(
                                    abort_future
                                )

                        status = abort_service.status(
                            "doctor-1",
                            fixture.request.request_id,
                        )
                finally:
                    root_logger.removeHandler(handler)
                    root_logger.setLevel(previous_level)

                won = [
                    call[1]
                    for call in race_repo.terminal_calls
                    if call[0] == "won"
                ]
                lost = [
                    call[1]
                    for call in race_repo.terminal_calls
                    if call[0] == "lost"
                ]
                self.assertEqual(won, [winner])
                self.assertEqual(
                    lost,
                    ["cancelled" if winner == "completed" else "completed"],
                )
                self.assertEqual(fixture.turn.status, winner)
                self.assertEqual(status.status, winner)
                if winner == "completed":
                    self.assertEqual(fixture.assistant.status, "success")
                    self.assertEqual(events[-1]["event"], "done")
                    self.assertIsInstance(
                        abort_result,
                        TurnAlreadyCompletedError,
                    )
                    self.assertEqual(
                        str(abort_result),
                        "TURN_ALREADY_COMPLETED",
                    )
                else:
                    self.assertEqual(fixture.assistant.status, "cancelled")
                    self.assertEqual(events[-1]["event"], "error")
                    self.assertEqual(
                        events[-1]["error_code"],
                        "TURN_CANCELLED",
                    )
                    self.assertEqual(abort_result.status, "cancelled")

                sql_db = _SQLRecorder()
                sql_repository = object.__new__(ChatMessageRepositoryImpl)
                sql_repository.db = sql_db
                for message_id, updates in fixture.message_repo.update_calls:
                    self.assertTrue(
                        sql_repository.update(message_id, updates)
                    )
                (
                    listed_checkpoints,
                    restored_checkpoints,
                    serialized_checkpoints,
                ) = _serialize_all_checkpoint_tuples(checkpointer)
                self.assertGreater(checkpointer.put_calls, 0)
                self.assertTrue(listed_checkpoints)
                self.assertTrue(all(restored_checkpoints))
                abort_surface = (
                    repr(abort_result)
                    if isinstance(abort_result, Exception)
                    else abort_result.model_dump_json()
                )
                surfaces = {
                    "SSE": json.dumps(events, ensure_ascii=False),
                    "history": json.dumps(
                        [
                            vars(message)
                            for message in fixture.message_repo.get_by_chat_id(
                                fixture.request.conversation_id
                            )
                        ],
                        ensure_ascii=False,
                        default=str,
                    ),
                    "message context": str(
                        getattr(fixture.assistant, "context", None)
                    ),
                    "message SQL params": json.dumps(
                        sql_db.calls,
                        ensure_ascii=False,
                        default=str,
                    ),
                    "status": status.model_dump_json(),
                    "abort result": abort_surface,
                    "log": "\n".join(handler.entries),
                    "checkpoint tuples": b"\n".join(
                        serialized_checkpoints
                    ).decode("utf-8", errors="replace"),
                }
                for surface_name, surface in surfaces.items():
                    with self.subTest(
                        winner=winner,
                        surface=surface_name,
                    ):
                        self.assertNotIn(_TXT_SECRET_SENTINEL, surface)

    async def test_research_txt_failure_redacts_body_from_exception_and_surfaces(self):
        graph = _CheckpointGraph()
        ingestion = _ResearchTextIngestion(fail=True)
        handler = _LogCapture()
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(handler)
        escaped_exception = None
        try:
            with tempfile.TemporaryDirectory() as temporary:
                fixture = _research_txt_fixture(
                    temporary,
                    ingestion=ingestion,
                    graph=graph,
                )
                try:
                    events = await _collect(
                        fixture.service.stream(
                            fixture.request,
                            _principal(frozenset({"ai:research"})),
                        )
                    )
                except Exception as error:  # pragma: no cover - 安全边界断言
                    escaped_exception = repr(error)
                    events = []
                status = PlatformChatTurnService(
                    db=_DB(),
                    turn_repo=fixture.turn_repo,
                    conversation_repo=fixture.conversation_repo,
                    message_repo=fixture.message_repo,
                ).status("doctor-1", fixture.request.request_id)
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(previous_level)

        self.assertIsNone(escaped_exception)
        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(events[-1]["error_code"], "RESEARCH_TXT_PARSE_FAILED")
        self.assertEqual(fixture.turn.status, "failed")
        self.assertEqual(fixture.assistant.status, "failed")
        self.assertIsNone(graph.checkpoint)
        surfaces = json.dumps(
            {
                "SSE": events,
                "history": [
                    vars(message)
                    for message in fixture.message_repo.get_by_chat_id(
                        fixture.request.conversation_id
                    )
                ],
                "message_context": getattr(
                    fixture.assistant, "context", None
                ),
                "checkpoint": graph.checkpoint,
                "status": status.model_dump(mode="json"),
                "log": handler.entries,
                "exception": escaped_exception,
            },
            ensure_ascii=False,
            default=str,
        )
        self.assertNotIn(_TXT_SECRET_SENTINEL, surfaces)

    def test_execute_schema_rejects_inline_base64_payload(self):
        payload = {
            "request_id": "request-safe-id",
            "request_fingerprint": "a" * 64,
            "conversation_id": "conversation-safe-id",
            "session_id": "session-safe-id",
            "patient_id": "patient-safe-id",
            "doctor_id": "doctor-1",
            "user_message_id": "user-safe-id",
            "assistant_message_id": "assistant-safe-id",
            "attachments": [
                {
                    "attachment_id": "attachment-safe-id",
                    "file_type": "image",
                    "filename": "safe.png",
                    "mime_type": "image/png",
                    "size_bytes": 128,
                    "page_count": None,
                    "content_sha256": "b" * 64,
                    "document_version": 1,
                    "analysis_attempt_id": "attempt-safe-id",
                    "download_url": "https://storage.example/file",
                    "base64": _BASE64_SENTINEL,
                }
            ],
        }

        with self.assertRaises(ValidationError):
            ExecutePlatformChatTurnRequest(**payload)


if __name__ == "__main__":
    unittest.main()
