import asyncio
import hashlib
from typing import Any

from domain.models.research_document import ExtractedResearchText
from infrastructure.attachments.parser_protocol import ParsedResearchText


_PARSE_FAILED = "RESEARCH_TXT_PARSE_FAILED"


class PlainTextProcessingError(RuntimeError):
    def __init__(self, error_code: str = _PARSE_FAILED) -> None:
        if error_code != _PARSE_FAILED:
            raise ValueError("不允许的科研 TXT 处理错误码")
        super().__init__(error_code)
        self.error_code = error_code


class PlainTextProcessor:
    def __init__(self, sandbox: Any) -> None:
        self._sandbox = sandbox

    async def process(self, downloaded: Any) -> ExtractedResearchText:
        identity = _downloaded_identity(downloaded)
        parse_failed = False
        try:
            parsed = await self._sandbox.parse(
                downloaded,
                profile="research_text_v1",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            parse_failed = True
            parsed = None
        if parse_failed:
            raise PlainTextProcessingError()

        if (
            not isinstance(parsed, ParsedResearchText)
            or parsed.attachment_id != identity[0]
            or parsed.document_version != identity[1]
            or parsed.mime_type != identity[2]
            or not isinstance(parsed.text, str)
        ):
            raise PlainTextProcessingError()

        encoding_failed = False
        try:
            encoded = parsed.text.encode("utf-8")
        except UnicodeEncodeError:
            encoding_failed = True
            encoded = b""
        if encoding_failed:
            raise PlainTextProcessingError()

        text_sha256 = hashlib.sha256(encoded).hexdigest()
        character_count = len(parsed.text)
        if (
            parsed.text_sha256 != text_sha256
            or parsed.character_count != character_count
        ):
            raise PlainTextProcessingError()

        validation_failed = False
        try:
            extracted = ExtractedResearchText(
                text=parsed.text,
                text_sha256=text_sha256,
                character_count=character_count,
            )
        except Exception:
            validation_failed = True
            extracted = None
        if validation_failed or extracted is None:
            raise PlainTextProcessingError()
        return extracted


def _downloaded_identity(downloaded: Any) -> tuple[str, int, str]:
    try:
        attachment_id = _value(downloaded, "attachment_id")
        document_version = _value(downloaded, "document_version")
        file_type = _value(downloaded, "file_type")
        mime_type = _value(downloaded, "mime_type")
    except Exception:
        raise PlainTextProcessingError() from None
    if (
        not isinstance(attachment_id, str)
        or not attachment_id
        or type(document_version) is not int
        or document_version < 1
        or file_type != "text"
        or mime_type != "text/plain"
    ):
        raise PlainTextProcessingError()
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


__all__ = [
    "PlainTextProcessingError",
    "PlainTextProcessor",
]
