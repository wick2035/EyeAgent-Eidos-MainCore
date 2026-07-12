import hashlib
import unicodedata
from dataclasses import dataclass


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
    if not isinstance(content, bytes) or not content:
        raise ResearchTextContractError("RESEARCH_TXT_INVALID")
    if len(content) > 512 * 1024:
        raise ResearchTextContractError("RESEARCH_TXT_SIZE_LIMIT")

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
    if len(normalized) > 500_000:
        raise ResearchTextContractError("RESEARCH_TXT_CONTENT_LIMIT")

    utf8_bytes = normalized.encode("utf-8")
    return NormalizedResearchText(
        text=normalized,
        utf8_bytes=utf8_bytes,
        sha256=hashlib.sha256(utf8_bytes).hexdigest(),
        character_count=len(normalized),
    )
