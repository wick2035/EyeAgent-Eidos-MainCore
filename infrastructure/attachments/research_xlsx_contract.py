import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any, Sequence


MAX_RESEARCH_XLSX_BYTES = 10 * 1024 * 1024
MAX_RESEARCH_XLSX_ZIP_ENTRIES = 512
MAX_RESEARCH_XLSX_ZIP_ENTRY_BYTES = 32 * 1024 * 1024
MAX_RESEARCH_XLSX_ZIP_TOTAL_BYTES = 64 * 1024 * 1024
MAX_RESEARCH_XLSX_COMPRESSION_RATIO = 100
MAX_RESEARCH_XLSX_SHEETS = 10
MAX_RESEARCH_XLSX_ROWS = 50_000
MAX_RESEARCH_XLSX_COLUMNS = 100
MAX_RESEARCH_XLSX_NON_EMPTY_CELLS = 2_000_000
MAX_RESEARCH_XLSX_CELL_CODEPOINTS = 32_767
MAX_RESEARCH_XLSX_CHUNK_ROWS = 500
TARGET_RESEARCH_XLSX_CHUNK_BYTES = 256 * 1024
MAX_RESEARCH_XLSX_DESCRIPTOR_BYTES = 16 * 1024 * 1024
MAX_RESEARCH_XLSX_CHUNK_BYTES = 16 * 1024 * 1024
MAX_RESEARCH_XLSX_CANONICAL_BYTES = 31 * 1024 * 1024

RESEARCH_XLSX_ERROR_CODES = frozenset(
    {
        "RESEARCH_XLSX_UNAVAILABLE",
        "RESEARCH_XLSX_SIZE_LIMIT",
        "RESEARCH_XLSX_INVALID",
        "RESEARCH_XLSX_ENCRYPTED",
        "RESEARCH_XLSX_STRUCTURE_LIMIT",
        "RESEARCH_XLSX_CONTENT_LIMIT",
        "RESEARCH_XLSX_FORMULA_UNSUPPORTED",
        "RESEARCH_XLSX_PARSE_FAILED",
    }
)

_DESCRIPTOR_SCHEMA = "research_xlsx_v1"
_CHUNK_SCHEMA = "research_xlsx_chunk_v1"
_VISIBILITIES = frozenset({"visible", "hidden", "veryHidden"})
_DATE_SYSTEMS = frozenset({"1900", "1904"})
_FORMULA_PREFIXES = frozenset("=+-@")
_ROW_KEYS = (
    "logical_row_number",
    "physical_row_start",
    "physical_row_end",
    "values",
    "formula_cell_indexes",
)
_CHUNK_KEYS = (
    "schema_version",
    "sheet_ordinal",
    "ordinal",
    "logical_row_start",
    "logical_row_end",
    "physical_row_start",
    "physical_row_end",
    "row_count",
    "non_empty_cell_count",
    "formula_like_cell_count",
    "formula_cell_count",
    "rows",
)
_SHEET_KEYS = (
    "ordinal",
    "name",
    "visibility",
    "headers",
    "header_row_start",
    "header_row_end",
    "physical_line_count",
    "record_count",
    "data_row_count",
    "column_count",
    "non_empty_cell_count",
    "formula_like_cell_count",
    "formula_cell_count",
    "merged_range_count",
    "missing_value_counts",
)
_DESCRIPTOR_KEYS = (
    "schema_version",
    "date_system",
    "workbook_sheet_count",
    "empty_sheet_count",
    "sheets",
    "total_record_count",
    "total_data_row_count",
    "total_non_empty_cell_count",
    "total_formula_like_cell_count",
    "total_formula_cell_count",
    "total_merged_range_count",
)


class ResearchXlsxContractError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        if error_code not in RESEARCH_XLSX_ERROR_CODES:
            raise ValueError("unsupported research XLSX error code")
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class XlsxRow:
    logical_row_number: int
    physical_row_start: int
    physical_row_end: int
    values: tuple[str, ...]
    formula_cell_indexes: tuple[int, ...]

    def to_json_value(self) -> dict[str, Any]:
        _validate_row(self)
        return {
            "logical_row_number": self.logical_row_number,
            "physical_row_start": self.physical_row_start,
            "physical_row_end": self.physical_row_end,
            "values": list(self.values),
            "formula_cell_indexes": list(self.formula_cell_indexes),
        }


