import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Callable

from agents.graph_manager import PreparedGraphTerminal, get_graph_manager
from application.services.chat_turn_execution_registry import (
    ChatTurnExecutionRegistry,
    get_chat_turn_execution_registry,
)
from application.services.chat_persistence_service import ChatPersistenceService
from application.services.platform_attachment_analyzer import (
    AttachmentStatusUpdate,
    PlatformAttachmentAnalyzer,
)
from application.services.research_document_context_selector import (
    ResearchDocumentContextSelection,
    ResearchDocumentContextSelector,
)
from application.services.research_document_ingestion_service import (
    ResearchDocumentIngestionService,
)
from application.services.research_document_processor import (
    ResearchDocumentProcessor,
)
from domain.models.chat_entity import MessageContext, canonicalize_citations
from domain.security.principal import CurrentPrincipal
from infrastructure.attachments.config import (
    AttachmentConfigurationError,
    AttachmentDownloadSettings,
)
from infrastructure.attachments.parser_sandbox import AttachmentParserSandbox
from infrastructure.attachments.secure_downloader import SecureAttachmentDownloader
from infrastructure.database.mysql_connection import get_db_connection
from infrastructure.repositories.chat_repository_impl import (
    get_conversation_repository,
    get_message_repository,
)
from infrastructure.repositories.chat_turn_request_repository_impl import (
    get_chat_turn_request_repository,
)
from infrastructure.repositories.research_document_repository_impl import (
    get_research_document_repository,
)
from presentation.dependencies.security import scope_for_platform_agent
from presentation.schemas.platform_chat_turn_schemas import (
    ExecutePlatformChatTurnRequest,
)
from utils.transient_attachment_context import (
    TransientAttachmentContext,
    TransientResearchDocumentContext,
    bind_attachment_analysis,
    bind_research_document_context,
    reset_attachment_analysis,
    reset_research_document_context,
)


ATTACHMENT_EXECUTE_MISMATCH = "ATTACHMENT_EXECUTE_MISMATCH"
_TURN_NOT_FOUND = "CHAT_TURN_NOT_FOUND"
_EXECUTION_CONFLICT = "TURN_EXECUTION_CONFLICT"
_TURN_TIMEOUT = "ATTACHMENT_ANALYSIS_TIMEOUT"
_SAFE_ERROR = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_TERMINAL = frozenset({"completed", "failed", "cancelled"})
_DEADLINE_SECONDS = 15 * 60
_HEARTBEAT_SECONDS = 30.0
_FORBIDDEN_PERSISTED_MARKERS = (
    "download_url",
    "base64",
    "page_images",
    "storage_key",
    "untrusted_text",
    "filename",
    "file_name",
    "original_name",
)


class PlatformPrincipalError(PermissionError):
    pass


class _ExecutionStopped(RuntimeError):
    pass


@dataclass(frozen=True)
class PlatformTurnFinalizeResult:
    request_id: str
    user_message_id: str
    assistant_message_id: str
    status: str
    error_code: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)


