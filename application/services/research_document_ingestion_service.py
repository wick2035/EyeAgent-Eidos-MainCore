import asyncio
import copy
import hashlib
import inspect
import math
import os
import re
import stat
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from application.services.research_document_segmenter import (
    SEGMENT_SCHEMA_VERSION,
    ResearchDocumentSegmenter,
)
from domain.models.research_document import (
    IngestionIdentity,
    ResearchDocumentIngestionEntity,
    build_research_document_ingestion_id,
)
from infrastructure.attachments.secure_downloader import DownloadedAttachment
from infrastructure.repositories.research_document_repository_impl import (
    ResearchDocumentFencingError,
)


PDF_EXTRACTOR_VERSION = "pymupdf_v1"
IMAGE_EXTRACTOR_VERSION = "research_vision_v1"
TEXT_EXTRACTOR_VERSION = "research_text_v1"
DOCX_EXTRACTOR_VERSION = "research_docx_v1"

_PROCESSOR_BY_FILE_TYPE = {
    "pdf": "pdf_hybrid_v1",
    "image": "image_vision_v1",
    "text": "plain_text_v1",
    "docx": "docx_text_v1",
}
_EXTRACTOR_BY_PROCESSOR = {
    "pdf_hybrid_v1": PDF_EXTRACTOR_VERSION,
    "image_vision_v1": IMAGE_EXTRACTOR_VERSION,
    "plain_text_v1": TEXT_EXTRACTOR_VERSION,
    "docx_text_v1": DOCX_EXTRACTOR_VERSION,
}

_MAX_FILES = 4
_MAX_TOTAL_BYTES = 40 * 1024 * 1024
_MAX_PDF_BYTES = 30 * 1024 * 1024
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_TEXT_BYTES = 512 * 1024
_MAX_DOCX_BYTES = 10 * 1024 * 1024
_DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_MAX_PDF_PAGES = 100
_MAX_TOTAL_PDF_PAGES = 120
_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_SAFE_ERROR = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SAFE_ERROR_PREFIXES = (
    "ATTACHMENT_",
    "PDF_",
    "RESEARCH_PDF_",
    "RESEARCH_TXT_",
    "RESEARCH_DOCX_",
    "RESEARCH_DOCUMENT_",
)
_INGESTION_TIMEOUT = "RESEARCH_DOCUMENT_INGESTION_TIMEOUT"
_LEGACY_ERROR_ALIASES = {
    "RESEARCH_DOCUMENT_DEADLINE_EXCEEDED": _INGESTION_TIMEOUT,
}


class ResearchDocumentIngestionError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        error_code = _LEGACY_ERROR_ALIASES.get(error_code, error_code)
        if not _SAFE_ERROR.fullmatch(error_code):
            raise ValueError("科研文档摄取错误码无效")
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class ResearchDocumentIngestionResult:
    entities: tuple[ResearchDocumentIngestionEntity, ...]

    def __post_init__(self) -> None:
        if not self.entities or not all(
            isinstance(entity, ResearchDocumentIngestionEntity)
            and entity.status == "ready"
            for entity in self.entities
        ):
            raise ValueError("摄取结果必须全部为 ready")

    @property
    def ingestion_ids(self) -> tuple[str, ...]:
        return tuple(entity.id for entity in self.entities)


class _LeaseLost(RuntimeError):
    pass