@dataclass(frozen=True)
class XlsxChunk:
    schema_version: str
    sheet_ordinal: int
    ordinal: int
    logical_row_start: int
    logical_row_end: int
    physical_row_start: int
    physical_row_end: int
    row_count: int
    non_empty_cell_count: int
    formula_like_cell_count: int
    formula_cell_count: int
    rows: tuple[XlsxRow, ...]

    def to_canonical_json_bytes(self) -> bytes:
        return _canonical_json_bytes(_chunk_json_value(self))

    @property
    def canonical_json_bytes(self) -> bytes:
        return self.to_canonical_json_bytes()

    @property
    def canonical_bytes(self) -> bytes:
        return self.to_canonical_json_bytes()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_canonical_json_bytes()).hexdigest()

    @classmethod
    def from_canonical_json_bytes(
        cls,
        content: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> "XlsxChunk":
        value = _load_canonical_json(content, expected_sha256)
        chunk = _chunk_from_json_value(value)
        if chunk.to_canonical_json_bytes() != content:
            _invalid()
        return chunk


@dataclass(frozen=True)
class XlsxSheetDescriptor:
    ordinal: int
    name: str
    visibility: str
    headers: tuple[str, ...]
    header_row_start: int
    header_row_end: int
    physical_line_count: int
    record_count: int
    data_row_count: int
    column_count: int
    non_empty_cell_count: int
    formula_like_cell_count: int
    formula_cell_count: int
    merged_range_count: int
    missing_value_counts: tuple[int, ...]

    def to_json_value(self) -> dict[str, Any]:
        return _sheet_json_value(self)


@dataclass(frozen=True)
class XlsxDescriptor:
    schema_version: str
    date_system: str
    workbook_sheet_count: int
    empty_sheet_count: int
    sheets: tuple[XlsxSheetDescriptor, ...]
    total_record_count: int
    total_data_row_count: int
    total_non_empty_cell_count: int
    total_formula_like_cell_count: int
    total_formula_cell_count: int
    total_merged_range_count: int

    def to_canonical_json_bytes(self) -> bytes:
        return _canonical_json_bytes(_descriptor_json_value(self))

    @property
    def canonical_json_bytes(self) -> bytes:
        return self.to_canonical_json_bytes()

    @property
    def canonical_bytes(self) -> bytes:
        return self.to_canonical_json_bytes()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.to_canonical_json_bytes()).hexdigest()

    @classmethod
    def from_canonical_json_bytes(
        cls,
        content: bytes,
        *,
        expected_sha256: str | None = None,
    ) -> "XlsxDescriptor":
        value = _load_canonical_json(content, expected_sha256)
        descriptor = _descriptor_from_json_value(value)
        if descriptor.to_canonical_json_bytes() != content:
            _invalid()
        return descriptor


@dataclass(frozen=True)
class NormalizedResearchXlsx:
    descriptor: XlsxDescriptor
    chunks: tuple[XlsxChunk, ...]

    @property
    def descriptor_canonical_json_bytes(self) -> bytes:
        return self.descriptor.to_canonical_json_bytes()

    @property
    def descriptor_sha256(self) -> str:
        return self.descriptor.sha256

    @property
    def chunk_canonical_json_bytes(self) -> tuple[bytes, ...]:
        return tuple(chunk.to_canonical_json_bytes() for chunk in self.chunks)

    @property
    def chunk_sha256s(self) -> tuple[str, ...]:
        return tuple(chunk.sha256 for chunk in self.chunks)


def build_normalized_research_xlsx(
    descriptor: XlsxDescriptor,
    rows_by_sheet: Sequence[Sequence[XlsxRow]],
) -> NormalizedResearchXlsx:
    if (
        not isinstance(rows_by_sheet, (list, tuple))
        or len(rows_by_sheet) != len(descriptor.sheets)
    ):
        _invalid()
    chunks = tuple(
        chunk
        for sheet, rows in zip(descriptor.sheets, rows_by_sheet)
        for chunk in _build_sheet_chunks(sheet.ordinal, tuple(rows))
    )
    normalized = NormalizedResearchXlsx(descriptor=descriptor, chunks=chunks)
    _validate_normalized(normalized)
    _validate_canonical_artifact_sizes(
        normalized,
        error_code="RESEARCH_XLSX_CONTENT_LIMIT",
    )
    return normalized