class PlatformChatTurnExecutionService:
    """附件回合 execute、模型流与原子终态的唯一编排者。"""

    def __init__(
        self,
        *,
        db=None,
        turn_repo=None,
        conversation_repo=None,
        message_repo=None,
        chat_persistence_service=None,
        downloader=None,
        analyzer=None,
        research_ingestion_service=None,
        research_context_selector=None,
        graph_manager=None,
        registry: ChatTurnExecutionRegistry | None = None,
        download_settings: AttachmentDownloadSettings | None = None,
        now: Callable[[], datetime] = datetime.now,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Any] = asyncio.sleep,
        heartbeat_interval: float = _HEARTBEAT_SECONDS,
    ) -> None:
        self.db = db or get_db_connection()
        self.turn_repo = turn_repo or get_chat_turn_request_repository()
        self.conversation_repo = conversation_repo or get_conversation_repository()
        self.message_repo = message_repo or get_message_repository()
        self.chat_persistence_service = (
            chat_persistence_service
            or ChatPersistenceService(
                self.conversation_repo,
                self.message_repo,
                db=self.db,
            )
        )
        self.download_settings = download_settings
        if downloader is None:
            settings = download_settings or AttachmentDownloadSettings.from_env()
            downloader = SecureAttachmentDownloader(settings)
            self.download_settings = settings
        elif self.download_settings is None:
            self.download_settings = getattr(downloader, "_settings", None)
        self.downloader = downloader
        self.analyzer = analyzer or PlatformAttachmentAnalyzer(
            AttachmentParserSandbox()
        )
        research_repository = (
            get_research_document_repository()
            if research_ingestion_service is None
            or research_context_selector is None
            else None
        )
        self.research_ingestion_service = (
            research_ingestion_service
            or ResearchDocumentIngestionService(
                repository=research_repository,
                processor=ResearchDocumentProcessor(
                    AttachmentParserSandbox()
                ),
            )
        )
        self.research_context_selector = (
            research_context_selector
            or ResearchDocumentContextSelector(research_repository)
        )
        self.graph_manager = graph_manager or get_graph_manager()
        self.registry = registry or get_chat_turn_execution_registry()
        self._now = now
        self._clock = clock
        self._sleep = sleep
        self._heartbeat_interval = heartbeat_interval
        self._active_doctors: dict[tuple[str, str], str] = {}

    async def stream(
        self,
        request: ExecutePlatformChatTurnRequest,
        principal: CurrentPrincipal,
    ) -> AsyncGenerator[dict, None]:
        self._require_principal(
            principal,
            request.doctor_id,
            request.agent_type or "health",
        )
        try:
            self._validate_urls(request)
            turn, user_message = self._claim_prepared_turn(request, principal.subject)
        except _ExecuteRejected as exc:
            yield self._error_event(request, exc.error_code)
            return

        cancel_event = self.registry.register(
            principal.subject,
            request.request_id,
        )
        active_key = (request.request_id, request.assistant_message_id)
        self._active_doctors[active_key] = principal.subject
        binding = None
        analysis_task = None
        graph_stream = None
        finalized = False
        deadline = self._clock() + _DEADLINE_SECONDS
        sequence = {item.attachment_id: 0 for item in request.attachments}
        descriptors = {item.attachment_id: item for item in request.attachments}

        try:
            await self._ensure_running(principal.subject, request.request_id, cancel_event)
            yield {
                "event": "execution_started",
                "request_id": request.request_id,
                "user_message_id": request.user_message_id,
                "assistant_message_id": request.assistant_message_id,
            }
            async with self.downloader.download_all(
                request.attachments,
                request.request_id,
            ) as downloaded:
                queue: asyncio.Queue[AttachmentStatusUpdate] = asyncio.Queue()

                async def on_status(update: AttachmentStatusUpdate) -> None:
                    # processing/heartbeat 由本服务按 descriptor 顺序统一产生。
                    if update.status != "processing":
                        await queue.put(update)

                for descriptor in request.attachments:
                    self._ensure_before_deadline(deadline)
                    await self._ensure_running(
                        principal.subject,
                        request.request_id,
                        cancel_event,
                    )
                    sequence[descriptor.attachment_id] += 1
                    yield {
                        "event": "attachment_status",
                        "request_id": request.request_id,
                        "user_message_id": request.user_message_id,
                        "assistant_message_id": request.assistant_message_id,
                        "attachment_id": descriptor.attachment_id,
                        "analysis_attempt_id": descriptor.analysis_attempt_id,
                        "sequence": sequence[descriptor.attachment_id],
                        "status": "processing",
                        "error_code": None,
                    }

                if turn.agent_type == "research":
                    analysis_task = asyncio.create_task(
                        self._prepare_research_documents(
                            principal.subject,
                            downloaded,
                            user_message.message_content,
                            deadline,
                        )
                    )
                    try:
                        while not analysis_task.done():
                            heartbeat_due = await self._wait_until_activity(
                                analysis_task,
                                queue,
                                cancel_event,
                                deadline,
                            )
                            if heartbeat_due:
                                for descriptor in request.attachments:
                                    self._ensure_before_deadline(deadline)
                                    await self._ensure_running(
                                        principal.subject,
                                        request.request_id,
                                        cancel_event,
                                    )
                                    sequence[descriptor.attachment_id] += 1
                                    yield {
                                        "event": "attachment_status",
                                        "request_id": request.request_id,
                                        "user_message_id": request.user_message_id,
                                        "assistant_message_id": request.assistant_message_id,
                                        "attachment_id": descriptor.attachment_id,
                                        "analysis_attempt_id": descriptor.analysis_attempt_id,
                                        "sequence": sequence[descriptor.attachment_id],
                                        "status": "processing",
                                        "error_code": None,
                                    }
                        ingestion_ids, entities, selection = (
                            await self._await_deadline(analysis_task, deadline)
                        )
                    except (_ExecutionStopped, asyncio.TimeoutError, TimeoutError):
                        raise
                    except Exception as error:
                        error_code = self.safe_error_code(error)
                        for descriptor in request.attachments:
                            sequence[descriptor.attachment_id] += 1
                            yield {
                                "event": "attachment_status",
                                "request_id": request.request_id,
                                "user_message_id": request.user_message_id,
                                "assistant_message_id": request.assistant_message_id,
                                "attachment_id": descriptor.attachment_id,
                                "analysis_attempt_id": descriptor.analysis_attempt_id,
                                "sequence": sequence[descriptor.attachment_id],
                                "status": "failed",
                                "error_code": error_code,
                            }
                        raise
                    for descriptor in request.attachments:
                        sequence[descriptor.attachment_id] += 1
                        yield {
                            "event": "attachment_status",
                            "request_id": request.request_id,
                            "user_message_id": request.user_message_id,
                            "assistant_message_id": request.assistant_message_id,
                            "attachment_id": descriptor.attachment_id,
                            "analysis_attempt_id": descriptor.analysis_attempt_id,
                            "sequence": sequence[descriptor.attachment_id],
                            "status": "ready",
                            "error_code": None,
                        }
                    if not self.turn_repo.compare_and_set_ingestion_ids(
                        principal.subject,
                        request.request_id,
                        "streaming",
                        ingestion_ids,
                    ):
                        error = RuntimeError(
                            "RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE"
                        )
                        error.error_code = (
                            "RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE"
                        )
                        raise error
                    context = TransientResearchDocumentContext(
                        implicit_prompt_id=turn.implicit_prompt_id,
                        selection=selection,
                    )
                else:
                    analysis_task = asyncio.create_task(
                        self.analyzer.analyze_all(downloaded, on_status)
                    )
                    terminal_attachments: set[str] = set()
                    while not analysis_task.done() or not queue.empty():
                        heartbeat_due = False
                        if queue.empty():
                            heartbeat_due = await self._wait_until_activity(
                                analysis_task,
                                queue,
                                cancel_event,
                                deadline,
                            )
                        while not queue.empty():
                            update = queue.get_nowait()
                            self._ensure_before_deadline(deadline)
                            if (
                                update.attachment_id not in descriptors
                                or update.status not in {"ready", "failed"}
                            ):
                                error = RuntimeError(
                                    "ATTACHMENT_CONTEXT_INCONSISTENT"
                                )
                                error.error_code = (
                                    "ATTACHMENT_CONTEXT_INCONSISTENT"
                                )
                                raise error
                            await self._ensure_running(
                                principal.subject,
                                request.request_id,
                                cancel_event,
                            )
                            descriptor = descriptors[update.attachment_id]
                            terminal_attachments.add(update.attachment_id)
                            error_code = (
                                self.safe_error_code_value(update.error_code)
                                if update.status == "failed"
                                else None
                            )
                            sequence[update.attachment_id] += 1
                            yield {
                                "event": "attachment_status",
                                "request_id": request.request_id,
                                "user_message_id": request.user_message_id,
                                "assistant_message_id": request.assistant_message_id,
                                "attachment_id": update.attachment_id,
                                "analysis_attempt_id": descriptor.analysis_attempt_id,
                                "sequence": sequence[update.attachment_id],
                                "status": update.status,
                                "error_code": error_code,
                            }
                        if heartbeat_due:
                            for descriptor in request.attachments:
                                if descriptor.attachment_id in terminal_attachments:
                                    continue
                                self._ensure_before_deadline(deadline)
                                await self._ensure_running(
                                    principal.subject,
                                    request.request_id,
                                    cancel_event,
                                )
                                sequence[descriptor.attachment_id] += 1
                                yield {
                                    "event": "attachment_status",
                                    "request_id": request.request_id,
                                    "user_message_id": request.user_message_id,
                                    "assistant_message_id": request.assistant_message_id,
                                    "attachment_id": descriptor.attachment_id,
                                    "analysis_attempt_id": descriptor.analysis_attempt_id,
                                    "sequence": sequence[descriptor.attachment_id],
                                    "status": "processing",
                                    "error_code": None,
                                }
                    analyses = await self._await_deadline(
                        analysis_task,
                        deadline,
                    )
                    if [item.attachment_id for item in analyses] != [
                        item.attachment_id for item in request.attachments
                    ]:
                        error = RuntimeError(
                            "ATTACHMENT_CONTEXT_INCONSISTENT"
                        )
                        error.error_code = "ATTACHMENT_CONTEXT_INCONSISTENT"
                        raise error
                    context = TransientAttachmentContext(
                        implicit_prompt_id=turn.implicit_prompt_id,
                        analyses=tuple(analyses),
                    )

            runnable_config: dict[str, Any] = {}
            if turn.agent_type == "research":
                binding = bind_research_document_context(
                    context,
                    runnable_config,
                )
            else:
                binding = bind_attachment_analysis(context, runnable_config)
            terminal: PreparedGraphTerminal | None = None
            safe_refs = [
                {
                    "attachment_id": item.attachment_id,
                    "document_version": item.document_version,
                    "content_sha256": item.content_sha256,
                    "page_count": item.page_count,
                }
                for item in request.attachments
            ]
            graph_stream = self.graph_manager.chat_stream_prepared_async(
                patient_id=request.patient_id,
                doctor_id=principal.subject,
                session_id=request.session_id,
                conversation_id=request.conversation_id,
                message=user_message.message_content,
                user_message_id=request.user_message_id,
                assistant_message_id=request.assistant_message_id,
                safe_attachment_refs=safe_refs,
                agent_type=turn.agent_type,
                research_options=turn.research_options,
                health_handle=(
                    binding.handle if turn.agent_type == "health" else None
                ),
                research_handle=(
                    binding.handle if turn.agent_type == "research" else None
                ),
                runnable_config=runnable_config,
            )
            while True:
                try:
                    event = await self._next_graph_event(
                        graph_stream,
                        cancel_event,
                        deadline,
                    )
                except StopAsyncIteration:
                    break
                if isinstance(event, PreparedGraphTerminal):
                    terminal = event
                    continue
                public = self._public_graph_event(event, request)
                if public is None:
                    continue
                self._ensure_before_deadline(deadline)
                await self._ensure_running(
                    principal.subject,
                    request.request_id,
                    cancel_event,
                )
                yield public
            if terminal is None:
                raise RuntimeError("PREPARED_GRAPH_TERMINAL_MISSING")
            result = await self.finalize_platform_turn_success(
                request.request_id,
                request.assistant_message_id,
                terminal,
            )
            finalized = True
            yield self.build_public_terminal_event(result)
        except (asyncio.CancelledError, GeneratorExit):
            if not finalized:
                await self.finalize_platform_turn_cancelled(
                    request.request_id,
                    request.assistant_message_id,
                )
            raise
        except _ExecutionStopped:
            if not finalized:
                result = await self.finalize_platform_turn_cancelled(
                    request.request_id,
                    request.assistant_message_id,
                )
                finalized = True
                if result.status in {"failed", "completed"}:
                    yield self.build_public_terminal_event(result)
        except (asyncio.TimeoutError, TimeoutError):
            result = await self.finalize_platform_turn_failure(
                request.request_id,
                request.assistant_message_id,
                _TURN_TIMEOUT,
            )
            finalized = True
            yield self.build_public_terminal_event(result)
        except Exception as exc:
            result = await self.finalize_platform_turn_failure(
                request.request_id,
                request.assistant_message_id,
                self.safe_error_code(exc),
            )
            finalized = True
            yield self.build_public_terminal_event(result)
        finally:
            if graph_stream is not None:
                try:
                    await graph_stream.aclose()
                except BaseException:
                    pass
            if analysis_task is not None:
                if not analysis_task.done():
                    analysis_task.cancel()
                await asyncio.gather(analysis_task, return_exceptions=True)
            if binding is not None:
                if turn.agent_type == "research":
                    reset_research_document_context(binding)
                else:
                    reset_attachment_analysis(binding)
            self.registry.unregister(
                principal.subject,
                request.request_id,
                cancel_event,
            )
            self._active_doctors.pop(active_key, None)

    async def _prepare_research_documents(
        self,
        doctor_id: str,
        downloaded,
        question: str,
        deadline: float,
    ):
        result = await self.research_ingestion_service.ingest(
            doctor_id,
            downloaded,
            deadline=deadline,
        )
        try:
            entities = tuple(result.entities)
            ingestion_ids = tuple(result.ingestion_ids)
            exact = (
                1 <= len(ingestion_ids) <= 4
                and len(entities) == len(ingestion_ids)
                and len(set(ingestion_ids)) == len(ingestion_ids)
                and all(
                    isinstance(ingestion_id, str)
                    and ingestion_id
                    and getattr(entity, "id", None) == ingestion_id
                    for ingestion_id, entity in zip(ingestion_ids, entities)
                )
            )
        except Exception:
            exact = False
        if not exact:
            error = RuntimeError("RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE")
            error.error_code = "RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE"
            raise error
        ready_map = {
            ingestion_id: entity
            for ingestion_id, entity in zip(ingestion_ids, entities)
        }
        selection = await self.research_context_selector.select(
            ingestion_ids,
            ready_map,
            question,
        )
        if not isinstance(selection, ResearchDocumentContextSelection):
            error = RuntimeError("RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE")
            error.error_code = "RESEARCH_DOCUMENT_CONTEXT_UNAVAILABLE"
            raise error
        return ingestion_ids, entities, selection

    async def finalize_platform_turn_success(
        self,
        request_id: str,
        assistant_message_id: str,
        terminal: PreparedGraphTerminal,
    ) -> PlatformTurnFinalizeResult:
        canonical_citations = canonicalize_citations(
            terminal.citations,
            drop_invalid=True,
        )
        return self._finalize(
            request_id,
            assistant_message_id,
            "completed",
            content=terminal.content,
            token_used=terminal.token_used,
            context=MessageContext(
                conversation_stage=terminal.stage,
                tool_results=self._sanitize_persisted_metadata(
                    terminal.tool_results
                ) or None,
                citations=canonical_citations or None,
                metadata={"agent_type": terminal.agent_type},
            ),
            citations=canonical_citations,
        )

    async def finalize_platform_turn_failure(
        self,
        request_id: str,
        assistant_message_id: str,
        error_code: str,
    ) -> PlatformTurnFinalizeResult:
        return self._finalize(
            request_id,
            assistant_message_id,
            "failed",
            error_code=self.safe_error_code_value(error_code),
        )

    async def finalize_platform_turn_cancelled(
        self,
        request_id: str,
        assistant_message_id: str,
    ) -> PlatformTurnFinalizeResult:
        return self._finalize(
            request_id,
            assistant_message_id,
            "cancelled",
        )

    def _finalize(
        self,
        request_id: str,
        assistant_message_id: str,
        status: str,
        *,
        content: str | None = None,
        token_used: int | None = None,
        context: MessageContext | None = None,
        error_code: str | None = None,
        citations: list[dict[str, Any]] | None = None,
    ) -> PlatformTurnFinalizeResult:
        doctor_id = self._active_doctors.get((request_id, assistant_message_id))
        if not doctor_id:
            raise RuntimeError("PLATFORM_TURN_CONTEXT_MISSING")
        with self.db.transaction():
            entity = self.turn_repo.get_for_update(doctor_id, request_id)
            if entity is None or entity.assistant_message_id != assistant_message_id:
                raise RuntimeError(_TURN_NOT_FOUND)
            if entity.status in _TERMINAL:
                return self._finalize_result(
                    entity,
                    self._persisted_assistant_citations(
                        entity.assistant_message_id
                    ),
                )
            if entity.status != "streaming":
                raise RuntimeError("INVALID_TURN_STATE")
            changed = self.turn_repo.compare_and_set_status(
                doctor_id,
                request_id,
                "streaming",
                status,
                error_code=error_code,
            )
            if not changed:
                latest = self.turn_repo.get_for_update(doctor_id, request_id)
                if latest is None:
                    raise RuntimeError(_TURN_NOT_FOUND)
                return self._finalize_result(
                    latest,
                    self._persisted_assistant_citations(
                        latest.assistant_message_id
                    ),
                )
            if context is not None:
                context = self._completion_context(entity, context)
            if not self.chat_persistence_service.finalize_platform_assistant(
                assistant_message_id,
                status="success" if status == "completed" else status,
                content=content,
                token_used=token_used,
                context=context,
                error_message=error_code,
            ):
                raise RuntimeError("ASSISTANT_FINALIZE_FAILED")
            latest = self.turn_repo.get_for_update(doctor_id, request_id) or entity
            latest.status = status
            latest.error_code = error_code
            return self._finalize_result(latest, citations)

    def _claim_prepared_turn(self, request, doctor_id):
        prefetched = self._get_turn(doctor_id, request.request_id)
        if prefetched is None:
            raise _ExecuteRejected(_TURN_NOT_FOUND)
        self._assert_request_matches(prefetched, request)
        with self.db.transaction():
            conversation = self._lock_conversation(request.conversation_id)
            if (
                getattr(conversation, "host_id", None) != doctor_id
                or getattr(conversation, "user_type", None) != "doctor"
                or getattr(conversation, "active_node_id", None)
                != request.assistant_message_id
            ):
                raise _ExecuteRejected(_TURN_NOT_FOUND)
            entity = self.turn_repo.get_for_update(doctor_id, request.request_id)
            if entity is None:
                raise _ExecuteRejected(_TURN_NOT_FOUND)
            self._assert_request_matches(entity, request)
            user = self.message_repo.get_by_id(request.user_message_id)
            assistant = self.message_repo.get_by_id(request.assistant_message_id)
            if (
                user is None
                or assistant is None
                or user.chat_id != request.conversation_id
                or assistant.chat_id != request.conversation_id
                or user.message_type != "user"
                or assistant.message_type != "assistant"
                or assistant.parent_id != user.id
                or getattr(user, "status", None) != "success"
                or getattr(assistant, "status", None) != "streaming"
                or bool(getattr(user, "deleted", False))
                or bool(getattr(assistant, "deleted", False))
            ):
                raise _ExecuteRejected(ATTACHMENT_EXECUTE_MISMATCH)
            if entity.status != "prepared":
                raise _ExecuteRejected(_EXECUTION_CONFLICT)
            started_at = self._now()
            changed = self.turn_repo.compare_and_set_status(
                doctor_id,
                request.request_id,
                "prepared",
                "streaming",
                execute_started_at=started_at,
                deadline_at=started_at + timedelta(minutes=15),
            )
            if not changed:
                raise _ExecuteRejected(_EXECUTION_CONFLICT)
            return entity, user

    @staticmethod
    def _assert_request_matches(entity, request) -> None:
        try:
            stored_attachment_ids = entity.attachment_ids
            stored_research_options = entity.research_options
        except (TypeError, ValueError):
            raise _ExecuteRejected(ATTACHMENT_EXECUTE_MISMATCH)
        request_research_options = (
            request.research_options.model_dump(mode="json")
            if request.research_options is not None
            else None
        )
        exact = (
            entity.request_fingerprint == request.request_fingerprint
            and entity.protocol_version == request.version
            and entity.agent_type == (request.agent_type or "health")
            and entity.attachment_scope
            == (request.attachment_scope or "patient")
            and stored_research_options == request_research_options
            and entity.conversation_id == request.conversation_id
            and entity.session_id == request.session_id
            and entity.patient_id == request.patient_id
            and entity.doctor_id == request.doctor_id
            and entity.user_message_id == request.user_message_id
            and entity.assistant_message_id == request.assistant_message_id
            and stored_attachment_ids
            == [item.attachment_id for item in request.attachments]
        )
        if not exact:
            raise _ExecuteRejected(ATTACHMENT_EXECUTE_MISMATCH)

    def _validate_urls(self, request: ExecutePlatformChatTurnRequest) -> None:
        attachment_ids = [item.attachment_id for item in request.attachments]
        attempt_ids = [item.analysis_attempt_id for item in request.attachments]
        if (
            len(set(attachment_ids)) != len(attachment_ids)
            or len(set(attempt_ids)) != len(attempt_ids)
            or any(not value.strip() for value in attachment_ids)
            or any(not value.strip() for value in attempt_ids)
        ):
            raise _ExecuteRejected(ATTACHMENT_EXECUTE_MISMATCH)
        if self.download_settings is None:
            raise _ExecuteRejected("ATTACHMENT_URL_REJECTED")
        try:
            for descriptor in request.attachments:
                self.download_settings.endpoints_for_url(descriptor.download_url)
        except AttachmentConfigurationError as exc:
            raise _ExecuteRejected("ATTACHMENT_URL_REJECTED") from exc

    async def _ensure_running(self, doctor_id, request_id, event) -> None:
        if event.is_set():
            raise _ExecutionStopped()
        entity = self._get_turn(doctor_id, request_id)
        if entity is None or entity.status != "streaming":
            raise _ExecutionStopped()

    async def _wait_until_activity(
        self,
        task,
        queue,
        cancel_event,
        deadline,
    ) -> bool:
        queue_task = asyncio.create_task(queue.get())
        cancel_task = asyncio.create_task(cancel_event.wait())
        heartbeat_task = asyncio.create_task(
            self._sleep(self._heartbeat_interval)
        )
        try:
            done, _ = await self._await_deadline(
                asyncio.wait(
                    {task, queue_task, cancel_task, heartbeat_task},
                    return_when=asyncio.FIRST_COMPLETED,
                ),
                deadline,
            )
            if cancel_task in done and cancel_task.result():
                if task.done():
                    await asyncio.gather(task, return_exceptions=True)
                raise _ExecutionStopped()
            if queue_task in done:
                queue.put_nowait(queue_task.result())
            return heartbeat_task in done
        finally:
            for pending in (queue_task, cancel_task, heartbeat_task):
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(
                queue_task,
                cancel_task,
                heartbeat_task,
                return_exceptions=True,
            )

    async def _next_graph_event(self, stream, cancel_event, deadline):
        next_task = asyncio.create_task(stream.__anext__())
        cancel_task = asyncio.create_task(cancel_event.wait())
        try:
            done, _ = await self._await_deadline(
                asyncio.wait(
                    {next_task, cancel_task},
                    return_when=asyncio.FIRST_COMPLETED,
                ),
                deadline,
            )
            if cancel_task in done and cancel_task.result():
                if not next_task.done():
                    next_task.cancel()
                await asyncio.gather(next_task, return_exceptions=True)
                raise _ExecutionStopped()
            return next_task.result()
        finally:
            if not next_task.done():
                next_task.cancel()
                await asyncio.gather(next_task, return_exceptions=True)
            if not cancel_task.done():
                cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)

    async def _await_deadline(self, awaitable, deadline):
        remaining = deadline - self._clock()
        if remaining <= 0:
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise asyncio.TimeoutError()
        return await asyncio.wait_for(awaitable, timeout=remaining)

    def _ensure_before_deadline(self, deadline: float) -> None:
        if self._clock() >= deadline:
            raise asyncio.TimeoutError()

    def _get_turn(self, doctor_id, request_id):
        getter = getattr(self.turn_repo, "get", None)
        return (
            getter(doctor_id, request_id)
            if getter is not None
            else self.turn_repo.get_for_update(doctor_id, request_id)
        )

    def _lock_conversation(self, conversation_id):
        locker = getattr(self.conversation_repo, "lock_by_id", None)
        conversation = (
            locker(conversation_id)
            if locker is not None
            else self.conversation_repo.get_by_id(conversation_id)
        )
        if conversation is None:
            raise _ExecuteRejected(_TURN_NOT_FOUND)
        return conversation

    @staticmethod
    def _require_principal(principal, doctor_id, agent_type):
        try:
            required_scope = scope_for_platform_agent(agent_type)
        except ValueError as exc:
            raise PlatformPrincipalError("PLATFORM_DOCTOR_FORBIDDEN") from exc
        if (
            not isinstance(principal, CurrentPrincipal)
            or principal.principal_type != "doctor"
            or required_scope not in principal.scopes
            or principal.subject != doctor_id
        ):
            raise PlatformPrincipalError("PLATFORM_DOCTOR_FORBIDDEN")

    @staticmethod
    def _public_graph_event(event, request):
        if not isinstance(event, dict) or event.get("type") != "token":
            return None
        content = event.get("content")
        if not isinstance(content, str) or not content:
            return None
        return {
            "event": "token",
            "request_id": request.request_id,
            "user_message_id": request.user_message_id,
            "assistant_message_id": request.assistant_message_id,
            "content": content,
        }

    @staticmethod
    def build_public_terminal_event(result: PlatformTurnFinalizeResult) -> dict:
        event = {
            "event": "done" if result.status == "completed" else "error",
            "request_id": result.request_id,
            "user_message_id": result.user_message_id,
            "assistant_message_id": result.assistant_message_id,
        }
        if result.status != "completed":
            event["error_code"] = result.error_code or (
                "TURN_CANCELLED" if result.status == "cancelled" else "ATTACHMENT_ANALYSIS_FAILED"
            )
        else:
            event["citations"] = result.citations
        return event

    @staticmethod
    def _error_event(request, error_code):
        return {
            "event": "error",
            "request_id": request.request_id,
            "user_message_id": request.user_message_id,
            "assistant_message_id": request.assistant_message_id,
            "error_code": error_code,
        }

    @staticmethod
    def safe_error_code(exc: Exception) -> str:
        return PlatformChatTurnExecutionService.safe_error_code_value(
            getattr(exc, "error_code", None)
        )

    @staticmethod
    def safe_error_code_value(value: Any) -> str:
        return value if isinstance(value, str) and _SAFE_ERROR.fullmatch(value) else "ATTACHMENT_ANALYSIS_FAILED"

    @staticmethod
    def _finalize_result(
        entity,
        citations: list[dict[str, Any]] | None = None,
    ) -> PlatformTurnFinalizeResult:
        return PlatformTurnFinalizeResult(
            request_id=entity.request_id,
            user_message_id=entity.user_message_id,
            assistant_message_id=entity.assistant_message_id,
            status=entity.status,
            error_code=entity.error_code,
            citations=list(citations or []),
        )

    @staticmethod
    def _completion_context(entity, context: MessageContext) -> MessageContext:
        if entity.operation != "regenerate":
            return context
        metadata = dict(context.metadata or {})
        metadata.update(
            {
                "attachment_ids": list(entity.attachment_ids),
                "turn_configuration": {
                    "protocol_version": entity.protocol_version,
                    "agent_type": entity.agent_type,
                    "attachment_scope": entity.attachment_scope,
                    "research_options": entity.research_options,
                },
            }
        )
        if entity.attachment_only:
            metadata.update(
                {
                    "attachment_only": True,
                    "implicit_prompt_id": entity.implicit_prompt_id,
                }
            )
        return context.model_copy(update={"metadata": metadata})

    def _persisted_assistant_citations(
        self,
        assistant_message_id: str,
    ) -> list[dict[str, Any]]:
        """竞态失败时只从已落库 assistant context 恢复引用。"""
        try:
            message = self.message_repo.get_by_id(assistant_message_id)
            raw_context = getattr(message, "context", None)
            if isinstance(raw_context, str):
                raw_context = json.loads(raw_context)
            if not isinstance(raw_context, list):
                return []
            context = MessageContext.from_context_list(raw_context)
            return list(context.citations or [])
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    @staticmethod
    def _sanitize_persisted_metadata(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): PlatformChatTurnExecutionService._sanitize_persisted_metadata(item)
                for key, item in value.items()
                if not any(
                    marker in str(key).lower()
                    for marker in _FORBIDDEN_PERSISTED_MARKERS
                )
            }
        if isinstance(value, (list, tuple)):
            return [
                PlatformChatTurnExecutionService._sanitize_persisted_metadata(item)
                for item in value
            ]
        if isinstance(value, str) and any(
            marker in value.lower() for marker in _FORBIDDEN_PERSISTED_MARKERS
        ):
            return "[REDACTED]"
        return value


class _ExecuteRejected(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


_execution_service: PlatformChatTurnExecutionService | None = None


def get_platform_chat_turn_execution_service() -> PlatformChatTurnExecutionService:
    global _execution_service
    if _execution_service is None:
        _execution_service = PlatformChatTurnExecutionService()
    return _execution_service


__all__ = [
    "ATTACHMENT_EXECUTE_MISMATCH",
    "PlatformChatTurnExecutionService",
    "PlatformTurnFinalizeResult",
    "get_platform_chat_turn_execution_service",
]
