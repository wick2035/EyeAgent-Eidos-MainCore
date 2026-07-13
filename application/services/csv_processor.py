import asyncio
from typing import Any

from domain.models.research_dataset import (
    ExtractedCsvChunk,
    ExtractedCsvRow,
    ExtractedResearchCsv,
)
from infrastructure.attachments.parser_protocol import ParsedResearchCsv


_CSV_MIME_TYPE = "text/csv"
_MAX_CSV_BYTES = 10 * 1024 * 1024
_PARSE_FAILED = "RESEARCH_CSV_PARSE_FAILED"
_STABLE_ERROR_CODES = frozenset(
    {
        "RESEARCH_CSV_UNAVAILABLE",
        "RESEARCH_CSV_SIZE_LIMIT",
        "RESEARCH_CSV_INVALID",
        "RESEARCH_CSV_ENCODING_UNSUPPORTED",
        "RESEARCH_CSV_STRUCTURE_LIMIT",
        "RESEARCH_CSV_CONTENT_LIMIT",
        _PARSE_FAILED,
    }
)


class CsvProcessingError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        if error_code not in _STABLE_ERROR_CODES:
            raise ValueError("不允许的科研 CSV 处理错误码")
        super().__init__(error_code)
        self.error_code = error_code


class CsvProcessor:
    def __init__(self, sandbox: Any) -> None:
        self._sandbox = sandbox

    async def process(self, downloaded: Any) -> ExtractedResearchCsv:
        identity = _downloaded_identity(downloaded)
        try:
            parsed = await self._sandbox.parse(
                downloaded,
                profile="research_csv_v1",
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise CsvProcessingError(_safe_error_code(error)) from None

        if (
            not isinstance(parsed, ParsedResearchCsv)
            or parsed.attachment_id != identity[0]
            or parsed.document_version != identity[1]
            or parsed.mime_type != identity[2]
        ):
            raise CsvProcessingError(_PARSE_FAILED)
        try:
            normalized = parsed.normalized
            descriptor = normalized.descriptor
            chunks = tuple(
                ExtractedCsvChunk(
                    schema_version=chunk.schema_version,
                    ordinal=chunk.ordinal,
                    logical_row_start=chunk.logical_row_start,
                    logical_row_end=chunk.logical_row_end,
                    physical_row_start=chunk.physical_row_start,
                    physical_row_end=chunk.physical_row_end,
                    row_count=chunk.row_count,
                    non_empty_cell_count=chunk.non_empty_cell_count,
                    formula_like_cell_count=chunk.formula_like_cell_count,
                    rows=tuple(
                        ExtractedCsvRow(
                            logical_row_number=row.logical_row_number,
                            physical_row_start=row.physical_row_start,
                            physical_row_end=row.physical_row_end,
                            values=row.values,
                        )
                        for row in chunk.rows
                    ),
                    payload_sha256=chunk.sha256,
                )
                for chunk in normalized.chunks
            )
            return ExtractedResearchCsv(
                schema_version=descriptor.schema_version,
                sheet_name=descriptor.sheet_name,
                headers=descriptor.headers,
                header_row_start=descriptor.header_row_start,
                header_row_end=descriptor.header_row_end,
                physical_line_count=descriptor.physical_line_count,
                record_count=descriptor.record_count,
                data_row_count=descriptor.data_row_count,
                column_count=descriptor.column_count,
                non_empty_cell_count=descriptor.non_empty_cell_count,
                formula_like_cell_count=descriptor.formula_like_cell_count,
                missing_value_counts=descriptor.missing_value_counts,
                chunks=chunks,
                descriptor_sha256=descriptor.sha256,
            )
        except Exception:
            raise CsvProcessingError(_PARSE_FAILED) from None


def _downloaded_identity(downloaded: Any) -> tuple[str, int, str]:
    attachment_id = _value(downloaded, "attachment_id")
    document_version = _value(downloaded, "document_version")
    file_type = _value(downloaded, "file_type")
    mime_type = _value(downloaded, "mime_type")
    size_bytes = _value(downloaded, "size_bytes")
    page_count = _value(downloaded, "page_count")
    if (
        not isinstance(attachment_id, str)
        or not attachment_id
        or type(document_version) is not int
        or document_version < 1
        or file_type != "csv"
        or mime_type != _CSV_MIME_TYPE
        or type(size_bytes) is not int
        or not 1 <= size_bytes <= _MAX_CSV_BYTES
        or page_count is not None
    ):
        raise CsvProcessingError("RESEARCH_CSV_INVALID")
    return attachment_id, document_version, mime_type


def _safe_error_code(error: Exception) -> str:
    error_code = getattr(error, "error_code", None)
    return error_code if error_code in _STABLE_ERROR_CODES else _PARSE_FAILED


def _value(source: Any, name: str) -> Any:
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


__all__ = ["CsvProcessingError", "CsvProcessor"]