class ResearchDocumentIngestionService:
    def __init__(
        self,
        *,
        repository: Any,
        processor: Any,
        segmenter: ResearchDocumentSegmenter | None = None,
        lease_seconds: float = 90.0,
        renew_interval_seconds: float = 30.0,
        poll_interval_seconds: float = 0.25,
        now: Callable[[], datetime] = datetime.now,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Any] = asyncio.sleep,
        file_validator: Callable[[Sequence[DownloadedAttachment]], Any]
        | None = None,
    ) -> None:
        for name, value in (
            ("lease_seconds", lease_seconds),
            ("renew_interval_seconds", renew_interval_seconds),
            ("poll_interval_seconds", poll_interval_seconds),
        ):
            if (
                type(value) not in {int, float}
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} 必须是有限正数")
        if renew_interval_seconds >= lease_seconds:
            raise ValueError("续租间隔必须短于租约")
        self._repository = repository
        self._processor = processor
        self._segmenter = segmenter or ResearchDocumentSegmenter()
        self._lease_seconds = float(lease_seconds)
        self._renew_interval_seconds = float(renew_interval_seconds)
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._now = now
        self._clock = clock
        self._sleep = sleep
        self._file_validator = file_validator

    async def ingest(
        self,
        doctor_id: str,
        downloaded: Sequence[DownloadedAttachment],
        *,
        deadline: float | None = None,
    ) -> ResearchDocumentIngestionResult:
        items = _validate_metadata(doctor_id, downloaded)
        await self._validate_files(items, deadline)
        try:
            identities = tuple(
                _build_identity(doctor_id, item) for item in items
            )
        except Exception:
            raise ResearchDocumentIngestionError(
                "RESEARCH_DOCUMENT_INPUT_INVALID"
            ) from None
        tasks = [
            asyncio.create_task(self._ingest_one(identity, item, deadline))
            for identity, item in zip(identities, items)
        ]
        try:
            entities = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return ResearchDocumentIngestionResult(tuple(entities))

    async def ingest_all(
        self,
        doctor_id: str,
        downloaded: Sequence[DownloadedAttachment],
        *,
        deadline: float | None = None,
    ) -> ResearchDocumentIngestionResult:
        return await self.ingest(doctor_id, downloaded, deadline=deadline)

    async def _validate_files(
        self,
        items: tuple[DownloadedAttachment, ...],
        deadline: float | None,
    ) -> None:
        self._ensure_deadline(deadline)
        if self._file_validator is None:
            awaitable = asyncio.to_thread(_validate_files_on_disk, items)
        else:
            result = self._file_validator(items)
            awaitable = result if inspect.isawaitable(result) else None
        if awaitable is not None:
            await self._await_deadline(awaitable, deadline)
        self._ensure_deadline(deadline)

    async def _ingest_one(
        self,
        identity: IngestionIdentity,
        item: DownloadedAttachment,
        deadline: float | None,
    ) -> ResearchDocumentIngestionEntity:
        while True:
            self._ensure_deadline(deadline)
            now = self._now()
            claim_failed = False
            try:
                claim = self._repository.claim(
                    identity,
                    now,
                    now + timedelta(seconds=self._lease_seconds),
                )
            except Exception:
                claim_failed = True
            if claim_failed:
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_INGESTION_FAILED"
                )
            entity, acquired = _validate_claim(identity, claim, now)
            if acquired:
                return await self._run_owner(identity, entity, item, deadline)
            if entity.status == "ready":
                return _validate_ready(identity, entity, item)
            if entity.status != "processing":
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_INGESTION_FAILED"
                )
            await self._await_deadline(
                self._sleep(self._poll_interval_seconds),
                deadline,
            )

    async def _run_owner(
        self,
        identity: IngestionIdentity,
        entity: ResearchDocumentIngestionEntity,
        item: DownloadedAttachment,
        deadline: float | None,
    ) -> ResearchDocumentIngestionEntity:
        renewer = asyncio.create_task(self._renew_loop(entity))
        work = asyncio.create_task(
            self._process_and_segment(identity, entity.id, item)
        )
        try:
            segments = await self._supervise_owner(work, renewer, deadline)
            await _stop_renewer(renewer)
            self._ensure_deadline(deadline)
            if not self._repository.complete(
                entity.id,
                entity.attempt_count,
                segments,
            ):
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_FENCING_FAILED"
                )
            ready = self._repository.get_ready(identity)
            if ready is None:
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_FENCING_FAILED"
                )
            return _validate_ready(identity, ready, item)
        except asyncio.CancelledError:
            await _cancel_tasks(work, renewer)
            self._best_effort_fail(
                entity,
                "RESEARCH_DOCUMENT_CANCELLED",
            )
            raise
        except _LeaseLost:
            await _cancel_tasks(work, renewer)
            error = ResearchDocumentIngestionError(
                "RESEARCH_DOCUMENT_LEASE_LOST"
            )
            self._best_effort_fail(entity, error.error_code)
            raise error
        except ResearchDocumentIngestionError as error:
            await _cancel_tasks(work, renewer)
            self._best_effort_fail(entity, error.error_code)
            raise
        except ResearchDocumentFencingError:
            await _cancel_tasks(work, renewer)
            error = ResearchDocumentIngestionError(
                "RESEARCH_DOCUMENT_FENCING_FAILED"
            )
            self._best_effort_fail(entity, error.error_code)
            raise error
        except Exception as raw_error:
            await _cancel_tasks(work, renewer)
            error_code = _safe_processing_error(raw_error)
            self._best_effort_fail(entity, error_code)
            raise ResearchDocumentIngestionError(error_code) from None

    async def _process_and_segment(
        self,
        identity: IngestionIdentity,
        ingestion_id: str,
        item: DownloadedAttachment,
    ):
        pages = await self._processor.process(item)
        return await asyncio.to_thread(
            self._segmenter.segment,
            ingestion_id,
            pages,
            processor_type=identity.processor_type,
        )

    async def _renew_loop(
        self,
        entity: ResearchDocumentIngestionEntity,
    ) -> None:
        while True:
            await self._sleep(self._renew_interval_seconds)
            now = self._now()
            if not self._repository.renew_lease(
                entity.id,
                entity.attempt_count,
                now + timedelta(seconds=self._lease_seconds),
            ):
                raise _LeaseLost()

    async def _supervise_owner(
        self,
        work: asyncio.Task,
        renewer: asyncio.Task,
        deadline: float | None,
    ):
        while True:
            remaining = self._remaining(deadline)
            done, _ = await asyncio.wait(
                {work, renewer},
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                raise ResearchDocumentIngestionError(
                    _INGESTION_TIMEOUT
                )
            if renewer in done:
                await renewer
                raise _LeaseLost()
            if work in done:
                return await work

    def _best_effort_fail(
        self,
        entity: ResearchDocumentIngestionEntity,
        error_code: str,
    ) -> None:
        safe_code = (
            error_code
            if _is_safe_error_code(error_code)
            else "RESEARCH_DOCUMENT_INGESTION_FAILED"
        )
        try:
            self._repository.fail(
                entity.id,
                entity.attempt_count,
                safe_code,
            )
        except Exception:
            pass

    async def _await_deadline(self, awaitable: Any, deadline: float | None):
        try:
            remaining = self._remaining(deadline)
        except BaseException:
            _dispose_unawaited(awaitable)
            raise
        try:
            if remaining is None:
                return await awaitable
            return await asyncio.wait_for(awaitable, timeout=remaining)
        except asyncio.TimeoutError:
            raise ResearchDocumentIngestionError(
                _INGESTION_TIMEOUT
            ) from None

    def _remaining(self, deadline: float | None) -> float | None:
        if deadline is None:
            return None
        if type(deadline) not in {int, float} or not math.isfinite(deadline):
            raise ResearchDocumentIngestionError(
                _INGESTION_TIMEOUT
            )
        remaining = float(deadline) - self._clock()
        if remaining <= 0:
            raise ResearchDocumentIngestionError(
                _INGESTION_TIMEOUT
            )
        return remaining

    def _ensure_deadline(self, deadline: float | None) -> None:
        self._remaining(deadline)


def _validate_metadata(
    doctor_id: str,
    downloaded: Sequence[DownloadedAttachment],
) -> tuple[DownloadedAttachment, ...]:
    if not isinstance(doctor_id, str) or not 1 <= len(doctor_id) <= 36:
        raise ResearchDocumentIngestionError("RESEARCH_DOCUMENT_INPUT_INVALID")
    if isinstance(downloaded, (str, bytes)):
        raise ResearchDocumentIngestionError("RESEARCH_DOCUMENT_INPUT_INVALID")
    items = tuple(downloaded)
    if not 1 <= len(items) <= _MAX_FILES or not all(
        isinstance(item, DownloadedAttachment) for item in items
    ):
        raise ResearchDocumentIngestionError("RESEARCH_DOCUMENT_INPUT_INVALID")
    attachment_ids = [item.attachment_id for item in items]
    if any(
        not isinstance(value, str) or not 1 <= len(value) <= 64
        for value in attachment_ids
    ):
        raise ResearchDocumentIngestionError("RESEARCH_DOCUMENT_INPUT_INVALID")
    if len(set(attachment_ids)) != len(attachment_ids):
        raise ResearchDocumentIngestionError("RESEARCH_DOCUMENT_INPUT_INVALID")

    total_bytes = 0
    total_pdf_pages = 0
    for item in items:
        if (
            type(item.size_bytes) is not int
            or item.size_bytes < 1
            or type(item.document_version) is not int
            or item.document_version < 1
            or not _is_sha256(item.content_sha256)
        ):
            raise ResearchDocumentIngestionError(
                "RESEARCH_DOCUMENT_INPUT_INVALID"
            )
        total_bytes += item.size_bytes
        if item.file_type == "pdf":
            if (
                item.mime_type != "application/pdf"
                or item.size_bytes > _MAX_PDF_BYTES
                or type(item.page_count) is not int
                or not 1 <= item.page_count <= _MAX_PDF_PAGES
            ):
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_CONTENT_LIMIT"
                )
            total_pdf_pages += item.page_count
        elif item.file_type == "image":
            if (
                item.mime_type not in _IMAGE_MIME_TYPES
                or item.size_bytes > _MAX_IMAGE_BYTES
                or item.page_count is not None
            ):
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_CONTENT_LIMIT"
                )
        elif item.file_type == "text":
            if (
                item.mime_type != "text/plain"
                or item.size_bytes > _MAX_TEXT_BYTES
                or item.page_count is not None
            ):
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_CONTENT_LIMIT"
                )
        elif item.file_type == "docx":
            if (
                item.mime_type != _DOCX_MIME_TYPE
                or item.size_bytes > _MAX_DOCX_BYTES
                or item.page_count is not None
            ):
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_CONTENT_LIMIT"
                )
        else:
            raise ResearchDocumentIngestionError(
                "RESEARCH_DOCUMENT_INPUT_INVALID"
            )
    if total_bytes > _MAX_TOTAL_BYTES or total_pdf_pages > _MAX_TOTAL_PDF_PAGES:
        raise ResearchDocumentIngestionError("RESEARCH_DOCUMENT_CONTENT_LIMIT")
    return items


