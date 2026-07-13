import csv
import hashlib
import io
import json
import threading
import unicodedata
from dataclasses import dataclass
from typing import Any, Sequence


MAX_RESEARCH_CSV_BYTES = 10 * 1024 * 1024
MAX_RESEARCH_CSV_PHYSICAL_LINES = 50_000
MAX_RESEARCH_CSV_RECORDS = 50_000
MAX_RESEARCH_CSV_COLUMNS = 100
MAX_RESEARCH_CSV_NON_EMPTY_CELLS = 2_000_000
MAX_RESEARCH_CSV_CHUNK_RECORDS = 500
TARGET_RESEARCH_CSV_CHUNK_BYTES = 256 * 1024
MAX_RESEARCH_CSV_DESCRIPTOR_BYTES = 16 * 1024 * 1024
MAX_RESEARCH_CSV_CHUNK_BYTES = 16 * 1024 * 1024
MAX_RESEARCH_CSV_CANONICAL_BYTES = 31 * 1024 * 1024

RESEARCH_CSV_ERROR_CODES = frozenset(
    {
        "RESEARCH_CSV_UNAVAILABLE",
        "RESEARCH_CSV_SIZE_LIMIT",
        "RESEARCH_CSV_INVALID",
        "RESEARCH_CSV_ENCODING_UNSUPPORTED",
        "RESEARCH_CSV_STRUCTURE_LIMIT",
        "RESEARCH_CSV_CONTENT_LIMIT",
        "RESEARCH_CSV_PARSE_FAILED",
    }
)

_DESCRIPTOR_SCHEMA = "research_csv_v1"
_CHUNK_SCHEMA = "research_csv_chunk_v1"
_FORMULA_PREFIXES = frozenset("=+-@")
_CSV_FIELD_LIMIT_LOCK = threading.Lock()
_DESCRIPTOR_KEYS = (
    "schema_version",
    "sheet_name",
    "headers",
    "header_row_start",
    "header_row_end",
    "physical_line_count",
    "record_count",
    "data_row_count",
    "column_count",
    "non_empty_cell_count",
    "formula_like_cell_count",
    "missing_value_counts",
)
_ROW_KEYS = (
    "logical_row_number",
    "physical_row_start",
    "physical_row_end",
    "values",
)
_CHUNK_KEYS = (
    "schema_version",
    "ordinal",
    "logical_row_start",
    "logical_row_end",
    "physical_row_start",
    "physical_row_end",
    "row_count",
    "non_empty_cell_count",
    "formula_like_cell_count",
    "rows",
)


class ResearchCsvContractError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        if error_code not in RESEARCH_CSV_ERROR_CODES:
            raise ValueError("unsupported research CSV error code")
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class CsvRow:
    logical_row_number: int
    physical_row_start: int
    physical_row_end: int
    values: tuple[str, ...]

    def to_json_value(self) -> dict[str, Any]:
        _validate_row(self)
        return {
            "logical_row_number": self.logical_row_number,
            "physical_row_start": self.physical_row_start,
            "physical_row_end": self.physical_row_end,
            "values": list(self.values),
        }


@dataclass(frozen=True)
class CsvDescriptor:
    schema_version: str
    sheet_name: str
    headers: tuple[str, ...]
    header_row_start: int
    header_row_end: int
    physical_line_count: int
    record_count: int
    data_row_count: int
    column_count: int
    non_empty_cell_count: int
    formula_like_cell_count: int
    missing_value_counts: tuple[int, ...]

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
    ) -> "CsvDescriptor":
        value = _load_canonical_json(content, expected_sha256)
        descriptor = _descriptor_from_json_value(value)
        if descriptor.to_canonical_json_bytes() != content:
            _invalid()
        return descriptor


@dataclass(frozen=True)
class CsvChunk:
    schema_version: str
    ordinal: int
    logical_row_start: int
    logical_row_end: int
    physical_row_start: int
    physical_row_end: int
    row_count: int
    non_empty_cell_count: int
    formula_like_cell_count: int
    rows: tuple[CsvRow, ...]

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
    ) -> "CsvChunk":
        value = _load_canonical_json(content, expected_sha256)
        chunk = _chunk_from_json_value(value)
        if chunk.to_canonical_json_bytes() != content:
            _invalid()
        return chunk


@dataclass(frozen=True)
class NormalizedResearchCsv:
    descriptor: CsvDescriptor
    rows: tuple[CsvRow, ...]
    chunks: tuple[CsvChunk, ...]

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


