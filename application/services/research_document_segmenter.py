import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Sequence

from domain.models.research_document import (
    ExtractedResearchPage,
    ExtractedResearchText,
    ProcessorType,
    ResearchDocumentSegmentEntity,
)


SEGMENT_SCHEMA_VERSION = "segment_v1"
MAX_SEGMENT_TOKENS = 2500
GLOBAL_CONTEXT_BUDGET = 12000

_MAX_SEGMENT_UTF8_BYTES = MAX_SEGMENT_TOKENS * 3
_PARAGRAPH_BOUNDARY = re.compile(r"\n[\t ]*\n+")
_SENTENCE_BOUNDARY = re.compile(r"[。！？!?；;.!]+[”’\"']*")
_WHITESPACE_BOUNDARY = re.compile(r"\s+")
_BOUNDARIES = (
    _PARAGRAPH_BOUNDARY,
    _SENTENCE_BOUNDARY,
    _WHITESPACE_BOUNDARY,
)


def estimate_tokens_v1(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text 必须是字符串")
    normalized = unicodedata.normalize("NFC", text)
    return max(1, math.ceil(len(normalized.encode("utf-8")) / 3))


@dataclass(frozen=True)
class _SourceChunk:
    text: str
    page_number: int
    extraction_method: str


class ResearchDocumentSegmenter:
    def segment(
        self,
        ingestion_id: str,
        extracted: Sequence[ExtractedResearchPage] | ExtractedResearchText,
        *,
        processor_type: ProcessorType,
    ) -> list[ResearchDocumentSegmentEntity]:
        if processor_type == "pdf_hybrid_v1":
            return self.segment_pdf(ingestion_id, extracted)
        if processor_type == "image_vision_v1":
            if not isinstance(extracted, Sequence) or len(extracted) != 1:
                raise ValueError("科研图片必须且只能产生一个提取页")
            return self.segment_image(ingestion_id, extracted[0])
        if processor_type == "plain_text_v1":
            return self.segment_text(ingestion_id, extracted)
        raise ValueError("不支持的科研文档 processor_type")

    def segment_pdf(
        self,
        ingestion_id: str,
        pages: Sequence[ExtractedResearchPage],
    ) -> list[ResearchDocumentSegmentEntity]:
        validated = _validate_pdf_pages(pages)
        source_chunks: list[_SourceChunk] = []
        for page_index, page in enumerate(validated):
            normalized = _normalize_text(page.text)
            if page_index > 0:
                normalized = "\n\n" + normalized
            for chunk in _split_normalized_text(normalized):
                source_chunks.append(
                    _SourceChunk(
                        text=chunk,
                        page_number=page.page_number,
                        extraction_method=page.extraction_method,
                    )
                )
        if not source_chunks:
            raise ValueError("科研 PDF 提取正文不能为空")
        packed = _pack_source_chunks(source_chunks)
        return [
            _build_pdf_segment(ingestion_id, ordinal, chunks)
            for ordinal, chunks in enumerate(packed)
        ]

    def segment_image(
        self,
        ingestion_id: str,
        page: ExtractedResearchPage,
    ) -> list[ResearchDocumentSegmentEntity]:
        if (
            not isinstance(page, ExtractedResearchPage)
            or page.page_number != 1
            or page.extraction_method != "vision"
        ):
            raise ValueError("科研图片提取结果无效")
        content = _normalize_text(page.text)
        if not content.strip():
            raise ValueError("科研图片提取正文不能为空")
        token_count = estimate_tokens_v1(content)
        if token_count > MAX_SEGMENT_TOKENS:
            raise ValueError("科研图片提取正文超过单段上限")
        return [
            ResearchDocumentSegmentEntity(
                ingestion_id=ingestion_id,
                ordinal=0,
                content=content,
                page_start=None,
                page_end=None,
                token_count=token_count,
                metadata={
                    "block_index": 0,
                    "extraction_method": "vision",
                    "extraction_mode": "vision",
                    "ocr_applied": False,
                    "ocr_page_count": 0,
                },
            )
        ]

    def segment_text(
        self,
        ingestion_id: str,
        extracted: ExtractedResearchText,
    ) -> list[ResearchDocumentSegmentEntity]:
        if not isinstance(extracted, ExtractedResearchText):
            raise ValueError("科研 TXT 提取结果无效")
        normalized = _normalize_text(extracted.text)
        chunks = [
            content
            for content in _split_normalized_text(normalized)
            if content.strip()
        ]
        if not chunks:
            raise ValueError("科研 TXT 提取正文不能为空")
        return [
            ResearchDocumentSegmentEntity(
                ingestion_id=ingestion_id,
                ordinal=ordinal,
                content=content,
                page_start=None,
                page_end=None,
                sheet_name=None,
                row_start=None,
                row_end=None,
                token_count=estimate_tokens_v1(content),
                metadata={
                    "block_index": ordinal,
                    "extraction_method": "plain_text",
                    "extraction_mode": "text",
                },
            )
            for ordinal, content in enumerate(chunks)
        ]


def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("科研文档提取正文必须是字符串")
    normalized_newlines = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", normalized_newlines)


def _validate_pdf_pages(
    pages: Sequence[ExtractedResearchPage],
) -> tuple[ExtractedResearchPage, ...]:
    if isinstance(pages, (str, bytes)):
        raise ValueError("科研 PDF 提取页无效")
    validated = tuple(pages)
    if not validated:
        raise ValueError("科研 PDF 提取页不能为空")
    for expected_number, page in enumerate(validated, start=1):
        if (
            not isinstance(page, ExtractedResearchPage)
            or page.page_number != expected_number
            or page.extraction_method not in {"digital_text", "ocr"}
        ):
            raise ValueError("科研 PDF 页码或提取方式无效")
    return validated


def _split_normalized_text(text: str) -> list[str]:
    if not text:
        return []
    return _split_at_level(text, 0)


def _split_at_level(text: str, boundary_index: int) -> list[str]:
    if estimate_tokens_v1(text) <= MAX_SEGMENT_TOKENS:
        return [text]
    if boundary_index >= len(_BOUNDARIES):
        return _hard_cut_by_code_point(text)

    pieces = _pieces_ending_at_boundaries(text, _BOUNDARIES[boundary_index])
    if len(pieces) == 1:
        return _split_at_level(text, boundary_index + 1)

    split_pieces: list[str] = []
    for piece in pieces:
        split_pieces.extend(_split_at_level(piece, boundary_index + 1))
    return _pack_text_pieces(split_pieces)


def _pieces_ending_at_boundaries(
    text: str,
    boundary: re.Pattern[str],
) -> list[str]:
    pieces: list[str] = []
    cursor = 0
    for match in boundary.finditer(text):
        end = match.end()
        if end > cursor:
            pieces.append(text[cursor:end])
        cursor = end
    if cursor < len(text):
        pieces.append(text[cursor:])
    return pieces or [text]


def _pack_text_pieces(pieces: Iterable[str]) -> list[str]:
    packed: list[str] = []
    current = ""
    current_bytes = 0
    for piece in pieces:
        piece_bytes = len(piece.encode("utf-8"))
        if not current:
            current = piece
            current_bytes = piece_bytes
        elif current_bytes + piece_bytes <= _MAX_SEGMENT_UTF8_BYTES:
            current += piece
            current_bytes += piece_bytes
        else:
            packed.append(current)
            current = piece
            current_bytes = piece_bytes
    if current:
        packed.append(current)
    return packed


def _hard_cut_by_code_point(text: str) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for character in text:
        character_bytes = len(character.encode("utf-8"))
        if current and current_bytes + character_bytes > _MAX_SEGMENT_UTF8_BYTES:
            chunks.append("".join(current))
            current = []
            current_bytes = 0
        current.append(character)
        current_bytes += character_bytes
    if current:
        chunks.append("".join(current))
    return chunks


def _pack_source_chunks(
    chunks: Sequence[_SourceChunk],
) -> list[tuple[_SourceChunk, ...]]:
    packed: list[tuple[_SourceChunk, ...]] = []
    current: list[_SourceChunk] = []
    current_text = ""
    for chunk in chunks:
        if not current:
            current = [chunk]
            current_text = chunk.text
        elif estimate_tokens_v1(current_text + chunk.text) <= MAX_SEGMENT_TOKENS:
            current.append(chunk)
            current_text += chunk.text
        else:
            packed.append(tuple(current))
            current = [chunk]
            current_text = chunk.text
    if current:
        packed.append(tuple(current))
    return packed


def _build_pdf_segment(
    ingestion_id: str,
    ordinal: int,
    chunks: Sequence[_SourceChunk],
) -> ResearchDocumentSegmentEntity:
    content = "".join(chunk.text for chunk in chunks)
    source_page_numbers = list(
        dict.fromkeys(chunk.page_number for chunk in chunks)
    )
    methods = set(chunk.extraction_method for chunk in chunks)
    if len(methods) == 1:
        extraction_method = next(iter(methods))
        extraction_mode = "text" if extraction_method == "digital_text" else "ocr"
    else:
        extraction_method = "mixed"
        extraction_mode = "mixed"
    ocr_pages = {
        chunk.page_number
        for chunk in chunks
        if chunk.extraction_method == "ocr"
    }
    return ResearchDocumentSegmentEntity(
        ingestion_id=ingestion_id,
        ordinal=ordinal,
        content=content,
        page_start=source_page_numbers[0],
        page_end=source_page_numbers[-1],
        token_count=estimate_tokens_v1(content),
        metadata={
            "block_index": ordinal,
            "extraction_method": extraction_method,
            "extraction_mode": extraction_mode,
            "ocr_applied": bool(ocr_pages),
            "ocr_page_count": len(ocr_pages),
            "source_page_numbers": source_page_numbers,
        },
    )


__all__ = [
    "GLOBAL_CONTEXT_BUDGET",
    "MAX_SEGMENT_TOKENS",
    "SEGMENT_SCHEMA_VERSION",
    "ResearchDocumentSegmenter",
    "estimate_tokens_v1",
]
