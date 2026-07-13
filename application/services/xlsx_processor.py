import asyncio
from typing import Any

from domain.models.research_dataset import (
    ExtractedResearchXlsx,
    ExtractedXlsxChunk,
    ExtractedXlsxRow,
    ExtractedXlsxSheet,
    build_research_xlsx_sheet_descriptor_sha256,
)
from infrastructure.attachments.parser_protocol import ParsedResearchXlsx
from infrastructure.attachments.research_xlsx_contract import (
    rebuild_research_xlsx_from_canonical_bytes,
)


_XLSX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
_MAX_XLSX_BYTES = 10 * 1024 * 1024
_PARSE_FAILED = "RESEARCH_XLSX_PARSE_FAILED"
_STABLE_ERROR_CODES = frozenset(
    {
        "RESEARCH_XLSX_UNAVAILABLE",
        "RESEARCH_XLSX_SIZE_LIMIT",
        "RESEARCH_XLSX_INVALID",
        "RESEARCH_XLSX_ENCRYPTED",
        "RESEARCH_XLSX_STRUCTURE_LIMIT",
        "RESEARCH_XLSX_FORMULA_UNSUPPORTED",
        "RESEARCH_XLSX_CONTENT_LIMIT",
        _PARSE_FAILED,
    }
)


class XlsxProcessingError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        if error_code not in _STABLE_ERROR_CODES:
            raise ValueError("不允许的科研 XLSX 处理错误码")
        super().__init__(error_code)
        self.error_code = error_code


class XlsxProcessor:
    def __init__(self, sandbox: Any) -> None:
        self._sandbox = sandbox

    async def process(self, downloaded: Any) -> ExtractedResearchXlsx:
        identity = _downloaded_identity(downloaded)
        try:
            parsed = await self._sandbox.parse(
                downloaded,
                profile="research_xlsx_v1",
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise XlsxProcessingError(_safe_error_code(error)) from None

        if (
            not isinstance(parsed, ParsedResearchXlsx)
            or parsed.attachment_id != identity[0]
            or parsed.document_version != identity[1]
            or parsed.mime_type != identity[2]
        ):
            raise XlsxProcessingError(_PARSE_FAILED)
        try:
            raw_normalized = parsed.normalized
            normalized = rebuild_research_xlsx_from_canonical_bytes(
                raw_normalized.descriptor_canonical_json_bytes,
                raw_normalized.chunk_canonical_json_bytes,
                descriptor_sha256=raw_normalized.descriptor_sha256,
                chunk_sha256s=raw_normalized.chunk_sha256s,
            )
            descriptor = normalized.descriptor
            sheets = tuple(
                _map_sheet(
                    sheet,
                    tuple(
                        chunk
                        for chunk in normalized.chunks
                        if chunk.sheet_ordinal == sheet.ordinal
                    ),
                )
                for sheet in descriptor.sheets
            )
            return ExtractedResearchXlsx(
                schema_version=descriptor.schema_version,
                date_system=descriptor.date_system,
                workbook_sheet_count=descriptor.workbook_sheet_count,
                empty_sheet_count=descriptor.empty_sheet_count,
                sheets=sheets,
                total_record_count=descriptor.total_record_count,
                total_data_row_count=descriptor.total_data_row_count,
                total_non_empty_cell_count=(
                    descriptor.total_non_empty_cell_count
                ),
                total_formula_like_cell_count=(
                    descriptor.total_formula_like_cell_count
                ),
                total_formula_cell_count=descriptor.total_formula_cell_count,
                total_merged_range_count=descriptor.total_merged_range_count,
                descriptor_sha256=descriptor.sha256,
            )
        except Exception:
            raise XlsxProcessingError(_PARSE_FAILED) from None


def _map_sheet(sheet: Any, chunks: tuple[Any, ...]) -> ExtractedXlsxSheet:
    extracted_chunks = tuple(
        ExtractedXlsxChunk(
            schema_version=chunk.schema_version,
            sheet_ordinal=chunk.sheet_ordinal,
            ordinal=chunk.ordinal,
            logical_row_start=chunk.logical_row_start,
            logical_row_end=chunk.logical_row_end,
            physical_row_start=chunk.physical_row_start,
            physical_row_end=chunk.physical_row_end,
            row_count=chunk.row_count,
            non_empty_cell_count=chunk.non_empty_cell_count,
            formula_like_cell_count=chunk.formula_like_cell_count,
            formula_cell_count=chunk.formula_cell_count,
            rows=tuple(
                ExtractedXlsxRow(
                    logical_row_number=row.logical_row_number,
                    physical_row_start=row.physical_row_start,
                    physical_row_end=row.physical_row_end,
                    values=row.values,
                    formula_cell_indexes=row.formula_cell_indexes,
                )
                for row in chunk.rows
            ),
            payload_sha256=chunk.sha256,
        )
        for chunk in chunks
    )
    descriptor_sha256 = build_research_xlsx_sheet_descriptor_sha256(
        ordinal=sheet.ordinal,
        name=sheet.name,
        visibility=sheet.visibility,
        headers=sheet.headers,
        header_row_start=sheet.header_row_start,
        header_row_end=sheet.header_row_end,
        physical_line_count=sheet.physical_line_count,
        record_count=sheet.record_count,
        data_row_count=sheet.data_row_count,
        column_count=sheet.column_count,
        non_empty_cell_count=sheet.non_empty_cell_count,
        formula_like_cell_count=sheet.formula_like_cell_count,
        formula_cell_count=sheet.formula_cell_count,
        merged_range_count=sheet.merged_range_count,
        missing_value_counts=sheet.missing_value_counts,
    )
    return ExtractedXlsxSheet(
        ordinal=sheet.ordinal,
        name=sheet.name,
        visibility=sheet.visibility,
        headers=sheet.headers,
        header_row_start=sheet.header_row_start,
        header_row_end=sheet.header_row_end,
        physical_line_count=sheet.physical_line_count,
        record_count=sheet.record_count,
        data_row_count=sheet.data_row_count,
        column_count=sheet.column_count,
        non_empty_cell_count=sheet.non_empty_cell_count,
        formula_like_cell_count=sheet.formula_like_cell_count,
        formula_cell_count=sheet.formula_cell_count,
        merged_range_count=sheet.merged_range_count,
        missing_value_counts=sheet.missing_value_counts,
        chunks=extracted_chunks,
        descriptor_sha256=descriptor_sha256,
    )


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
        or file_type != "xlsx"
        or mime_type != _XLSX_MIME_TYPE
        or type(size_bytes) is not int
        or not 1 <= size_bytes <= _MAX_XLSX_BYTES
        or page_count is not None
    ):
        raise XlsxProcessingError("RESEARCH_XLSX_INVALID")
    return attachment_id, document_version, mime_type


def _safe_error_code(error: Exception) -> str:
    error_code = getattr(error, "error_code", None)
    return error_code if error_code in _STABLE_ERROR_CODES else _PARSE_FAILED


def _value(source: Any, name: str) -> Any:
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


__all__ = ["XlsxProcessingError", "XlsxProcessor"]