def parse_research_csv_bytes(raw: bytes) -> NormalizedResearchCsv:
    if not isinstance(raw, bytes) or not raw:
        raise ResearchCsvContractError("RESEARCH_CSV_INVALID")
    if len(raw) > MAX_RESEARCH_CSV_BYTES:
        raise ResearchCsvContractError("RESEARCH_CSV_SIZE_LIMIT")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ResearchCsvContractError(
            "RESEARCH_CSV_ENCODING_UNSUPPORTED"
        )

    encoded = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        decoded = encoded.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise ResearchCsvContractError(
            "RESEARCH_CSV_ENCODING_UNSUPPORTED"
        ) from None
    if "\x00" in decoded:
        raise ResearchCsvContractError("RESEARCH_CSV_INVALID")

    physical_line_count = _physical_line_count(decoded)
    if physical_line_count > MAX_RESEARCH_CSV_PHYSICAL_LINES:
        raise ResearchCsvContractError("RESEARCH_CSV_STRUCTURE_LIMIT")
    _validate_rfc4180_syntax(decoded)

    parsed_records: list[tuple[int, int, tuple[str, ...]]] = []
    reader = csv.reader(
        io.StringIO(decoded, newline=""),
        delimiter=",",
        quotechar='"',
        doublequote=True,
        skipinitialspace=False,
        strict=True,
    )
    previous_line = 0
    with _CSV_FIELD_LIMIT_LOCK:
        previous_field_limit = csv.field_size_limit()
        csv.field_size_limit(MAX_RESEARCH_CSV_BYTES)
        try:
            for record in reader:
                if len(parsed_records) >= MAX_RESEARCH_CSV_RECORDS:
                    raise ResearchCsvContractError(
                        "RESEARCH_CSV_STRUCTURE_LIMIT"
                    )
                normalized = tuple(_normalize_cell(cell) for cell in record)
                parsed_records.append(
                    (previous_line + 1, reader.line_num, normalized)
                )
                previous_line = reader.line_num
        except ResearchCsvContractError:
            raise
        except csv.Error:
            raise ResearchCsvContractError("RESEARCH_CSV_INVALID") from None
        except Exception:
            raise ResearchCsvContractError(
                "RESEARCH_CSV_PARSE_FAILED"
            ) from None
        finally:
            csv.field_size_limit(previous_field_limit)

    header_index = next(
        (
            index
            for index, (_, _, values) in enumerate(parsed_records)
            if any(value.strip() for value in values)
        ),
        None,
    )
    if header_index is None:
        raise ResearchCsvContractError("RESEARCH_CSV_INVALID")

    header_start, header_end, raw_headers = parsed_records[header_index]
    headers = tuple(value.strip() for value in raw_headers)
    if not headers or any(not header for header in headers):
        raise ResearchCsvContractError("RESEARCH_CSV_INVALID")
    if len(headers) > MAX_RESEARCH_CSV_COLUMNS:
        raise ResearchCsvContractError("RESEARCH_CSV_STRUCTURE_LIMIT")
    if len(set(headers)) != len(headers):
        raise ResearchCsvContractError("RESEARCH_CSV_INVALID")

    rows: list[CsvRow] = []
    missing_value_counts = [0] * len(headers)
    non_empty_cell_count = sum(bool(value) for value in headers)
    formula_like_cell_count = sum(_is_formula_like(value) for value in headers)
    data_records = parsed_records[header_index + 1 :]
    if len(data_records) + 1 > MAX_RESEARCH_CSV_RECORDS:
        raise ResearchCsvContractError("RESEARCH_CSV_STRUCTURE_LIMIT")

    for logical_row_number, (physical_start, physical_end, values) in enumerate(
        data_records,
        start=1,
    ):
        if len(values) != len(headers):
            raise ResearchCsvContractError("RESEARCH_CSV_INVALID")
        row = CsvRow(
            logical_row_number=logical_row_number,
            physical_row_start=physical_start,
            physical_row_end=physical_end,
            values=values,
        )
        rows.append(row)
        for column, value in enumerate(values):
            if value:
                non_empty_cell_count += 1
                formula_like_cell_count += _is_formula_like(value)
            else:
                missing_value_counts[column] += 1
        if non_empty_cell_count > MAX_RESEARCH_CSV_NON_EMPTY_CELLS:
            raise ResearchCsvContractError("RESEARCH_CSV_CONTENT_LIMIT")

    descriptor = CsvDescriptor(
        schema_version=_DESCRIPTOR_SCHEMA,
        sheet_name="CSV",
        headers=headers,
        header_row_start=header_start,
        header_row_end=header_end,
        physical_line_count=physical_line_count,
        record_count=1 + len(rows),
        data_row_count=len(rows),
        column_count=len(headers),
        non_empty_cell_count=non_empty_cell_count,
        formula_like_cell_count=formula_like_cell_count,
        missing_value_counts=tuple(missing_value_counts),
    )
    normalized = NormalizedResearchCsv(
        descriptor=descriptor,
        rows=tuple(rows),
        chunks=_build_chunks(rows),
    )
    _validate_normalized(normalized)
    _validate_canonical_artifact_sizes(
        normalized,
        error_code="RESEARCH_CSV_CONTENT_LIMIT",
    )
    return normalized