def validate_canonical_research_xlsx_descriptor_bytes(
    content: bytes,
    *,
    expected_sha256: str | None = None,
) -> XlsxDescriptor:
    return XlsxDescriptor.from_canonical_json_bytes(
        content,
        expected_sha256=expected_sha256,
    )


def validate_canonical_research_xlsx_chunk_bytes(
    content: bytes,
    *,
    expected_sha256: str | None = None,
) -> XlsxChunk:
    return XlsxChunk.from_canonical_json_bytes(
        content,
        expected_sha256=expected_sha256,
    )


def rebuild_research_xlsx_from_canonical_bytes(
    descriptor_bytes: bytes,
    chunk_bytes: Sequence[bytes],
    *,
    descriptor_sha256: str | None = None,
    chunk_sha256s: Sequence[str] | None = None,
) -> NormalizedResearchXlsx:
    if not isinstance(chunk_bytes, (list, tuple)):
        _invalid()
    if chunk_sha256s is not None and (
        not isinstance(chunk_sha256s, (list, tuple))
        or len(chunk_sha256s) != len(chunk_bytes)
    ):
        _invalid()
    descriptor = validate_canonical_research_xlsx_descriptor_bytes(
        descriptor_bytes,
        expected_sha256=descriptor_sha256,
    )
    chunks = tuple(
        validate_canonical_research_xlsx_chunk_bytes(
            content,
            expected_sha256=(
                None if chunk_sha256s is None else chunk_sha256s[index]
            ),
        )
        for index, content in enumerate(chunk_bytes)
    )
    normalized = NormalizedResearchXlsx(descriptor=descriptor, chunks=chunks)
    _validate_normalized(normalized)
    _validate_canonical_artifact_sizes(
        normalized,
        error_code="RESEARCH_XLSX_INVALID",
    )
    return normalized


def _build_sheet_chunks(
    sheet_ordinal: int,
    rows: tuple[XlsxRow, ...],
) -> tuple[XlsxChunk, ...]:
    chunks: list[XlsxChunk] = []
    pending: list[XlsxRow] = []
    pending_row_bytes = 0
    pending_non_empty = 0
    pending_formula_like = 0
    pending_formula = 0
    for row in rows:
        row_bytes = len(_canonical_json_bytes(row.to_json_value()))
        row_non_empty = sum(bool(value) for value in row.values)
        row_formula_like = sum(_is_formula_like(value) for value in row.values)
        row_formula = len(row.formula_cell_indexes)
        candidate_count = len(pending) + 1
        candidate_size = _chunk_canonical_size(
            sheet_ordinal=sheet_ordinal,
            ordinal=len(chunks) + 1,
            first=pending[0] if pending else row,
            last=row,
            row_count=candidate_count,
            non_empty_cell_count=pending_non_empty + row_non_empty,
            formula_like_cell_count=(
                pending_formula_like + row_formula_like
            ),
            formula_cell_count=pending_formula + row_formula,
            row_json_bytes=pending_row_bytes + row_bytes,
        )
        if pending and (
            candidate_count > MAX_RESEARCH_XLSX_CHUNK_ROWS
            or candidate_size > TARGET_RESEARCH_XLSX_CHUNK_BYTES
        ):
            chunks.append(
                _make_chunk(sheet_ordinal, len(chunks) + 1, tuple(pending))
            )
            pending = [row]
            pending_row_bytes = row_bytes
            pending_non_empty = row_non_empty
            pending_formula_like = row_formula_like
            pending_formula = row_formula
        else:
            pending.append(row)
            pending_row_bytes += row_bytes
            pending_non_empty += row_non_empty
            pending_formula_like += row_formula_like
            pending_formula += row_formula
    if pending:
        chunks.append(
            _make_chunk(sheet_ordinal, len(chunks) + 1, tuple(pending))
        )
    return tuple(chunks)