def _build_identity(
    doctor_id: str,
    item: DownloadedAttachment,
) -> IngestionIdentity:
    processor_type = _PROCESSOR_BY_FILE_TYPE[item.file_type]
    return IngestionIdentity(
        doctor_id=doctor_id,
        attachment_id=item.attachment_id,
        document_version=item.document_version,
        content_sha256=item.content_sha256,
        processor_type=processor_type,
        extractor_version=_EXTRACTOR_BY_PROCESSOR[processor_type],
        segment_schema_version=SEGMENT_SCHEMA_VERSION,
    )


def _validate_claim(
    identity: IngestionIdentity,
    claim: Any,
    claim_now: datetime,
) -> tuple[ResearchDocumentIngestionEntity, bool]:
    raw_entity = getattr(claim, "entity", None)
    acquired = getattr(claim, "acquired", None)
    try:
        entity = ResearchDocumentIngestionEntity.model_validate(
            copy.deepcopy(raw_entity.model_dump(mode="python"))
        )
    except Exception:
        raise ResearchDocumentIngestionError(
            "RESEARCH_DOCUMENT_INGESTION_FAILED"
        ) from None
    if (
        type(acquired) is not bool
        or entity.identity != identity
        or entity.id != build_research_document_ingestion_id(identity)
        or entity.status not in {"processing", "ready"}
    ):
        raise ResearchDocumentIngestionError(
            "RESEARCH_DOCUMENT_INGESTION_FAILED"
        )
    if acquired and entity.status != "processing":
        raise ResearchDocumentIngestionError(
            "RESEARCH_DOCUMENT_INGESTION_FAILED"
        )
    if entity.status == "processing":
        try:
            valid_processing = (
                entity.attempt_count >= 1
                and entity.lease_expires_at is not None
                and entity.lease_expires_at > claim_now
                and entity.started_at is not None
                and entity.page_count is None
                and entity.error_code is None
                and entity.completed_at is None
            )
        except (TypeError, ValueError):
            valid_processing = False
        if not valid_processing:
            raise ResearchDocumentIngestionError(
                "RESEARCH_DOCUMENT_INGESTION_FAILED"
            )
    return entity, acquired


