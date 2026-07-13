import asyncio
import hashlib
from typing import Any

from domain.models.research_document import ExtractedResearchText
from infrastructure.attachments.parser_protocol import ParsedResearchDocx


_DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_PARSE_FAILED = "RESEARCH_DOCX_PARSE_FAILED"
_SAFE_PROCESSING_ERRORS = frozenset(
    {
        "RESEARCH_DOCX_SIZE_LIMIT",
        "RESEARCH_DOCX_INVALID",
        "RESEARCH_DOCX_ENCRYPTED",
        "RESEARCH_DOCX_STRUCTURE_LIMIT",
        "RESEARCH_DOCX_CONTENT_LIMIT",
        _PARSE_FAILED,
    }
)


class DocxProcessingError(RuntimeError):
    def __init__(self, error_code: str = _PARSE_FAILED) -> None:
        if error_code not in _SAFE_PROCESSING_ERRORS:
            raise ValueError("不允许的科研 DOCX 处理错误码")
        super().__init__(error_code)
        self.error_code = error_code


class DocxProcessor:
    def __init__(self, sandbox: Any) -> None:
        self._sandbox = sandbox

    async def process(self, downloaded: Any) -> ExtractedResearchText:
        identity = _downloaded_identity(downloaded)
        try:
            parsed = await self._sandbox.parse(
                downloaded,
                profile="research_docx_v1",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error_code = getattr(exc, "error_code", None)
            raise DocxProcessingError(
                error_code if error_code in _SAFE_PROCESSING_ERRORS else _PARSE_FAILED
            ) from None

        if (
            not isinstance(parsed, ParsedResearchDocx)
            or parsed.attachment_id != identity[0]
            or parsed.document_version != identity[1]
            or parsed.mime_type != identity[2]
            or not isinstance(parsed.text, str)
        ):
            raise DocxProcessingError()
        try:
            encoded = parsed.text.encode("utf-8")
        except UnicodeEncodeError:
            raise DocxProcessingError() from None
        digest = hashlib.sha256(encoded).hexdigest()
        character_count = len(parsed.text)
        if parsed.text_sha256 != digest or parsed.character_count != character_count:
            raise DocxProcessingError()
        try:
            return ExtractedResearchText(
                text=parsed.text,
                text_sha256=digest,
                character_count=character_count,
            )
        except Exception:
            raise DocxProcessingError() from None


def _downloaded_identity(downloaded: Any) -> tuple[str, int, str]:
    try:
        attachment_id = _value(downloaded, "attachment_id")
        document_version = _value(downloaded, "document_version")
        file_type = _value(downloaded, "file_type")
        mime_type = _value(downloaded, "mime_type")
    except Exception:
        raise DocxProcessingError() from None
    if (
        not isinstance(attachment_id, str)
        or not attachment_id
        or type(document_version) is not int
        or document_version < 1
        or file_type != "docx"
        or mime_type != _DOCX_MIME_TYPE
    ):
        raise DocxProcessingError()
    return attachment_id, document_version, mime_type


def _value(item: Any, name: str) -> Any:
    missing = object()
    if isinstance(item, dict):
        value = item.get(name, missing)
    else:
        value = getattr(item, name, missing)
    if value is missing:
        raise KeyError(name)
    return value


__all__ = ["DocxProcessingError", "DocxProcessor"]