def _chunk_canonical_size(
    *,
    sheet_ordinal: int,
    ordinal: int,
    first: XlsxRow,
    last: XlsxRow,
    row_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    formula_cell_count: int,
    row_json_bytes: int,
) -> int:
    empty_rows_value = {
        "schema_version": _CHUNK_SCHEMA,
        "sheet_ordinal": sheet_ordinal,
        "ordinal": ordinal,
        "logical_row_start": first.logical_row_number,
        "logical_row_end": last.logical_row_number,
        "physical_row_start": first.physical_row_start,
        "physical_row_end": last.physical_row_end,
        "row_count": row_count,
        "non_empty_cell_count": non_empty_cell_count,
        "formula_like_cell_count": formula_like_cell_count,
        "formula_cell_count": formula_cell_count,
        "rows": [],
    }
    return (
        len(_canonical_json_bytes(empty_rows_value))
        + row_json_bytes
        + row_count
        - 1
    )


def _make_chunk(
    sheet_ordinal: int,
    ordinal: int,
    rows: tuple[XlsxRow, ...],
) -> XlsxChunk:
    first = rows[0]
    last = rows[-1]
    return XlsxChunk(
        schema_version=_CHUNK_SCHEMA,
        sheet_ordinal=sheet_ordinal,
        ordinal=ordinal,
        logical_row_start=first.logical_row_number,
        logical_row_end=last.logical_row_number,
        physical_row_start=first.physical_row_start,
        physical_row_end=last.physical_row_end,
        row_count=len(rows),
        non_empty_cell_count=sum(
            bool(value) for row in rows for value in row.values
        ),
        formula_like_cell_count=sum(
            _is_formula_like(value) for row in rows for value in row.values
        ),
        formula_cell_count=sum(len(row.formula_cell_indexes) for row in rows),
        rows=rows,
    )


def _validate_normalized(normalized: NormalizedResearchXlsx) -> None:
    descriptor = normalized.descriptor
    _descriptor_json_value(descriptor)
    chunks = normalized.chunks
    if not isinstance(chunks, tuple):
        _invalid()

    chunks_by_sheet: dict[int, list[XlsxChunk]] = {
        sheet.ordinal: [] for sheet in descriptor.sheets
    }
    previous_key: tuple[int, int] | None = None
    for chunk in chunks:
        _chunk_json_value(chunk)
        key = (chunk.sheet_ordinal, chunk.ordinal)
        if previous_key is not None and key <= previous_key:
            _invalid()
        previous_key = key
        if chunk.sheet_ordinal not in chunks_by_sheet:
            _invalid()
        chunks_by_sheet[chunk.sheet_ordinal].append(chunk)

    for sheet in descriptor.sheets:
        sheet_chunks = tuple(chunks_by_sheet[sheet.ordinal])
        rows = tuple(row for chunk in sheet_chunks for row in chunk.rows)
        if len(rows) != sheet.data_row_count:
            _invalid()
        for index, row in enumerate(rows, start=1):
            if (
                row.logical_row_number != index
                or row.physical_row_start != sheet.header_row_end + index
                or row.physical_row_end != row.physical_row_start
                or len(row.values) != sheet.column_count
            ):
                _invalid()
        if rows:
            if rows[-1].physical_row_end != sheet.physical_line_count:
                _invalid()
        elif sheet.physical_line_count != sheet.header_row_end:
            _invalid()

        expected_missing = tuple(
            sum(row.values[column] == "" for row in rows)
            for column in range(sheet.column_count)
        )
        expected_non_empty = sum(bool(value) for value in sheet.headers) + sum(
            bool(value) for row in rows for value in row.values
        )
        expected_formula_like = sum(
            _is_formula_like(value) for value in sheet.headers
        ) + sum(
            _is_formula_like(value) for row in rows for value in row.values
        )
        expected_formula = sum(
            len(row.formula_cell_indexes) for row in rows
        )
        if (
            sheet.missing_value_counts != expected_missing
            or sheet.non_empty_cell_count != expected_non_empty
            or sheet.formula_like_cell_count != expected_formula_like
            or sheet.formula_cell_count != expected_formula
        ):
            _invalid()
        expected_chunks = _build_sheet_chunks(sheet.ordinal, rows)
        if sheet_chunks != expected_chunks:
            _invalid()


