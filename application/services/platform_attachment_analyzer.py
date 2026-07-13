import asyncio
import base64
import inspect
import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from langchain_core.messages import HumanMessage

from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ParsedAttachment,
)
from utils.attachment_analyzer import (
    _IMAGE_ANALYSIS_PROMPT,
    _PDF_ANALYSIS_PROMPT,
)
from utils.llm_config import get_llm, get_pdf_analysis_llm
from utils.transient_attachment_context import AttachmentAnalysis


_SAFE_ERROR_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


@dataclass(frozen=True)
class AttachmentStatusUpdate:
    attachment_id: str
    status: Literal["processing", "ready", "failed"]
    error_code: str | None = None


@dataclass(frozen=True)
class _ItemFailure:
    attachment_id: str
    error_code: str


class AttachmentAnalysisBatchError(RuntimeError):
    def __init__(self, failures: tuple[_ItemFailure, ...]) -> None:
        super().__init__("ATTACHMENT_ANALYSIS_FAILED")
        self.error_code = "ATTACHMENT_ANALYSIS_FAILED"
        self.failures = failures


StatusCallback = Callable[[AttachmentStatusUpdate], Awaitable[None]]
ParsedAnalyzer = Callable[[ParsedAttachment], Awaitable[str] | str]


class PlatformAttachmentAnalyzer:
    def __init__(
        self,
        sandbox: Any,
        *,
        analyze_parsed: ParsedAnalyzer | None = None,
        timeout_seconds: float = 120.0,
        heartbeat_interval: float = 30.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sandbox = sandbox
        self._analyze_parsed = analyze_parsed or self._default_analyze_parsed
        self._timeout_seconds = timeout_seconds
        self._heartbeat_interval = heartbeat_interval
        self._sleep = sleep
        self._clock = clock
        self._semaphore = asyncio.Semaphore(2)

    async def analyze_all(
        self,
        downloaded: list[Any],
        on_status: StatusCallback,
    ) -> list[AttachmentAnalysis]:
        tasks = [
            asyncio.create_task(self._analyze_one(item, on_status))
            for item in downloaded
        ]
        try:
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        failures: list[_ItemFailure] = []
        analyses: list[AttachmentAnalysis] = []
        for item, outcome in zip(downloaded, outcomes):
            if isinstance(outcome, _ItemFailure):
                failures.append(outcome)
            elif isinstance(outcome, BaseException):
                failures.append(
                    _ItemFailure(
                        attachment_id=str(_value(item, "attachment_id")),
                        error_code="ATTACHMENT_ANALYSIS_FAILED",
                    )
                )
            else:
                analyses.append(outcome)
        if failures:
            raise AttachmentAnalysisBatchError(tuple(failures))
        return analyses

    async def _analyze_one(
        self,
        downloaded: Any,
        on_status: StatusCallback,
    ) -> AttachmentAnalysis | _ItemFailure:
        attachment_id = str(_value(downloaded, "attachment_id"))
        await _emit_status(
            on_status,
            AttachmentStatusUpdate(
                attachment_id=attachment_id,
                status="processing",
            ),
        )
        heartbeat = asyncio.create_task(
            self._heartbeat(attachment_id, on_status)
        )
        try:
            try:
                analysis = await asyncio.wait_for(
                    self._run_limited(downloaded),
                    timeout=self._timeout_seconds,
                )
            except asyncio.TimeoutError:
                error_code = "ATTACHMENT_ANALYSIS_TIMEOUT"
                await _emit_status(
                    on_status,
                    AttachmentStatusUpdate(
                        attachment_id=attachment_id,
                        status="failed",
                        error_code=error_code,
                    ),
                )
                return _ItemFailure(attachment_id, error_code)
            except AttachmentParserError as exc:
                error_code = (
                    exc.error_code
                    if _SAFE_ERROR_PATTERN.fullmatch(exc.error_code)
                    else "ATTACHMENT_PARSER_FAILED"
                )
                await _emit_status(
                    on_status,
                    AttachmentStatusUpdate(
                        attachment_id=attachment_id,
                        status="failed",
                        error_code=error_code,
                    ),
                )
                return _ItemFailure(attachment_id, error_code)
            except asyncio.CancelledError:
                raise
            except BaseException:
                error_code = "ATTACHMENT_ANALYSIS_FAILED"
                await _emit_status(
                    on_status,
                    AttachmentStatusUpdate(
                        attachment_id=attachment_id,
                        status="failed",
                        error_code=error_code,
                    ),
                )
                return _ItemFailure(attachment_id, error_code)

            await _emit_status(
                on_status,
                AttachmentStatusUpdate(
                    attachment_id=attachment_id,
                    status="ready",
                ),
            )
            return AttachmentAnalysis(
                attachment_id=attachment_id,
                untrusted_text=analysis,
            )
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

    async def _run_limited(self, downloaded: Any) -> str:
        async with self._semaphore:
            parsed = await self._sandbox.parse(downloaded)
            value = self._analyze_parsed(parsed)
            if inspect.isawaitable(value):
                value = await value
            if not isinstance(value, str) or not value:
                raise AttachmentParserError("ATTACHMENT_ANALYSIS_EMPTY")
            return value

    async def _heartbeat(
        self,
        attachment_id: str,
        on_status: StatusCallback,
    ) -> None:
        last_emitted_at = self._clock()
        while True:
            await self._sleep(self._heartbeat_interval)
            current_time = self._clock()
            if current_time - last_emitted_at >= self._heartbeat_interval:
                await _emit_status(
                    on_status,
                    AttachmentStatusUpdate(
                        attachment_id=attachment_id,
                        status="processing",
                    ),
                )
                last_emitted_at = current_time

    async def _default_analyze_parsed(self, parsed: ParsedAttachment) -> str:
        if not parsed.pages:
            raise AttachmentParserError("ATTACHMENT_ANALYSIS_EMPTY")
        content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:{page.mime_type};base64,"
                        f"{base64.b64encode(page.content).decode('ascii')}"
                    )
                },
            }
            for page in parsed.pages
        ]
        if parsed.file_type == "image":
            content.append({"type": "text", "text": _IMAGE_ANALYSIS_PROMPT})
            llm = get_llm()
        elif parsed.file_type == "pdf":
            content.append({"type": "text", "text": _PDF_ANALYSIS_PROMPT})
            llm = get_pdf_analysis_llm()
        else:
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        response = await llm.ainvoke([HumanMessage(content=content)])
        result = response.content if hasattr(response, "content") else str(response)
        if not isinstance(result, str):
            result = str(result)
        return result


async def _emit_status(
    callback: StatusCallback,
    update: AttachmentStatusUpdate,
) -> None:
    result = callback(update)
    if not inspect.isawaitable(result):
        raise TypeError("on_status must be an async callback")
    await result


def _value(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item[name]
    return getattr(item, name)


__all__ = [
    "AttachmentAnalysis",
    "AttachmentAnalysisBatchError",
    "AttachmentStatusUpdate",
    "PlatformAttachmentAnalyzer",
]