def validate_canonical_research_csv_descriptor_bytes(
    content: bytes,
    *,
    expected_sha256: str | None = None,
) -> CsvDescriptor:
    return CsvDescriptor.from_canonical_json_bytes(
        content,
        expected_sha256=expected_sha256,
    )


def validate_canonical_research_csv_chunk_bytes(
    content: bytes,
    *,
    expected_sha256: str | None = None,
) -> CsvChunk:
    return CsvChunk.from_canonical_json_bytes(
        content,
        expected_sha256=expected_sha256,
    )


def rebuild_research_csv_from_canonical_bytes(
    descriptor_bytes: bytes,
    chunk_bytes: Sequence[bytes],
    *,
    descriptor_sha256: str | None = None,
    chunk_sha256s: Sequence[str] | None = None,
) -> NormalizedResearchCsv:
    if not isinstance(chunk_bytes, (list, tuple)):
        _invalid()
    if chunk_sha256s is not None and (
        not isinstance(chunk_sha256s, (list, tuple))
        or len(chunk_sha256s) != len(chunk_bytes)
    ):
        _invalid()
    descriptor = validate_canonical_research_csv_descriptor_bytes(
        descriptor_bytes,
        expected_sha256=descriptor_sha256,
    )
    chunks = tuple(
        validate_canonical_research_csv_chunk_bytes(
            content,
            expected_sha256=(
                None if chunk_sha256s is None else chunk_sha256s[index]
            ),
        )
        for index, content in enumerate(chunk_bytes)
    )
    normalized = NormalizedResearchCsv(
        descriptor=descriptor,
        rows=tuple(row for chunk in chunks for row in chunk.rows),
        chunks=chunks,
    )
    _validate_normalized(normalized)
    _validate_canonical_artifact_sizes(
        normalized,
        error_code="RESEARCH_CSV_INVALID",
    )
    return normalized


def _build_chunks(rows: Sequence[CsvRow]) -> tuple[CsvChunk, ...]:
    chunks: list[CsvChunk] = []
    pending: list[CsvRow] = []
    pending_row_bytes = 0
    pending_non_empty = 0
    pending_formula_like = 0
    for row in rows:
        row_bytes = len(_canonical_json_bytes(row.to_json_value()))
        row_non_empty = sum(bool(value) for value in row.values)
        row_formula_like = sum(_is_formula_like(value) for value in row.values)
        candidate_count = len(pending) + 1
        candidate_size = _chunk_canonical_size(
            ordinal=len(chunks) + 1,
            first=pending[0] if pending else row,
            last=row,
            row_count=candidate_count,
            non_empty_cell_count=pending_non_empty + row_non_empty,
            formula_like_cell_count=pending_formula_like + row_formula_like,
            row_json_bytes=pending_row_bytes + row_bytes,
        )
        if pending and (
            candidate_count > MAX_RESEARCH_CSV_CHUNK_RECORDS
            or candidate_size > TARGET_RESEARCH_CSV_CHUNK_BYTES
        ):
            chunks.append(_make_chunk(len(chunks) + 1, pending))
            pending = [row]
            pending_row_bytes = row_bytes
            pending_non_empty = row_non_empty
            pending_formula_like = row_formula_like
        else:
            pending.append(row)
            pending_row_bytes += row_bytes
            pending_non_empty += row_non_empty
            pending_formula_like += row_formula_like
    if pending:
        chunks.append(_make_chunk(len(chunks) + 1, pending))
    return tuple(chunks)