def _descriptor_json_value(descriptor: XlsxDescriptor) -> dict[str, Any]:
    if (
        descriptor.schema_version != _DESCRIPTOR_SCHEMA
        or descriptor.date_system not in _DATE_SYSTEMS
        or not _positive_int(descriptor.workbook_sheet_count)
        or descriptor.workbook_sheet_count > MAX_RESEARCH_XLSX_SHEETS
        or not _non_negative_int(descriptor.empty_sheet_count)
        or not isinstance(descriptor.sheets, tuple)
        or not descriptor.sheets
        or len(descriptor.sheets) + descriptor.empty_sheet_count
        != descriptor.workbook_sheet_count
        or any(
            descriptor.sheets[index].ordinal
            <= descriptor.sheets[index - 1].ordinal
            for index in range(1, len(descriptor.sheets))
        )
        or len({sheet.name.casefold() for sheet in descriptor.sheets})
        != len(descriptor.sheets)
        or descriptor.sheets[-1].ordinal >= descriptor.workbook_sheet_count
        or any(sheet.ordinal < 0 for sheet in descriptor.sheets)
        or not _non_negative_int(descriptor.total_record_count)
        or not _non_negative_int(descriptor.total_data_row_count)
        or descriptor.total_data_row_count > MAX_RESEARCH_XLSX_ROWS
        or not _non_negative_int(descriptor.total_non_empty_cell_count)
        or descriptor.total_non_empty_cell_count
        > MAX_RESEARCH_XLSX_NON_EMPTY_CELLS
        or not _non_negative_int(descriptor.total_formula_like_cell_count)
        or not _non_negative_int(descriptor.total_formula_cell_count)
        or not _non_negative_int(descriptor.total_merged_range_count)
    ):
        _invalid()
    sheets = [sheet.to_json_value() for sheet in descriptor.sheets]
    if (
        descriptor.total_record_count
        != sum(sheet.record_count for sheet in descriptor.sheets)
        or descriptor.total_data_row_count
        != sum(sheet.data_row_count for sheet in descriptor.sheets)
        or descriptor.total_non_empty_cell_count
        != sum(sheet.non_empty_cell_count for sheet in descriptor.sheets)
        or descriptor.total_formula_like_cell_count
        != sum(sheet.formula_like_cell_count for sheet in descriptor.sheets)
        or descriptor.total_formula_cell_count
        != sum(sheet.formula_cell_count for sheet in descriptor.sheets)
        or descriptor.total_merged_range_count
        != sum(sheet.merged_range_count for sheet in descriptor.sheets)
        or descriptor.total_formula_cell_count
        > descriptor.total_formula_like_cell_count
        or descriptor.total_formula_like_cell_count
        > descriptor.total_non_empty_cell_count
    ):
        _invalid()
    return {
        "schema_version": descriptor.schema_version,
        "date_system": descriptor.date_system,
        "workbook_sheet_count": descriptor.workbook_sheet_count,
        "empty_sheet_count": descriptor.empty_sheet_count,
        "sheets": sheets,
        "total_record_count": descriptor.total_record_count,
        "total_data_row_count": descriptor.total_data_row_count,
        "total_non_empty_cell_count": descriptor.total_non_empty_cell_count,
        "total_formula_like_cell_count": descriptor.total_formula_like_cell_count,
        "total_formula_cell_count": descriptor.total_formula_cell_count,
        "total_merged_range_count": descriptor.total_merged_range_count,
    }