def _validate_ready(
    identity: IngestionIdentity,
    entity: Any,
    item: DownloadedAttachment,
) -> ResearchDocumentIngestionEntity:
    try:
        rebuilt = ResearchDocumentIngestionEntity.model_validate(
            copy.deepcopy(entity.model_dump(mode="python"))
        )
    except Exception:
        raise ResearchDocumentIngestionError(
            "RESEARCH_DOCUMENT_FENCING_FAILED"
        ) from None
    expected_page_count = item.page_count if item.file_type == "pdf" else 0
    if (
        rebuilt.identity != identity
        or rebuilt.id != build_research_document_ingestion_id(identity)
        or rebuilt.status != "ready"
        or rebuilt.page_count != expected_page_count
        or rebuilt.attempt_count < 1
        or rebuilt.lease_expires_at is not None
        or rebuilt.error_code is not None
        or rebuilt.started_at is None
        or rebuilt.completed_at is None
    ):
        raise ResearchDocumentIngestionError(
            "RESEARCH_DOCUMENT_FENCING_FAILED"
        )
    return rebuilt


def _validate_files_on_disk(items: Sequence[DownloadedAttachment]) -> None:
    for item in items:
        path = item.path
        if not isinstance(path, Path):
            raise ResearchDocumentIngestionError(
                "RESEARCH_DOCUMENT_INPUT_INVALID"
            )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError:
            raise ResearchDocumentIngestionError(
                "RESEARCH_DOCUMENT_INPUT_INVALID"
            ) from None
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or info.st_size != item.size_bytes
            ):
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_INPUT_INVALID"
                )
            digest = hashlib.sha256()
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
            if digest.hexdigest() != item.content_sha256:
                raise ResearchDocumentIngestionError(
                    "RESEARCH_DOCUMENT_INPUT_INVALID"
                )
        finally:
            os.close(descriptor)