def _chunk_canonical_size(
    *,
    ordinal: int,
    first: CsvRow,
    last: CsvRow,
    row_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    row_json_bytes: int,
) -> int:
    empty_rows_value = {
        "schema_version": _CHUNK_SCHEMA,
        "ordinal": ordinal,
        "logical_row_start": first.logical_row_number,
        "logical_row_end": last.logical_row_number,
        "physical_row_start": first.physical_row_start,
        "physical_row_end": last.physical_row_end,
        "row_count": row_count,
        "non_empty_cell_count": non_empty_cell_count,
        "formula_like_cell_count": formula_like_cell_count,
        "rows": [],
    }
    return (
        len(_canonical_json_bytes(empty_rows_value))
        + row_json_bytes
        + row_count
        - 1
    )


def _make_chunk(ordinal: int, rows: Sequence[CsvRow]) -> CsvChunk:
    first = rows[0]
    last = rows[-1]
    return CsvChunk(
        schema_version=_CHUNK_SCHEMA,
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
        rows=tuple(rows),
    )


def _validate_normalized(normalized: NormalizedResearchCsv) -> None:
    descriptor = normalized.descriptor
    _descriptor_json_value(descriptor)
    rows = normalized.rows
    if descriptor.data_row_count != len(rows):
        _invalid()
    if descriptor.record_count != descriptor.data_row_count + 1:
        _invalid()
    if descriptor.column_count != len(descriptor.headers):
        _invalid()
    if descriptor.physical_line_count < descriptor.header_row_end:
        _invalid()
    if rows:
        if rows[0].physical_row_start != descriptor.header_row_end + 1:
            _invalid()
        if rows[-1].physical_row_end != descriptor.physical_line_count:
            _invalid()
    elif descriptor.physical_line_count != descriptor.header_row_end:
        _invalid()

    for index, row in enumerate(rows, start=1):
        _validate_row(row)
        if row.logical_row_number != index:
            _invalid()
        if len(row.values) != descriptor.column_count:
            _invalid()
        if index > 1 and row.physical_row_start != rows[index - 2].physical_row_end + 1:
            _invalid()

    expected_missing = tuple(
        sum(row.values[column] == "" for row in rows)
        for column in range(descriptor.column_count)
    )
    expected_non_empty = sum(bool(value) for value in descriptor.headers) + sum(
        bool(value) for row in rows for value in row.values
    )
    expected_formula = sum(
        _is_formula_like(value) for value in descriptor.headers
    ) + sum(_is_formula_like(value) for row in rows for value in row.values)
    if (
        descriptor.missing_value_counts != expected_missing
        or descriptor.non_empty_cell_count != expected_non_empty
        or descriptor.formula_like_cell_count != expected_formula
    ):
        _invalid()
    if descriptor.non_empty_cell_count > MAX_RESEARCH_CSV_NON_EMPTY_CELLS:
        _invalid()

    expected_chunks = _build_chunks(rows)
    if normalized.chunks != expected_chunks:
        _invalid()


def _validate_canonical_artifact_sizes(
    normalized: NormalizedResearchCsv,
    *,
    error_code: str,
) -> None:
    descriptor_bytes = normalized.descriptor.to_canonical_json_bytes()
    chunk_bytes = tuple(
        chunk.to_canonical_json_bytes() for chunk in normalized.chunks
    )
    if (
        len(descriptor_bytes) > MAX_RESEARCH_CSV_DESCRIPTOR_BYTES
        or any(len(content) > MAX_RESEARCH_CSV_CHUNK_BYTES for content in chunk_bytes)
        or len(descriptor_bytes) + sum(map(len, chunk_bytes))
        > MAX_RESEARCH_CSV_CANONICAL_BYTES
    ):
        raise ResearchCsvContractError(error_code)