def _sheet_json_value(sheet: XlsxSheetDescriptor) -> dict[str, Any]:
    if (
        not _non_negative_int(sheet.ordinal)
        or not _is_nfc_string(sheet.name)
        or not sheet.name
        or len(sheet.name) > 31
        or any(
            unicodedata.category(character).startswith("C")
            for character in sheet.name
        )
        or sheet.visibility not in _VISIBILITIES
        or not isinstance(sheet.headers, tuple)
        or not sheet.headers
        or any(
            not _is_nfc_string(value)
            or not value
            or value.strip() != value
            or len(value) > MAX_RESEARCH_XLSX_CELL_CODEPOINTS
            for value in sheet.headers
        )
        or len(set(sheet.headers)) != len(sheet.headers)
        or not _positive_int(sheet.header_row_start)
        or not _positive_int(sheet.header_row_end)
        or sheet.header_row_start != sheet.header_row_end
        or not _positive_int(sheet.physical_line_count)
        or sheet.physical_line_count > MAX_RESEARCH_XLSX_ROWS
        or sheet.physical_line_count < sheet.header_row_end
        or not _positive_int(sheet.record_count)
        or not _non_negative_int(sheet.data_row_count)
        or sheet.data_row_count > MAX_RESEARCH_XLSX_ROWS
        or sheet.record_count != sheet.data_row_count + 1
        or sheet.physical_line_count - sheet.header_row_end
        != sheet.data_row_count
        or not _positive_int(sheet.column_count)
        or sheet.column_count > MAX_RESEARCH_XLSX_COLUMNS
        or len(sheet.headers) != sheet.column_count
        or not _non_negative_int(sheet.non_empty_cell_count)
        or sheet.non_empty_cell_count > MAX_RESEARCH_XLSX_NON_EMPTY_CELLS
        or not _non_negative_int(sheet.formula_like_cell_count)
        or sheet.formula_like_cell_count > sheet.non_empty_cell_count
        or not _non_negative_int(sheet.formula_cell_count)
        or sheet.formula_cell_count > sheet.formula_like_cell_count
        or not _non_negative_int(sheet.merged_range_count)
        or not isinstance(sheet.missing_value_counts, tuple)
        or len(sheet.missing_value_counts) != sheet.column_count
        or any(
            not _non_negative_int(value) or value > sheet.data_row_count
            for value in sheet.missing_value_counts
        )
    ):
        _invalid()
    return {
        "ordinal": sheet.ordinal,
        "name": sheet.name,
        "visibility": sheet.visibility,
        "headers": list(sheet.headers),
        "header_row_start": sheet.header_row_start,
        "header_row_end": sheet.header_row_end,
        "physical_line_count": sheet.physical_line_count,
        "record_count": sheet.record_count,
        "data_row_count": sheet.data_row_count,
        "column_count": sheet.column_count,
        "non_empty_cell_count": sheet.non_empty_cell_count,
        "formula_like_cell_count": sheet.formula_like_cell_count,
        "formula_cell_count": sheet.formula_cell_count,
        "merged_range_count": sheet.merged_range_count,
        "missing_value_counts": list(sheet.missing_value_counts),
    }


def _chunk_json_value(chunk: XlsxChunk) -> dict[str, Any]:
    if (
        chunk.schema_version != _CHUNK_SCHEMA
        or not _non_negative_int(chunk.sheet_ordinal)
        or not _positive_int(chunk.ordinal)
        or not _positive_int(chunk.logical_row_start)
        or not _positive_int(chunk.logical_row_end)
        or chunk.logical_row_end < chunk.logical_row_start
        or not _positive_int(chunk.physical_row_start)
        or not _positive_int(chunk.physical_row_end)
        or chunk.physical_row_end < chunk.physical_row_start
        or not _positive_int(chunk.row_count)
        or chunk.row_count > MAX_RESEARCH_XLSX_CHUNK_ROWS
        or not _non_negative_int(chunk.non_empty_cell_count)
        or not _non_negative_int(chunk.formula_like_cell_count)
        or not _non_negative_int(chunk.formula_cell_count)
        or not isinstance(chunk.rows, tuple)
        or len(chunk.rows) != chunk.row_count
    ):
        _invalid()
    rows = [row.to_json_value() for row in chunk.rows]
    if (
        chunk.logical_row_start != chunk.rows[0].logical_row_number
        or chunk.logical_row_end != chunk.rows[-1].logical_row_number
        or chunk.physical_row_start != chunk.rows[0].physical_row_start
        or chunk.physical_row_end != chunk.rows[-1].physical_row_end
        or chunk.non_empty_cell_count
        != sum(bool(value) for row in chunk.rows for value in row.values)
        or chunk.formula_like_cell_count
        != sum(_is_formula_like(value) for row in chunk.rows for value in row.values)
        or chunk.formula_cell_count
        != sum(len(row.formula_cell_indexes) for row in chunk.rows)
        or chunk.formula_cell_count > chunk.formula_like_cell_count
        or chunk.formula_like_cell_count > chunk.non_empty_cell_count
        or any(
            row.logical_row_number != chunk.logical_row_start + index
            for index, row in enumerate(chunk.rows)
        )
        or any(
            chunk.rows[index].physical_row_start
            != chunk.rows[index - 1].physical_row_end + 1
            for index in range(1, len(chunk.rows))
        )
        or any(
            row.physical_row_start != row.physical_row_end
            or len(row.values) != len(chunk.rows[0].values)
            for row in chunk.rows
        )
    ):
        _invalid()
    return {
        "schema_version": chunk.schema_version,
        "sheet_ordinal": chunk.sheet_ordinal,
        "ordinal": chunk.ordinal,
        "logical_row_start": chunk.logical_row_start,
        "logical_row_end": chunk.logical_row_end,
        "physical_row_start": chunk.physical_row_start,
        "physical_row_end": chunk.physical_row_end,
        "row_count": chunk.row_count,
        "non_empty_cell_count": chunk.non_empty_cell_count,
        "formula_like_cell_count": chunk.formula_like_cell_count,
        "formula_cell_count": chunk.formula_cell_count,
        "rows": rows,
    }


