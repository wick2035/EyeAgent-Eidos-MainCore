import hashlib
import io
import json
import logging
import subprocess
import tempfile
import unittest
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from pydantic import ValidationError

from agents.graph_manager import PreparedGraphTerminal
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
from utils.transient_attachment_context import get_attachment_analysis


_IMAGE = "eyeagent/attachment-parser:1"
_URL_SENTINEL = "URL_QUERY_SENTINEL_7f3f7b"
_BASE64_SENTINEL = "BASE64_SENTINEL_c2Vuc2l0aXZl"
_PARSED_SENTINEL = "PARSED_BODY_SENTINEL_0d81d9"
_FILENAME_SENTINEL = "FILENAME_SENTINEL_51e697"
_SENTINELS = (
    _URL_SENTINEL,
    _BASE64_SENTINEL,
    _PARSED_SENTINEL,
    _FILENAME_SENTINEL,
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


class _SQLRecorder:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((" ".join(sql.split()), params))
        return 1


def _principal() -> CurrentPrincipal:
    return CurrentPrincipal(
        issuer="java",
        subject="doctor-1",
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=frozenset({"ai:chat"}),
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
