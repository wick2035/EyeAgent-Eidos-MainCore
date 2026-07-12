import hashlib
import unicodedata
from dataclasses import dataclass


MAX_RESEARCH_TEXT_RAW_BYTES = 512 * 1024
MAX_RESEARCH_TEXT_CHARACTERS = 500_000
MAX_RESEARCH_TEXT_CANONICAL_BYTES = 4 * MAX_RESEARCH_TEXT_CHARACTERS


@dataclass(frozen=True)
class NormalizedResearchText:
    text: str
    utf8_bytes: bytes
    sha256: str
    character_count: int


class ResearchTextContractError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


def normalize_research_text_bytes(content: bytes) -> NormalizedResearchText:
    return _normalize_research_text_bytes(
        content,
        max_bytes=MAX_RESEARCH_TEXT_RAW_BYTES,
        size_error_code="RESEARCH_TXT_SIZE_LIMIT",
    )


def validate_canonical_research_text_bytes(
    content: bytes,
) -> NormalizedResearchText:
    normalized = _normalize_research_text_bytes(
        content,
        max_bytes=MAX_RESEARCH_TEXT_CANONICAL_BYTES,
        size_error_code="RESEARCH_TXT_CONTENT_LIMIT",
    )
    if normalized.utf8_bytes != content:
        raise ResearchTextContractError("ATTACHMENT_OUTPUT_TEXT_INVALID")
    return normalized


def _normalize_research_text_bytes(
    content: bytes,
    *,
    max_bytes: int,
    size_error_code: str,
) -> NormalizedResearchText:
    if not isinstance(content, bytes) or not content:
        raise ResearchTextContractError("RESEARCH_TXT_INVALID")
    if len(content) > max_bytes:
        raise ResearchTextContractError(size_error_code)

    raw = content[3:] if content.startswith(b"\xef\xbb\xbf") else content
    try:
        decoded = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise ResearchTextContractError(
            "RESEARCH_TXT_ENCODING_UNSUPPORTED"
        ) from None

    normalized = unicodedata.normalize(
        "NFC",
        decoded.replace("\r\n", "\n").replace("\r", "\n"),
    )
    if any(
        (ord(character) < 32 and character not in "\n\t")
        or ord(character) == 127
        for character in normalized
    ):
        raise ResearchTextContractError("RESEARCH_TXT_BINARY")
    if not normalized.strip():
        raise ResearchTextContractError("RESEARCH_TXT_INVALID")
    if len(normalized) > MAX_RESEARCH_TEXT_CHARACTERS:
        raise ResearchTextContractError("RESEARCH_TXT_CONTENT_LIMIT")

    utf8_bytes = normalized.encode("utf-8")
    return NormalizedResearchText(
        text=normalized,
        utf8_bytes=utf8_bytes,
        sha256=hashlib.sha256(utf8_bytes).hexdigest(),
        character_count=len(normalized),
    )