def _validate_row(row: XlsxRow) -> None:
    if (
        not _positive_int(row.logical_row_number)
        or not _positive_int(row.physical_row_start)
        or not _positive_int(row.physical_row_end)
        or row.physical_row_start != row.physical_row_end
        or row.physical_row_end > MAX_RESEARCH_XLSX_ROWS
        or not isinstance(row.values, tuple)
        or not row.values
        or len(row.values) > MAX_RESEARCH_XLSX_COLUMNS
        or any(
            not _is_nfc_string(value)
            or len(value) > MAX_RESEARCH_XLSX_CELL_CODEPOINTS
            for value in row.values
        )
        or not isinstance(row.formula_cell_indexes, tuple)
        or any(type(index) is not int for index in row.formula_cell_indexes)
        or tuple(sorted(set(row.formula_cell_indexes)))
        != row.formula_cell_indexes
        or any(
            index < 0
            or index >= len(row.values)
            or not row.values[index].startswith("=")
            for index in row.formula_cell_indexes
        )
    ):
        _invalid()


def _descriptor_from_json_value(value: Any) -> XlsxDescriptor:
    _require_exact_object(value, _DESCRIPTOR_KEYS)
    raw_sheets = value["sheets"]
    if not isinstance(raw_sheets, list):
        _invalid()
    descriptor = XlsxDescriptor(
        schema_version=value["schema_version"],
        date_system=value["date_system"],
        workbook_sheet_count=value["workbook_sheet_count"],
        empty_sheet_count=value["empty_sheet_count"],
        sheets=tuple(_sheet_from_json_value(sheet) for sheet in raw_sheets),
        total_record_count=value["total_record_count"],
        total_data_row_count=value["total_data_row_count"],
        total_non_empty_cell_count=value["total_non_empty_cell_count"],
        total_formula_like_cell_count=value[
            "total_formula_like_cell_count"
        ],
        total_formula_cell_count=value["total_formula_cell_count"],
        total_merged_range_count=value["total_merged_range_count"],
    )
    _descriptor_json_value(descriptor)
    return descriptor


def _sheet_from_json_value(value: Any) -> XlsxSheetDescriptor:
    _require_exact_object(value, _SHEET_KEYS)
    sheet = XlsxSheetDescriptor(
        ordinal=value["ordinal"],
        name=value["name"],
        visibility=value["visibility"],
        headers=_string_tuple(value["headers"]),
        header_row_start=value["header_row_start"],
        header_row_end=value["header_row_end"],
        physical_line_count=value["physical_line_count"],
        record_count=value["record_count"],
        data_row_count=value["data_row_count"],
        column_count=value["column_count"],
        non_empty_cell_count=value["non_empty_cell_count"],
        formula_like_cell_count=value["formula_like_cell_count"],
        formula_cell_count=value["formula_cell_count"],
        merged_range_count=value["merged_range_count"],
        missing_value_counts=_int_tuple(value["missing_value_counts"]),
    )
    _sheet_json_value(sheet)
    return sheet


def _chunk_from_json_value(value: Any) -> XlsxChunk:
    _require_exact_object(value, _CHUNK_KEYS)
    raw_rows = value["rows"]
    if not isinstance(raw_rows, list):
        _invalid()
    chunk = XlsxChunk(
        schema_version=value["schema_version"],
        sheet_ordinal=value["sheet_ordinal"],
        ordinal=value["ordinal"],
        logical_row_start=value["logical_row_start"],
        logical_row_end=value["logical_row_end"],
        physical_row_start=value["physical_row_start"],
        physical_row_end=value["physical_row_end"],
        row_count=value["row_count"],
        non_empty_cell_count=value["non_empty_cell_count"],
        formula_like_cell_count=value["formula_like_cell_count"],
        formula_cell_count=value["formula_cell_count"],
        rows=tuple(_row_from_json_value(row) for row in raw_rows),
    )
    _chunk_json_value(chunk)
    return chunk