def _descriptor_json_value(descriptor: CsvDescriptor) -> dict[str, Any]:
    if (
        descriptor.schema_version != _DESCRIPTOR_SCHEMA
        or descriptor.sheet_name != "CSV"
        or not isinstance(descriptor.headers, tuple)
        or not descriptor.headers
        or any(
            not _is_nfc_string(value) or not value or value.strip() != value
            for value in descriptor.headers
        )
        or len(set(descriptor.headers)) != len(descriptor.headers)
        or not _positive_int(descriptor.header_row_start)
        or not _positive_int(descriptor.header_row_end)
        or descriptor.header_row_end < descriptor.header_row_start
        or not _positive_int(descriptor.physical_line_count)
        or descriptor.physical_line_count > MAX_RESEARCH_CSV_PHYSICAL_LINES
        or not _positive_int(descriptor.record_count)
        or descriptor.record_count > MAX_RESEARCH_CSV_RECORDS
        or not _non_negative_int(descriptor.data_row_count)
        or descriptor.record_count != descriptor.data_row_count + 1
        or not _positive_int(descriptor.column_count)
        or descriptor.column_count > MAX_RESEARCH_CSV_COLUMNS
        or not _non_negative_int(descriptor.non_empty_cell_count)
        or not _non_negative_int(descriptor.formula_like_cell_count)
        or descriptor.formula_like_cell_count > descriptor.non_empty_cell_count
        or descriptor.non_empty_cell_count > MAX_RESEARCH_CSV_NON_EMPTY_CELLS
        or not isinstance(descriptor.missing_value_counts, tuple)
        or len(descriptor.missing_value_counts) != descriptor.column_count
        or any(not _non_negative_int(value) for value in descriptor.missing_value_counts)
    ):
        _invalid()
    return {
        "schema_version": descriptor.schema_version,
        "sheet_name": descriptor.sheet_name,
        "headers": list(descriptor.headers),
        "header_row_start": descriptor.header_row_start,
        "header_row_end": descriptor.header_row_end,
        "physical_line_count": descriptor.physical_line_count,
        "record_count": descriptor.record_count,
        "data_row_count": descriptor.data_row_count,
        "column_count": descriptor.column_count,
        "non_empty_cell_count": descriptor.non_empty_cell_count,
        "formula_like_cell_count": descriptor.formula_like_cell_count,
        "missing_value_counts": list(descriptor.missing_value_counts),
    }


def _chunk_json_value(chunk: CsvChunk) -> dict[str, Any]:
    if (
        chunk.schema_version != _CHUNK_SCHEMA
        or not _positive_int(chunk.ordinal)
        or not _positive_int(chunk.logical_row_start)
        or not _positive_int(chunk.logical_row_end)
        or chunk.logical_row_end < chunk.logical_row_start
        or not _positive_int(chunk.physical_row_start)
        or not _positive_int(chunk.physical_row_end)
        or chunk.physical_row_end < chunk.physical_row_start
        or not _positive_int(chunk.row_count)
        or chunk.row_count > MAX_RESEARCH_CSV_CHUNK_RECORDS
        or not _non_negative_int(chunk.non_empty_cell_count)
        or not _non_negative_int(chunk.formula_like_cell_count)
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
            len(row.values) > MAX_RESEARCH_CSV_COLUMNS
            or len(row.values) != len(chunk.rows[0].values)
            for row in chunk.rows
        )
    ):
        _invalid()
    return {
        "schema_version": chunk.schema_version,
        "ordinal": chunk.ordinal,
        "logical_row_start": chunk.logical_row_start,
        "logical_row_end": chunk.logical_row_end,
        "physical_row_start": chunk.physical_row_start,
        "physical_row_end": chunk.physical_row_end,
        "row_count": chunk.row_count,
        "non_empty_cell_count": chunk.non_empty_cell_count,
        "formula_like_cell_count": chunk.formula_like_cell_count,
        "rows": rows,
    }


def _validate_row(row: CsvRow) -> None:
    if (
        not _positive_int(row.logical_row_number)
        or not _positive_int(row.physical_row_start)
        or not _positive_int(row.physical_row_end)
        or row.physical_row_end < row.physical_row_start
        or not isinstance(row.values, tuple)
        or any(not _is_nfc_string(value) or "\x00" in value for value in row.values)
    ):
        _invalid()


def _descriptor_from_json_value(value: Any) -> CsvDescriptor:
    _require_exact_object(value, _DESCRIPTOR_KEYS)
    descriptor = CsvDescriptor(
        schema_version=value["schema_version"],
        sheet_name=value["sheet_name"],
        headers=_string_tuple(value["headers"]),
        header_row_start=value["header_row_start"],
        header_row_end=value["header_row_end"],
        physical_line_count=value["physical_line_count"],
        record_count=value["record_count"],
        data_row_count=value["data_row_count"],
        column_count=value["column_count"],
        non_empty_cell_count=value["non_empty_cell_count"],
        formula_like_cell_count=value["formula_like_cell_count"],
        missing_value_counts=_int_tuple(value["missing_value_counts"]),
    )
    _descriptor_json_value(descriptor)
    return descriptor