async def _stop_renewer(task: asyncio.Task) -> None:
    if not task.done():
        task.cancel()
    result = (await asyncio.gather(task, return_exceptions=True))[0]
    if isinstance(result, asyncio.CancelledError):
        return
    if isinstance(result, BaseException):
        raise result


async def _cancel_tasks(*tasks: asyncio.Task) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _dispose_unawaited(awaitable: Any) -> None:
    if isinstance(awaitable, asyncio.Future):
        if not awaitable.done():
            awaitable.cancel()
        return
    close = getattr(awaitable, "close", None)
    if callable(close):
        close()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_safe_error_code(value: Any) -> bool:
    return (
        isinstance(value, str)
        and _SAFE_ERROR.fullmatch(value) is not None
        and value.startswith(_SAFE_ERROR_PREFIXES)
    )


def _safe_processing_error(error: Exception) -> str:
    error_code = getattr(error, "error_code", None)
    return (
        error_code
        if _is_safe_error_code(error_code)
        else "RESEARCH_DOCUMENT_PROCESSING_FAILED"
    )


__all__ = [
    "DOCX_EXTRACTOR_VERSION",
    "IMAGE_EXTRACTOR_VERSION",
    "PDF_EXTRACTOR_VERSION",
    "TEXT_EXTRACTOR_VERSION",
    "ResearchDocumentIngestionError",
    "ResearchDocumentIngestionResult",
    "ResearchDocumentIngestionService",
]