def _row_from_json_value(value: Any) -> XlsxRow:
    _require_exact_object(value, _ROW_KEYS)
    row = XlsxRow(
        logical_row_number=value["logical_row_number"],
        physical_row_start=value["physical_row_start"],
        physical_row_end=value["physical_row_end"],
        values=_string_tuple(value["values"]),
        formula_cell_indexes=_int_tuple(value["formula_cell_indexes"]),
    )
    _validate_row(row)
    return row


def _validate_canonical_artifact_sizes(
    normalized: NormalizedResearchXlsx,
    *,
    error_code: str,
) -> None:
    descriptor_bytes = normalized.descriptor.to_canonical_json_bytes()
    chunk_bytes = tuple(
        chunk.to_canonical_json_bytes() for chunk in normalized.chunks
    )
    if (
        len(descriptor_bytes) > MAX_RESEARCH_XLSX_DESCRIPTOR_BYTES
        or any(
            len(content) > MAX_RESEARCH_XLSX_CHUNK_BYTES
            for content in chunk_bytes
        )
        or len(descriptor_bytes) + sum(map(len, chunk_bytes))
        > MAX_RESEARCH_XLSX_CANONICAL_BYTES
    ):
        raise ResearchXlsxContractError(error_code)


def _load_canonical_json(content: bytes, expected_sha256: str | None) -> Any:
    if not isinstance(content, bytes) or not content:
        _invalid()
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or expected_sha256.lower() != expected_sha256
        or any(
            character not in "0123456789abcdef"
            for character in expected_sha256
        )
        or actual_sha256 != expected_sha256
    ):
        _invalid()
    try:
        decoded = content.decode("utf-8", "strict")
        value = json.loads(
            decoded,
            object_pairs_hook=_object_without_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _invalid()
    return value


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _require_exact_object(value: Any, keys: tuple[str, ...]) -> None:
    if not isinstance(value, dict) or tuple(value) != keys:
        _invalid()


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        _invalid()
    return tuple(value)


def _int_tuple(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list) or any(type(item) is not int for item in value):
        _invalid()
    return tuple(value)


def _is_formula_like(value: str) -> bool:
    stripped = value.lstrip()
    return bool(stripped and stripped[0] in _FORMULA_PREFIXES)


def _is_nfc_string(value: Any) -> bool:
    return (
        isinstance(value, str)
        and "\x00" not in value
        and not any(0xD800 <= ord(character) <= 0xDFFF for character in value)
        and unicodedata.normalize("NFC", value) == value
    )


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _non_negative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _invalid() -> None:
    raise ResearchXlsxContractError("RESEARCH_XLSX_INVALID")


__all__ = [
    "MAX_RESEARCH_XLSX_BYTES",
    "MAX_RESEARCH_XLSX_CANONICAL_BYTES",
    "MAX_RESEARCH_XLSX_CELL_CODEPOINTS",
    "MAX_RESEARCH_XLSX_CHUNK_BYTES",
    "MAX_RESEARCH_XLSX_CHUNK_ROWS",
    "MAX_RESEARCH_XLSX_COLUMNS",
    "MAX_RESEARCH_XLSX_COMPRESSION_RATIO",
    "MAX_RESEARCH_XLSX_DESCRIPTOR_BYTES",
    "MAX_RESEARCH_XLSX_NON_EMPTY_CELLS",
    "MAX_RESEARCH_XLSX_ROWS",
    "MAX_RESEARCH_XLSX_SHEETS",
    "MAX_RESEARCH_XLSX_ZIP_ENTRIES",
    "MAX_RESEARCH_XLSX_ZIP_ENTRY_BYTES",
    "MAX_RESEARCH_XLSX_ZIP_TOTAL_BYTES",
    "RESEARCH_XLSX_ERROR_CODES",
    "TARGET_RESEARCH_XLSX_CHUNK_BYTES",
    "NormalizedResearchXlsx",
    "ResearchXlsxContractError",
    "XlsxChunk",
    "XlsxDescriptor",
    "XlsxRow",
    "XlsxSheetDescriptor",
    "build_normalized_research_xlsx",
    "rebuild_research_xlsx_from_canonical_bytes",
    "validate_canonical_research_xlsx_chunk_bytes",
    "validate_canonical_research_xlsx_descriptor_bytes",
]