def _chunk_from_json_value(value: Any) -> CsvChunk:
    _require_exact_object(value, _CHUNK_KEYS)
    raw_rows = value["rows"]
    if not isinstance(raw_rows, list):
        _invalid()
    rows = tuple(_row_from_json_value(row) for row in raw_rows)
    chunk = CsvChunk(
        schema_version=value["schema_version"],
        ordinal=value["ordinal"],
        logical_row_start=value["logical_row_start"],
        logical_row_end=value["logical_row_end"],
        physical_row_start=value["physical_row_start"],
        physical_row_end=value["physical_row_end"],
        row_count=value["row_count"],
        non_empty_cell_count=value["non_empty_cell_count"],
        formula_like_cell_count=value["formula_like_cell_count"],
        rows=rows,
    )
    _chunk_json_value(chunk)
    return chunk


def _row_from_json_value(value: Any) -> CsvRow:
    _require_exact_object(value, _ROW_KEYS)
    row = CsvRow(
        logical_row_number=value["logical_row_number"],
        physical_row_start=value["physical_row_start"],
        physical_row_end=value["physical_row_end"],
        values=_string_tuple(value["values"]),
    )
    _validate_row(row)
    return row


def _load_canonical_json(content: bytes, expected_sha256: str | None) -> Any:
    if not isinstance(content, bytes) or not content:
        _invalid()
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or expected_sha256.lower() != expected_sha256
        or any(character not in "0123456789abcdef" for character in expected_sha256)
        or actual_sha256 != expected_sha256
    ):
        _invalid()
    try:
        decoded = content.decode("utf-8", "strict")
        value = json.loads(decoded, object_pairs_hook=_object_without_duplicates)
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
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _invalid()
    return tuple(value)


def _int_tuple(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list) or any(type(item) is not int for item in value):
        _invalid()
    return tuple(value)


def _validate_rfc4180_syntax(text: str) -> None:
    in_quotes = False
    at_field_start = True
    just_closed_quote = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_quotes:
            if character == '"':
                if index + 1 < len(text) and text[index + 1] == '"':
                    index += 2
                    continue
                in_quotes = False
                just_closed_quote = True
            index += 1
            continue
        if just_closed_quote:
            if character == ",":
                at_field_start = True
                just_closed_quote = False
            elif character in "\r\n":
                at_field_start = True
                just_closed_quote = False
                if character == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
                    index += 1
            else:
                raise ResearchCsvContractError("RESEARCH_CSV_INVALID")
        elif character == '"':
            if not at_field_start:
                raise ResearchCsvContractError("RESEARCH_CSV_INVALID")
            in_quotes = True
            at_field_start = False
        elif character == ",":
            at_field_start = True
        elif character in "\r\n":
            at_field_start = True
            if character == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
                index += 1
        else:
            at_field_start = False
        index += 1
    if in_quotes:
        raise ResearchCsvContractError("RESEARCH_CSV_INVALID")


def _physical_line_count(text: str) -> int:
    if not text:
        return 0
    line_breaks = 0
    index = 0
    while index < len(text):
        if text[index] == "\r":
            line_breaks += 1
            if index + 1 < len(text) and text[index + 1] == "\n":
                index += 1
        elif text[index] == "\n":
            line_breaks += 1
        index += 1
    return line_breaks if text.endswith(("\r", "\n")) else line_breaks + 1


def _is_formula_like(value: str) -> bool:
    stripped = value.lstrip()
    return bool(stripped and stripped[0] in _FORMULA_PREFIXES)


def _normalize_cell(value: str) -> str:
    return unicodedata.normalize(
        "NFC",
        value.replace("\r\n", "\n").replace("\r", "\n"),
    )


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
    raise ResearchCsvContractError("RESEARCH_CSV_INVALID")


__all__ = [
    "MAX_RESEARCH_CSV_BYTES",
    "MAX_RESEARCH_CSV_CHUNK_RECORDS",
    "MAX_RESEARCH_CSV_COLUMNS",
    "MAX_RESEARCH_CSV_NON_EMPTY_CELLS",
    "MAX_RESEARCH_CSV_PHYSICAL_LINES",
    "MAX_RESEARCH_CSV_RECORDS",
    "RESEARCH_CSV_ERROR_CODES",
    "TARGET_RESEARCH_CSV_CHUNK_BYTES",
    "CsvChunk",
    "CsvDescriptor",
    "CsvRow",
    "NormalizedResearchCsv",
    "ResearchCsvContractError",
    "parse_research_csv_bytes",
    "rebuild_research_csv_from_canonical_bytes",
    "validate_canonical_research_csv_chunk_bytes",
    "validate_canonical_research_csv_descriptor_bytes",
]
