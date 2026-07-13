import hashlib
import unicodedata
from dataclasses import dataclass


MAX_RESEARCH_DOCX_BYTES = 10 * 1024 * 1024
MAX_RESEARCH_DOCX_CHARACTERS = 500_000
MAX_RESEARCH_DOCX_CANONICAL_BYTES = 4 * MAX_RESEARCH_DOCX_CHARACTERS


@dataclass(frozen=True)
class NormalizedResearchDocxText:
    text: str
    utf8_bytes: bytes
    sha256: str
    character_count: int


class ResearchDocxContractError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


def normalize_research_docx_text(text: str) -> NormalizedResearchDocxText:
    if not isinstance(text, str):
        raise ResearchDocxContractError("RESEARCH_DOCX_INVALID")
    normalized = unicodedata.normalize(
        "NFC",
        text.replace("\r\n", "\n").replace("\r", "\n"),
    )
    if any(
        (ord(character) < 32 and character not in "\n\t")
        or ord(character) == 127
        for character in normalized
    ):
        raise ResearchDocxContractError("RESEARCH_DOCX_INVALID")
    if not normalized.strip():
        raise ResearchDocxContractError("RESEARCH_DOCX_INVALID")
    if len(normalized) > MAX_RESEARCH_DOCX_CHARACTERS:
        raise ResearchDocxContractError("RESEARCH_DOCX_CONTENT_LIMIT")
    encoded = normalized.encode("utf-8")
    if len(encoded) > MAX_RESEARCH_DOCX_CANONICAL_BYTES:
        raise ResearchDocxContractError("RESEARCH_DOCX_CONTENT_LIMIT")
    return NormalizedResearchDocxText(
        text=normalized,
        utf8_bytes=encoded,
        sha256=hashlib.sha256(encoded).hexdigest(),
        character_count=len(normalized),
    )


def validate_canonical_research_docx_bytes(
    content: bytes,
) -> NormalizedResearchDocxText:
    if not isinstance(content, bytes) or not content:
        raise ResearchDocxContractError("RESEARCH_DOCX_INVALID")
    if len(content) > MAX_RESEARCH_DOCX_CANONICAL_BYTES:
        raise ResearchDocxContractError("RESEARCH_DOCX_CONTENT_LIMIT")
    try:
        decoded = content.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise ResearchDocxContractError("RESEARCH_DOCX_INVALID") from None
    normalized = normalize_research_docx_text(decoded)
    if normalized.utf8_bytes != content:
        raise ResearchDocxContractError("RESEARCH_DOCX_INVALID")
    return normalized


__all__ = [
    "MAX_RESEARCH_DOCX_BYTES",
    "MAX_RESEARCH_DOCX_CANONICAL_BYTES",
    "MAX_RESEARCH_DOCX_CHARACTERS",
    "NormalizedResearchDocxText",
    "ResearchDocxContractError",
    "normalize_research_docx_text",
    "validate_canonical_research_docx_bytes",
]
