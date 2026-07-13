import hashlib
import json
import unicodedata
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator


MAX_RESEARCH_DATASET_ROWS = 50_000
MAX_RESEARCH_DATASET_COLUMNS = 100
MAX_RESEARCH_DATASET_SHEETS = 10
MAX_RESEARCH_DATASET_NON_EMPTY_CELLS = 2_000_000
MAX_RESEARCH_DATASET_CHUNK_ROWS = 500
MAX_RESEARCH_DATASET_CELL_CODEPOINTS = 32_767

DatasetFileType = Literal["csv", "xlsx"]
DatasetSheetVisibility = Literal["visible", "hidden", "veryHidden"]
XlsxDateSystem = Literal["1900", "1904"]

_DATASET_ID_NAMESPACE = uuid.UUID("75b061cd-f909-5404-b318-19cb9c9129bb")
_SHEET_ID_NAMESPACE = uuid.UUID("ef084d12-e706-558c-9206-505153c3fa2a")
_ROW_CHUNK_ID_NAMESPACE = uuid.UUID("934f93eb-2e3b-51c3-9908-bb9c9a0b2ca2")


def _sha256_json(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_formula_like(value: str) -> bool:
    return value.lstrip().startswith(("=", "+", "-", "@"))


def _row_payload(row: "ExtractedCsvRow") -> dict[str, object]:
    return {
        "logical_row_number": row.logical_row_number,
        "physical_row_start": row.physical_row_start,
        "physical_row_end": row.physical_row_end,
        "values": list(row.values),
    }


def _xlsx_row_payload(row: "ExtractedXlsxRow") -> dict[str, object]:
    return {
        "logical_row_number": row.logical_row_number,
        "physical_row_start": row.physical_row_start,
        "physical_row_end": row.physical_row_end,
        "values": list(row.values),
        "formula_cell_indexes": list(row.formula_cell_indexes),
    }


def build_research_csv_chunk_payload_sha256(
    *,
    ordinal: int,
    logical_row_start: int,
    logical_row_end: int,
    physical_row_start: int,
    physical_row_end: int,
    row_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    rows: tuple["ExtractedCsvRow", ...],
) -> str:
    return _sha256_json(
        {
            "schema_version": "research_csv_chunk_v1",
            "ordinal": ordinal,
            "logical_row_start": logical_row_start,
            "logical_row_end": logical_row_end,
            "physical_row_start": physical_row_start,
            "physical_row_end": physical_row_end,
            "row_count": row_count,
            "non_empty_cell_count": non_empty_cell_count,
            "formula_like_cell_count": formula_like_cell_count,
            "rows": [_row_payload(row) for row in rows],
        }
    )


def build_research_csv_descriptor_sha256(
    *,
    sheet_name: str,
    headers: tuple[str, ...],
    header_row_start: int,
    header_row_end: int,
    physical_line_count: int,
    record_count: int,
    data_row_count: int,
    column_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    missing_value_counts: tuple[int, ...],
) -> str:
    return _sha256_json(
        {
            "schema_version": "research_csv_v1",
            "sheet_name": sheet_name,
            "headers": list(headers),
            "header_row_start": header_row_start,
            "header_row_end": header_row_end,
            "physical_line_count": physical_line_count,
            "record_count": record_count,
            "data_row_count": data_row_count,
            "column_count": column_count,
            "non_empty_cell_count": non_empty_cell_count,
            "formula_like_cell_count": formula_like_cell_count,
            "missing_value_counts": list(missing_value_counts),
        }
    )


def build_research_xlsx_chunk_payload_sha256(
    *,
    sheet_ordinal: int,
    ordinal: int,
    logical_row_start: int,
    logical_row_end: int,
    physical_row_start: int,
    physical_row_end: int,
    row_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    formula_cell_count: int,
    rows: tuple["ExtractedXlsxRow", ...],
) -> str:
    return _sha256_json(
        {
            "schema_version": "research_xlsx_chunk_v1",
            "sheet_ordinal": sheet_ordinal,
            "ordinal": ordinal,
            "logical_row_start": logical_row_start,
            "logical_row_end": logical_row_end,
            "physical_row_start": physical_row_start,
            "physical_row_end": physical_row_end,
            "row_count": row_count,
            "non_empty_cell_count": non_empty_cell_count,
            "formula_like_cell_count": formula_like_cell_count,
            "formula_cell_count": formula_cell_count,
            "rows": [_xlsx_row_payload(row) for row in rows],
        }
    )


def _research_xlsx_sheet_descriptor_payload(
    *,
    ordinal: int,
    name: str,
    visibility: DatasetSheetVisibility,
    headers: tuple[str, ...],
    header_row_start: int,
    header_row_end: int,
    physical_line_count: int,
    record_count: int,
    data_row_count: int,
    column_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    formula_cell_count: int,
    merged_range_count: int,
    missing_value_counts: tuple[int, ...],
) -> dict[str, object]:
    return {
        "ordinal": ordinal,
        "name": name,
        "visibility": visibility,
        "headers": list(headers),
        "header_row_start": header_row_start,
        "header_row_end": header_row_end,
        "physical_line_count": physical_line_count,
        "record_count": record_count,
        "data_row_count": data_row_count,
        "column_count": column_count,
        "non_empty_cell_count": non_empty_cell_count,
        "formula_like_cell_count": formula_like_cell_count,
        "formula_cell_count": formula_cell_count,
        "merged_range_count": merged_range_count,
        "missing_value_counts": list(missing_value_counts),
    }


def build_research_xlsx_sheet_descriptor_sha256(
    *,
    ordinal: int,
    name: str,
    visibility: DatasetSheetVisibility,
    headers: tuple[str, ...],
    header_row_start: int,
    header_row_end: int,
    physical_line_count: int,
    record_count: int,
    data_row_count: int,
    column_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    formula_cell_count: int,
    merged_range_count: int,
    missing_value_counts: tuple[int, ...],
) -> str:
    return _sha256_json(
        _research_xlsx_sheet_descriptor_payload(
            ordinal=ordinal,
            name=name,
            visibility=visibility,
            headers=headers,
            header_row_start=header_row_start,
            header_row_end=header_row_end,
            physical_line_count=physical_line_count,
            record_count=record_count,
            data_row_count=data_row_count,
            column_count=column_count,
            non_empty_cell_count=non_empty_cell_count,
            formula_like_cell_count=formula_like_cell_count,
            formula_cell_count=formula_cell_count,
            merged_range_count=merged_range_count,
            missing_value_counts=missing_value_counts,
        )
    )


def build_research_xlsx_descriptor_sha256(
    *,
    date_system: XlsxDateSystem,
    workbook_sheet_count: int,
    empty_sheet_count: int,
    sheets: tuple["ExtractedXlsxSheet", ...]
    | tuple["ResearchDatasetSheetEntity", ...],
    total_record_count: int,
    total_data_row_count: int,
    total_non_empty_cell_count: int,
    total_formula_like_cell_count: int,
    total_formula_cell_count: int,
    total_merged_range_count: int,
) -> str:
    return _sha256_json(
        {
            "schema_version": "research_xlsx_v1",
            "date_system": date_system,
            "workbook_sheet_count": workbook_sheet_count,
            "empty_sheet_count": empty_sheet_count,
            "sheets": [
                _research_xlsx_sheet_descriptor_payload(
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
                for sheet in sheets
            ],
            "total_record_count": total_record_count,
            "total_data_row_count": total_data_row_count,
            "total_non_empty_cell_count": total_non_empty_cell_count,
            "total_formula_like_cell_count": total_formula_like_cell_count,
            "total_formula_cell_count": total_formula_cell_count,
            "total_merged_range_count": total_merged_range_count,
        }
    )


def build_research_dataset_id(ingestion_id: str) -> str:
    return str(uuid.uuid5(_DATASET_ID_NAMESPACE, ingestion_id))


def build_research_dataset_sheet_id(
    dataset_id: str,
    ordinal: int,
    name: str,
) -> str:
    canonical = json.dumps(
        [dataset_id, ordinal, name],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(_SHEET_ID_NAMESPACE, canonical))


def build_research_dataset_row_chunk_id(
    sheet_id: str,
    ordinal: int,
    payload_sha256: str,
) -> str:
    canonical = json.dumps(
        [sheet_id, ordinal, payload_sha256],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(_ROW_CHUNK_ID_NAMESPACE, canonical))


class ExtractedCsvRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_row_number: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    values: tuple[StrictStr, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )

    @model_validator(mode="after")
    def validate_physical_range(self):
        if self.physical_row_end < self.physical_row_start:
            raise ValueError("physical_row_end 不能小于 physical_row_start")
        if any(
            unicodedata.is_normalized("NFC", value) is False or "\x00" in value
            for value in self.values
        ):
            raise ValueError("row values 必须为 NFC 且不得包含 NUL")
        return self


class ExtractedXlsxRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_row_number: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    values: tuple[StrictStr, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )
    formula_cell_indexes: tuple[StrictInt, ...] = Field(
        default=(),
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )

    @model_validator(mode="after")
    def validate_xlsx_row(self):
        if self.physical_row_start != self.physical_row_end:
            raise ValueError("XLSX row 必须对应单一 physical row")
        if any(
            not unicodedata.is_normalized("NFC", value)
            or "\x00" in value
            or len(value) > MAX_RESEARCH_DATASET_CELL_CODEPOINTS
            or any(0xD800 <= ord(character) <= 0xDFFF for character in value)
            for value in self.values
        ):
            raise ValueError("row values 必须为 NFC 且不得包含 NUL/surrogate")
        if list(self.formula_cell_indexes) != sorted(
            set(self.formula_cell_indexes)
        ):
            raise ValueError("formula_cell_indexes 必须唯一且递增")
        if any(
            index < 0 or index >= len(self.values)
            for index in self.formula_cell_indexes
        ):
            raise ValueError("formula_cell_indexes 超出 row 列范围")
        if any(
            not self.values[index].startswith("=")
            for index in self.formula_cell_indexes
        ):
            raise ValueError("formula cell 必须保存为 = 开头的字面字符串")
        return self


def _validate_chunk_fields(
    *,
    ordinal: int,
    logical_row_start: int,
    logical_row_end: int,
    physical_row_start: int,
    physical_row_end: int,
    row_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    rows: tuple[ExtractedCsvRow, ...],
    payload_sha256: str,
) -> None:
    if row_count != len(rows):
        raise ValueError("row_count 与 rows 数量不一致")
    if logical_row_end - logical_row_start + 1 != row_count:
        raise ValueError("logical row 范围必须与 row_count 一致")
    logical_numbers = [row.logical_row_number for row in rows]
    if logical_numbers != list(range(logical_row_start, logical_row_end + 1)):
        raise ValueError("logical row 必须有序且连续")
    if rows[0].physical_row_start != physical_row_start:
        raise ValueError("physical_row_start 与首行不一致")
    if rows[-1].physical_row_end != physical_row_end:
        raise ValueError("physical_row_end 与末行不一致")
    for previous, current in zip(rows, rows[1:]):
        if current.physical_row_start != previous.physical_row_end + 1:
            raise ValueError("chunk 内 physical row 必须有序且连续")
    column_count = len(rows[0].values)
    if any(len(row.values) != column_count for row in rows):
        raise ValueError("rows 必须为矩形")
    expected_non_empty = sum(
        value != "" for row in rows for value in row.values
    )
    expected_formula_like = sum(
        _is_formula_like(value) for row in rows for value in row.values
    )
    if non_empty_cell_count != expected_non_empty:
        raise ValueError("non_empty_cell_count 与 rows 不一致")
    if formula_like_cell_count != expected_formula_like:
        raise ValueError("formula_like_cell_count 与 rows 不一致")
    expected_sha256 = build_research_csv_chunk_payload_sha256(
        ordinal=ordinal,
        logical_row_start=logical_row_start,
        logical_row_end=logical_row_end,
        physical_row_start=physical_row_start,
        physical_row_end=physical_row_end,
        row_count=row_count,
        non_empty_cell_count=non_empty_cell_count,
        formula_like_cell_count=formula_like_cell_count,
        rows=rows,
    )
    if payload_sha256 != expected_sha256:
        raise ValueError("payload_sha256 与 chunk payload 不一致")


class ExtractedCsvChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research_csv_chunk_v1"] = "research_csv_chunk_v1"
    ordinal: StrictInt = Field(ge=1)
    logical_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    logical_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    row_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_CHUNK_ROWS)
    non_empty_cell_count: StrictInt = Field(
        ge=0,
        le=MAX_RESEARCH_DATASET_NON_EMPTY_CELLS,
    )
    formula_like_cell_count: StrictInt = Field(ge=0)
    rows: tuple[ExtractedCsvRow, ...] = Field(min_length=1)
    payload_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_chunk(self):
        _validate_chunk_fields(
            ordinal=self.ordinal,
            logical_row_start=self.logical_row_start,
            logical_row_end=self.logical_row_end,
            physical_row_start=self.physical_row_start,
            physical_row_end=self.physical_row_end,
            row_count=self.row_count,
            non_empty_cell_count=self.non_empty_cell_count,
            formula_like_cell_count=self.formula_like_cell_count,
            rows=self.rows,
            payload_sha256=self.payload_sha256,
        )
        return self


def _validate_xlsx_chunk_fields(
    *,
    sheet_ordinal: int,
    ordinal: int,
    logical_row_start: int,
    logical_row_end: int,
    physical_row_start: int,
    physical_row_end: int,
    row_count: int,
    non_empty_cell_count: int,
    formula_like_cell_count: int,
    formula_cell_count: int,
    rows: tuple[ExtractedXlsxRow, ...],
    payload_sha256: str,
) -> None:
    if row_count != len(rows):
        raise ValueError("row_count 与 rows 数量不一致")
    if logical_row_end - logical_row_start + 1 != row_count:
        raise ValueError("logical row 范围必须与 row_count 一致")
    if [row.logical_row_number for row in rows] != list(
        range(logical_row_start, logical_row_end + 1)
    ):
        raise ValueError("logical row 必须有序且连续")
    if rows[0].physical_row_start != physical_row_start:
        raise ValueError("physical_row_start 与首行不一致")
    if rows[-1].physical_row_end != physical_row_end:
        raise ValueError("physical_row_end 与末行不一致")
    for previous, current in zip(rows, rows[1:]):
        if current.physical_row_start != previous.physical_row_end + 1:
            raise ValueError("chunk 内 physical row 必须有序且连续")
    column_count = len(rows[0].values)
    if any(len(row.values) != column_count for row in rows):
        raise ValueError("rows 必须为矩形")
    expected_non_empty = sum(
        value != "" for row in rows for value in row.values
    )
    expected_formula_like = sum(
        _is_formula_like(value) for row in rows for value in row.values
    )
    expected_formula = sum(len(row.formula_cell_indexes) for row in rows)
    if non_empty_cell_count != expected_non_empty:
        raise ValueError("non_empty_cell_count 与 rows 不一致")
    if formula_like_cell_count != expected_formula_like:
        raise ValueError("formula_like_cell_count 与 rows 不一致")
    if formula_cell_count != expected_formula:
        raise ValueError("formula_cell_count 与 rows 不一致")
    expected_sha256 = build_research_xlsx_chunk_payload_sha256(
        sheet_ordinal=sheet_ordinal,
        ordinal=ordinal,
        logical_row_start=logical_row_start,
        logical_row_end=logical_row_end,
        physical_row_start=physical_row_start,
        physical_row_end=physical_row_end,
        row_count=row_count,
        non_empty_cell_count=non_empty_cell_count,
        formula_like_cell_count=formula_like_cell_count,
        formula_cell_count=formula_cell_count,
        rows=rows,
    )
    if payload_sha256 != expected_sha256:
        raise ValueError("payload_sha256 与 XLSX chunk payload 不一致")


class ExtractedXlsxChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research_xlsx_chunk_v1"] = "research_xlsx_chunk_v1"
    sheet_ordinal: StrictInt = Field(ge=0, lt=MAX_RESEARCH_DATASET_SHEETS)
    ordinal: StrictInt = Field(ge=1)
    logical_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    logical_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    row_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_CHUNK_ROWS)
    non_empty_cell_count: StrictInt = Field(
        ge=0,
        le=MAX_RESEARCH_DATASET_NON_EMPTY_CELLS,
    )
    formula_like_cell_count: StrictInt = Field(ge=0)
    formula_cell_count: StrictInt = Field(ge=0)
    rows: tuple[ExtractedXlsxRow, ...] = Field(min_length=1)
    payload_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_chunk(self):
        _validate_xlsx_chunk_fields(
            sheet_ordinal=self.sheet_ordinal,
            ordinal=self.ordinal,
            logical_row_start=self.logical_row_start,
            logical_row_end=self.logical_row_end,
            physical_row_start=self.physical_row_start,
            physical_row_end=self.physical_row_end,
            row_count=self.row_count,
            non_empty_cell_count=self.non_empty_cell_count,
            formula_like_cell_count=self.formula_like_cell_count,
            formula_cell_count=self.formula_cell_count,
            rows=self.rows,
            payload_sha256=self.payload_sha256,
        )
        return self


def _validate_headers(headers: tuple[str, ...]) -> None:
    if any(
        not header
        or header.strip() != header
        or not unicodedata.is_normalized("NFC", header)
        or "\x00" in header
        or any(0xD800 <= ord(character) <= 0xDFFF for character in header)
        for header in headers
    ):
        raise ValueError("headers 必须非空、去除边缘空白且为 NFC")
    if len(set(headers)) != len(headers):
        raise ValueError("headers 必须唯一")


def _validate_continuous_chunks(chunks: tuple[object, ...]) -> None:
    for previous, current in zip(chunks, chunks[1:]):
        if current.logical_row_start != previous.logical_row_end + 1:
            raise ValueError("chunk logical row 范围必须连续")
        if current.physical_row_start != previous.physical_row_end + 1:
            raise ValueError("chunk physical row 范围必须连续")


class ExtractedResearchCsv(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research_csv_v1"] = "research_csv_v1"
    sheet_name: Literal["CSV"] = "CSV"
    headers: tuple[StrictStr, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )
    header_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    header_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_line_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    record_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    data_row_count: StrictInt = Field(ge=0, le=MAX_RESEARCH_DATASET_ROWS)
    column_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_COLUMNS)
    non_empty_cell_count: StrictInt = Field(
        ge=1,
        le=MAX_RESEARCH_DATASET_NON_EMPTY_CELLS,
    )
    formula_like_cell_count: StrictInt = Field(ge=0)
    missing_value_counts: tuple[StrictInt, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )
    chunks: tuple[ExtractedCsvChunk, ...]
    descriptor_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_csv(self):
        _validate_headers(self.headers)
        if self.header_row_end < self.header_row_start:
            raise ValueError("header_row_end 不能小于 header_row_start")
        if self.physical_line_count < self.header_row_end:
            raise ValueError("physical_line_count 不能小于 header 范围")
        if self.record_count != self.data_row_count + 1:
            raise ValueError("record_count 必须等于 data_row_count + 1")
        if self.column_count != len(self.headers):
            raise ValueError("column_count 必须等于 headers 数量")
        if len(self.missing_value_counts) != self.column_count:
            raise ValueError("missing_value_counts 数量必须等于 column_count")
        if any(count > self.data_row_count for count in self.missing_value_counts):
            raise ValueError("missing value count 不能超过 data_row_count")
        if [chunk.ordinal for chunk in self.chunks] != list(
            range(1, len(self.chunks) + 1)
        ):
            raise ValueError("chunk ordinal 必须从 1 连续递增")
        _validate_continuous_chunks(self.chunks)
        if self.data_row_count != sum(chunk.row_count for chunk in self.chunks):
            raise ValueError("data_row_count 与 chunks 不一致")

        if self.chunks:
            if self.chunks[0].physical_row_start != self.header_row_end + 1:
                raise ValueError("首个 data record 必须紧接 header physical range")
            if self.chunks[-1].physical_row_end != self.physical_line_count:
                raise ValueError("末个 data record 必须结束于 physical_line_count")
            if self.chunks[0].logical_row_start != 1:
                raise ValueError("首个 data logical row 必须从 1 开始")
            if self.chunks[-1].logical_row_end != self.data_row_count:
                raise ValueError("末个 data logical row 必须等于 data_row_count")
        elif self.physical_line_count != self.header_row_end:
            raise ValueError("无 data record 时 header 必须结束于文件末行")

        if any(
            len(row.values) != self.column_count
            for chunk in self.chunks
            for row in chunk.rows
        ):
            raise ValueError("rows 必须与 headers 构成矩形")
        expected_missing_counts = tuple(
            sum(
                row.values[column] == ""
                for chunk in self.chunks
                for row in chunk.rows
            )
            for column in range(self.column_count)
        )
        if self.missing_value_counts != expected_missing_counts:
            raise ValueError("missing_value_counts 与 data rows 不一致")

        header_non_empty = self.column_count
        header_formula_like = sum(_is_formula_like(header) for header in self.headers)
        expected_non_empty = header_non_empty + sum(
            chunk.non_empty_cell_count for chunk in self.chunks
        )
        expected_formula_like = header_formula_like + sum(
            chunk.formula_like_cell_count for chunk in self.chunks
        )
        if self.non_empty_cell_count != expected_non_empty:
            raise ValueError("non_empty_cell_count 必须包含 header 与 data rows")
        if self.formula_like_cell_count != expected_formula_like:
            raise ValueError("formula_like_cell_count 必须包含 header 与 data rows")

        expected_descriptor = build_research_csv_descriptor_sha256(
            sheet_name=self.sheet_name,
            headers=self.headers,
            header_row_start=self.header_row_start,
            header_row_end=self.header_row_end,
            physical_line_count=self.physical_line_count,
            record_count=self.record_count,
            data_row_count=self.data_row_count,
            column_count=self.column_count,
            non_empty_cell_count=self.non_empty_cell_count,
            formula_like_cell_count=self.formula_like_cell_count,
            missing_value_counts=self.missing_value_counts,
        )
        if self.descriptor_sha256 != expected_descriptor:
            raise ValueError("descriptor_sha256 与 CSV descriptor 不一致")
        return self


def _validate_xlsx_sheet_name(name: str) -> None:
    if (
        not unicodedata.is_normalized("NFC", name)
        or any(unicodedata.category(character).startswith("C") for character in name)
    ):
        raise ValueError("XLSX sheet name 必须为 NFC 且无控制字符")


class ExtractedXlsxSheet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: StrictInt = Field(ge=0, lt=MAX_RESEARCH_DATASET_SHEETS)
    name: StrictStr = Field(min_length=1, max_length=31)
    visibility: DatasetSheetVisibility
    headers: tuple[StrictStr, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )
    header_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    header_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_line_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    record_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    data_row_count: StrictInt = Field(ge=0, le=MAX_RESEARCH_DATASET_ROWS)
    column_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_COLUMNS)
    non_empty_cell_count: StrictInt = Field(
        ge=1,
        le=MAX_RESEARCH_DATASET_NON_EMPTY_CELLS,
    )
    formula_like_cell_count: StrictInt = Field(ge=0)
    formula_cell_count: StrictInt = Field(ge=0)
    merged_range_count: StrictInt = Field(ge=0)
    missing_value_counts: tuple[StrictInt, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )
    chunks: tuple[ExtractedXlsxChunk, ...]
    descriptor_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_xlsx_sheet(self):
        _validate_xlsx_sheet_name(self.name)
        _validate_headers(self.headers)
        if any(
            len(header) > MAX_RESEARCH_DATASET_CELL_CODEPOINTS
            or any(0xD800 <= ord(character) <= 0xDFFF for character in header)
            for header in self.headers
        ):
            raise ValueError("XLSX headers 超出长度限制或包含 surrogate")
        if self.header_row_start != self.header_row_end:
            raise ValueError("XLSX header 必须位于单一 physical row")
        if self.record_count != self.data_row_count + 1:
            raise ValueError("record_count 必须等于 data_row_count + 1")
        if self.column_count != len(self.headers):
            raise ValueError("column_count 必须等于 headers 数量")
        if len(self.missing_value_counts) != self.column_count:
            raise ValueError("missing_value_counts 数量必须等于 column_count")
        if any(count > self.data_row_count for count in self.missing_value_counts):
            raise ValueError("missing value count 不能超过 data_row_count")
        if self.physical_line_count != self.header_row_end + self.data_row_count:
            raise ValueError("XLSX physical rows 必须从 header 到末行连续")
        if [chunk.ordinal for chunk in self.chunks] != list(
            range(1, len(self.chunks) + 1)
        ):
            raise ValueError("chunk ordinal 必须从 1 连续递增")
        if any(chunk.sheet_ordinal != self.ordinal for chunk in self.chunks):
            raise ValueError("chunk sheet_ordinal 必须等于所属 sheet ordinal")
        _validate_continuous_chunks(self.chunks)
        if self.data_row_count != sum(chunk.row_count for chunk in self.chunks):
            raise ValueError("data_row_count 与 chunks 不一致")
        if self.chunks:
            if self.chunks[0].physical_row_start != self.header_row_end + 1:
                raise ValueError("首个 data row 必须紧接 header")
            if self.chunks[-1].physical_row_end != self.physical_line_count:
                raise ValueError("末个 data row 必须结束于 physical_line_count")
            if self.chunks[0].logical_row_start != 1:
                raise ValueError("首个 data logical row 必须从 1 开始")
            if self.chunks[-1].logical_row_end != self.data_row_count:
                raise ValueError("末个 data logical row 必须等于 data_row_count")
        if any(
            len(row.values) != self.column_count
            for chunk in self.chunks
            for row in chunk.rows
        ):
            raise ValueError("rows 必须与 headers 构成矩形")
        expected_missing = tuple(
            sum(
                row.values[column] == ""
                for chunk in self.chunks
                for row in chunk.rows
            )
            for column in range(self.column_count)
        )
        if self.missing_value_counts != expected_missing:
            raise ValueError("missing_value_counts 与 data rows 不一致")
        expected_non_empty = self.column_count + sum(
            chunk.non_empty_cell_count for chunk in self.chunks
        )
        expected_formula_like = sum(
            _is_formula_like(header) for header in self.headers
        ) + sum(chunk.formula_like_cell_count for chunk in self.chunks)
        expected_formula = sum(
            chunk.formula_cell_count for chunk in self.chunks
        )
        if self.non_empty_cell_count != expected_non_empty:
            raise ValueError("non_empty_cell_count 必须包含 header 与 data rows")
        if self.formula_like_cell_count != expected_formula_like:
            raise ValueError("formula_like_cell_count 必须包含 header 与 data rows")
        if self.formula_cell_count != expected_formula:
            raise ValueError("formula_cell_count 与 data rows 不一致")
        expected_descriptor = build_research_xlsx_sheet_descriptor_sha256(
            ordinal=self.ordinal,
            name=self.name,
            visibility=self.visibility,
            headers=self.headers,
            header_row_start=self.header_row_start,
            header_row_end=self.header_row_end,
            physical_line_count=self.physical_line_count,
            record_count=self.record_count,
            data_row_count=self.data_row_count,
            column_count=self.column_count,
            non_empty_cell_count=self.non_empty_cell_count,
            formula_like_cell_count=self.formula_like_cell_count,
            formula_cell_count=self.formula_cell_count,
            merged_range_count=self.merged_range_count,
            missing_value_counts=self.missing_value_counts,
        )
        if self.descriptor_sha256 != expected_descriptor:
            raise ValueError("descriptor_sha256 与 XLSX sheet descriptor 不一致")
        return self


class ExtractedResearchXlsx(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research_xlsx_v1"] = "research_xlsx_v1"
    date_system: XlsxDateSystem
    workbook_sheet_count: StrictInt = Field(
        ge=1,
        le=MAX_RESEARCH_DATASET_SHEETS,
    )
    empty_sheet_count: StrictInt = Field(ge=0, lt=MAX_RESEARCH_DATASET_SHEETS)
    sheets: tuple[ExtractedXlsxSheet, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_SHEETS,
    )
    total_record_count: StrictInt = Field(ge=1)
    total_data_row_count: StrictInt = Field(
        ge=0,
        le=MAX_RESEARCH_DATASET_ROWS,
    )
    total_non_empty_cell_count: StrictInt = Field(
        ge=1,
        le=MAX_RESEARCH_DATASET_NON_EMPTY_CELLS,
    )
    total_formula_like_cell_count: StrictInt = Field(ge=0)
    total_formula_cell_count: StrictInt = Field(ge=0)
    total_merged_range_count: StrictInt = Field(ge=0)
    descriptor_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_xlsx(self):
        if self.workbook_sheet_count != len(self.sheets) + self.empty_sheet_count:
            raise ValueError("workbook sheet count 必须等于非空与空 sheet 数量之和")
        ordinals = [sheet.ordinal for sheet in self.sheets]
        if ordinals != sorted(set(ordinals)):
            raise ValueError("sheets 必须按原始 workbook ordinal 唯一递增")
        if any(ordinal >= self.workbook_sheet_count for ordinal in ordinals):
            raise ValueError("sheet ordinal 超出 workbook sheet 范围")
        folded_names = [sheet.name.casefold() for sheet in self.sheets]
        if len(folded_names) != len(set(folded_names)):
            raise ValueError("XLSX sheet name 必须按 casefold 唯一")
        expected_totals = {
            "total_record_count": sum(sheet.record_count for sheet in self.sheets),
            "total_data_row_count": sum(
                sheet.data_row_count for sheet in self.sheets
            ),
            "total_non_empty_cell_count": sum(
                sheet.non_empty_cell_count for sheet in self.sheets
            ),
            "total_formula_like_cell_count": sum(
                sheet.formula_like_cell_count for sheet in self.sheets
            ),
            "total_formula_cell_count": sum(
                sheet.formula_cell_count for sheet in self.sheets
            ),
            "total_merged_range_count": sum(
                sheet.merged_range_count for sheet in self.sheets
            ),
        }
        for field_name, expected in expected_totals.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name} 与 sheets 不一致")
        expected_descriptor = build_research_xlsx_descriptor_sha256(
            date_system=self.date_system,
            workbook_sheet_count=self.workbook_sheet_count,
            empty_sheet_count=self.empty_sheet_count,
            sheets=self.sheets,
            total_record_count=self.total_record_count,
            total_data_row_count=self.total_data_row_count,
            total_non_empty_cell_count=self.total_non_empty_cell_count,
            total_formula_like_cell_count=self.total_formula_like_cell_count,
            total_formula_cell_count=self.total_formula_cell_count,
            total_merged_range_count=self.total_merged_range_count,
        )
        if self.descriptor_sha256 != expected_descriptor:
            raise ValueError("descriptor_sha256 与 XLSX workbook descriptor 不一致")
        return self


class ResearchDatasetEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr
    ingestion_id: StrictStr = Field(min_length=1, max_length=64)
    file_type: DatasetFileType
    sheet_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_SHEETS)
    total_data_row_count: StrictInt = Field(
        ge=0,
        le=MAX_RESEARCH_DATASET_ROWS,
    )
    total_column_count: StrictInt = Field(
        ge=1,
        le=MAX_RESEARCH_DATASET_COLUMNS * MAX_RESEARCH_DATASET_SHEETS,
    )
    total_non_empty_cell_count: StrictInt = Field(
        ge=1,
        le=MAX_RESEARCH_DATASET_NON_EMPTY_CELLS,
    )
    total_formula_like_cell_count: StrictInt = Field(ge=0)
    total_formula_cell_count: StrictInt = Field(default=0, ge=0)
    total_merged_range_count: StrictInt = Field(default=0, ge=0)
    descriptor_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_identity(self):
        if self.id != build_research_dataset_id(self.ingestion_id):
            raise ValueError("dataset id 必须由 ingestion_id 稳定生成")
        if self.total_formula_like_cell_count > self.total_non_empty_cell_count:
            raise ValueError("formula-like total 不能超过 non-empty total")
        if self.total_formula_cell_count > self.total_non_empty_cell_count:
            raise ValueError("formula total 不能超过 non-empty total")
        return self


class ResearchDatasetSheetEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr
    dataset_id: StrictStr
    ordinal: StrictInt = Field(ge=0)
    name: StrictStr = Field(min_length=1, max_length=128)
    visibility: DatasetSheetVisibility = "visible"
    headers: tuple[StrictStr, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )
    header_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    header_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_line_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    record_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    data_row_count: StrictInt = Field(ge=0, le=MAX_RESEARCH_DATASET_ROWS)
    column_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_COLUMNS)
    non_empty_cell_count: StrictInt = Field(
        ge=1,
        le=MAX_RESEARCH_DATASET_NON_EMPTY_CELLS,
    )
    formula_like_cell_count: StrictInt = Field(ge=0)
    formula_cell_count: StrictInt = Field(default=0, ge=0)
    merged_range_count: StrictInt = Field(default=0, ge=0)
    missing_value_counts: tuple[StrictInt, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_DATASET_COLUMNS,
    )
    descriptor_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_sheet(self):
        _validate_headers(self.headers)
        _validate_xlsx_sheet_name(self.name)
        if self.id != build_research_dataset_sheet_id(
            self.dataset_id,
            self.ordinal,
            self.name,
        ):
            raise ValueError("sheet id 必须由 dataset 关系稳定生成")
        if self.header_row_end < self.header_row_start:
            raise ValueError("header_row_end 不能小于 header_row_start")
        if self.physical_line_count < self.header_row_end:
            raise ValueError("physical_line_count 不能小于 header 范围")
        if self.record_count != self.data_row_count + 1:
            raise ValueError("record_count 必须等于 data_row_count + 1")
        if self.column_count != len(self.headers):
            raise ValueError("column_count 必须等于 headers 数量")
        if len(self.missing_value_counts) != self.column_count:
            raise ValueError("missing_value_counts 数量必须等于 column_count")
        if any(count > self.data_row_count for count in self.missing_value_counts):
            raise ValueError("missing value count 不能超过 data_row_count")
        header_formula_like = sum(_is_formula_like(header) for header in self.headers)
        if self.formula_like_cell_count < header_formula_like:
            raise ValueError("formula_like_cell_count 不得少于 header 贡献")
        if self.non_empty_cell_count < self.column_count:
            raise ValueError("non_empty_cell_count 不得少于 header 贡献")
        if self.formula_cell_count > self.non_empty_cell_count:
            raise ValueError("formula_cell_count 不能超过 non_empty_cell_count")
        return self


class ResearchDatasetRowChunkEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: StrictStr
    sheet_id: StrictStr
    schema_version: Literal[
        "research_csv_chunk_v1",
        "research_xlsx_chunk_v1",
    ] = "research_csv_chunk_v1"
    sheet_ordinal: StrictInt | None = Field(
        default=None,
        ge=0,
        lt=MAX_RESEARCH_DATASET_SHEETS,
    )
    ordinal: StrictInt = Field(ge=1)
    logical_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    logical_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_start: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    physical_row_end: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_ROWS)
    row_count: StrictInt = Field(ge=1, le=MAX_RESEARCH_DATASET_CHUNK_ROWS)
    non_empty_cell_count: StrictInt = Field(
        ge=0,
        le=MAX_RESEARCH_DATASET_NON_EMPTY_CELLS,
    )
    formula_like_cell_count: StrictInt = Field(ge=0)
    formula_cell_count: StrictInt = Field(default=0, ge=0)
    rows: tuple[ExtractedCsvRow | ExtractedXlsxRow, ...] = Field(min_length=1)
    payload_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_chunk(self):
        if self.schema_version == "research_csv_chunk_v1":
            if self.sheet_ordinal is not None or self.formula_cell_count != 0:
                raise ValueError("CSV chunk 不得包含 XLSX 专用字段")
            if any(not isinstance(row, ExtractedCsvRow) for row in self.rows):
                raise ValueError("CSV chunk rows 类型不匹配")
            _validate_chunk_fields(
                ordinal=self.ordinal,
                logical_row_start=self.logical_row_start,
                logical_row_end=self.logical_row_end,
                physical_row_start=self.physical_row_start,
                physical_row_end=self.physical_row_end,
                row_count=self.row_count,
                non_empty_cell_count=self.non_empty_cell_count,
                formula_like_cell_count=self.formula_like_cell_count,
                rows=self.rows,
                payload_sha256=self.payload_sha256,
            )
        else:
            if self.sheet_ordinal is None:
                raise ValueError("XLSX chunk 必须包含 sheet_ordinal")
            if any(not isinstance(row, ExtractedXlsxRow) for row in self.rows):
                raise ValueError("XLSX chunk rows 类型不匹配")
            _validate_xlsx_chunk_fields(
                sheet_ordinal=self.sheet_ordinal,
                ordinal=self.ordinal,
                logical_row_start=self.logical_row_start,
                logical_row_end=self.logical_row_end,
                physical_row_start=self.physical_row_start,
                physical_row_end=self.physical_row_end,
                row_count=self.row_count,
                non_empty_cell_count=self.non_empty_cell_count,
                formula_like_cell_count=self.formula_like_cell_count,
                formula_cell_count=self.formula_cell_count,
                rows=self.rows,
                payload_sha256=self.payload_sha256,
            )
        expected_id = build_research_dataset_row_chunk_id(
            self.sheet_id,
            self.ordinal,
            self.payload_sha256,
        )
        if self.id != expected_id:
            raise ValueError("row chunk id 必须由 sheet 关系与 payload 稳定生成")
        return self


class ResearchXlsxMaterializationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date_system: XlsxDateSystem
    workbook_sheet_count: StrictInt = Field(
        ge=1,
        le=MAX_RESEARCH_DATASET_SHEETS,
    )
    empty_sheet_count: StrictInt = Field(ge=0, lt=MAX_RESEARCH_DATASET_SHEETS)
    total_record_count: StrictInt = Field(ge=1)


class ResearchDatasetMaterialization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: ResearchDatasetEntity
    sheets: tuple[ResearchDatasetSheetEntity, ...] = Field(min_length=1)
    row_chunks: tuple[ResearchDatasetRowChunkEntity, ...]
    xlsx_metadata: ResearchXlsxMaterializationMetadata | None = None

    @model_validator(mode="after")
    def validate_materialization(self):
        if self.dataset.sheet_count != len(self.sheets):
            raise ValueError("dataset sheet_count 与 sheets 不一致")
        sheet_ordinals_in_order = [sheet.ordinal for sheet in self.sheets]
        if sheet_ordinals_in_order != sorted(set(sheet_ordinals_in_order)):
            raise ValueError("sheet ordinal 必须唯一且递增")
        if any(sheet.dataset_id != self.dataset.id for sheet in self.sheets):
            raise ValueError("sheet 必须属于 materialization dataset")
        if self.dataset.file_type == "csv":
            if (
                len(self.sheets) != 1
                or self.sheets[0].ordinal != 0
                or self.sheets[0].name != "CSV"
            ):
                raise ValueError("CSV dataset 必须且只能包含名为 CSV 的 sheet")
            if self.xlsx_metadata is not None:
                raise ValueError("CSV dataset 不得包含 XLSX metadata")
            csv_sheet = self.sheets[0]
            if (
                csv_sheet.visibility != "visible"
                or csv_sheet.formula_cell_count != 0
                or csv_sheet.merged_range_count != 0
            ):
                raise ValueError("CSV sheet 的 XLSX 专用计数必须为默认值")
            expected_descriptor = build_research_csv_descriptor_sha256(
                sheet_name=csv_sheet.name,
                headers=csv_sheet.headers,
                header_row_start=csv_sheet.header_row_start,
                header_row_end=csv_sheet.header_row_end,
                physical_line_count=csv_sheet.physical_line_count,
                record_count=csv_sheet.record_count,
                data_row_count=csv_sheet.data_row_count,
                column_count=csv_sheet.column_count,
                non_empty_cell_count=csv_sheet.non_empty_cell_count,
                formula_like_cell_count=csv_sheet.formula_like_cell_count,
                missing_value_counts=csv_sheet.missing_value_counts,
            )
            if csv_sheet.descriptor_sha256 != expected_descriptor:
                raise ValueError("CSV sheet descriptor 与字段不一致")
        else:
            if self.xlsx_metadata is None:
                raise ValueError("XLSX dataset 必须包含 workbook metadata")
            if (
                self.xlsx_metadata.workbook_sheet_count
                != len(self.sheets) + self.xlsx_metadata.empty_sheet_count
            ):
                raise ValueError("XLSX workbook sheet 数量不一致")
            if any(
                ordinal >= self.xlsx_metadata.workbook_sheet_count
                for ordinal in sheet_ordinals_in_order
            ):
                raise ValueError("XLSX sheet ordinal 超出 workbook 范围")
            folded_names = [sheet.name.casefold() for sheet in self.sheets]
            if len(folded_names) != len(set(folded_names)):
                raise ValueError("XLSX sheet name 必须按 casefold 唯一")
            if any(len(sheet.name) > 31 for sheet in self.sheets):
                raise ValueError("XLSX sheet name 不能超过 31 个字符")

        chunks_by_sheet: dict[str, list[ResearchDatasetRowChunkEntity]] = {
            sheet.id: [] for sheet in self.sheets
        }
        sheet_ordinals = {sheet.id: sheet.ordinal for sheet in self.sheets}
        for chunk in self.row_chunks:
            if chunk.sheet_id not in chunks_by_sheet:
                raise ValueError("row chunk 引用了 materialization 之外的 sheet")
            chunks_by_sheet[chunk.sheet_id].append(chunk)
        if list(self.row_chunks) != sorted(
            self.row_chunks,
            key=lambda chunk: (sheet_ordinals[chunk.sheet_id], chunk.ordinal),
        ):
            raise ValueError("row chunks 必须按 sheet/ordinal 有序")

        for sheet in self.sheets:
            chunks = tuple(chunks_by_sheet[sheet.id])
            expected_schema = (
                "research_csv_chunk_v1"
                if self.dataset.file_type == "csv"
                else "research_xlsx_chunk_v1"
            )
            if any(chunk.schema_version != expected_schema for chunk in chunks):
                raise ValueError("row chunk schema 与 dataset file_type 不一致")
            if self.dataset.file_type == "xlsx" and any(
                chunk.sheet_ordinal != sheet.ordinal for chunk in chunks
            ):
                raise ValueError("XLSX chunk sheet_ordinal 与 sheet 不一致")
            if [chunk.ordinal for chunk in chunks] != list(
                range(1, len(chunks) + 1)
            ):
                raise ValueError("每个 sheet 的 chunk ordinal 必须从 1 连续递增")
            _validate_continuous_chunks(chunks)
            if sheet.data_row_count != sum(chunk.row_count for chunk in chunks):
                raise ValueError("sheet data_row_count 与 chunks 不一致")
            if chunks:
                if chunks[0].physical_row_start != sheet.header_row_end + 1:
                    raise ValueError("首个 chunk 必须紧接 header physical range")
                if chunks[-1].physical_row_end != sheet.physical_line_count:
                    raise ValueError("末个 chunk 必须结束于 physical_line_count")
                if chunks[0].logical_row_start != 1:
                    raise ValueError("首个 data logical row 必须从 1 开始")
                if chunks[-1].logical_row_end != sheet.data_row_count:
                    raise ValueError("末个 data logical row 必须等于 data_row_count")
                if any(
                    len(row.values) != sheet.column_count
                    for chunk in chunks
                    for row in chunk.rows
                ):
                    raise ValueError("chunk rows 必须与 sheet headers 构成矩形")
            elif sheet.physical_line_count != sheet.header_row_end:
                raise ValueError("无 data record 时 header 必须结束于文件末行")
            expected_missing = tuple(
                sum(
                    row.values[column] == ""
                    for chunk in chunks
                    for row in chunk.rows
                )
                for column in range(sheet.column_count)
            )
            if sheet.missing_value_counts != expected_missing:
                raise ValueError("sheet missing_value_counts 与 chunks 不一致")
            expected_non_empty = sheet.column_count + sum(
                chunk.non_empty_cell_count for chunk in chunks
            )
            expected_formula_like = sum(
                _is_formula_like(header) for header in sheet.headers
            ) + sum(chunk.formula_like_cell_count for chunk in chunks)
            expected_formula = sum(
                chunk.formula_cell_count for chunk in chunks
            )
            if sheet.non_empty_cell_count != expected_non_empty:
                raise ValueError("sheet non-empty total 与 header/chunks 不一致")
            if sheet.formula_like_cell_count != expected_formula_like:
                raise ValueError("sheet formula-like total 与 header/chunks 不一致")
            if sheet.formula_cell_count != expected_formula:
                raise ValueError("sheet formula total 与 chunks 不一致")
            if self.dataset.file_type == "xlsx":
                expected_descriptor = build_research_xlsx_sheet_descriptor_sha256(
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
                if sheet.descriptor_sha256 != expected_descriptor:
                    raise ValueError("XLSX sheet descriptor 与字段不一致")

        if self.dataset.total_data_row_count != sum(
            sheet.data_row_count for sheet in self.sheets
        ):
            raise ValueError("dataset data row total 与 sheets 不一致")
        if self.dataset.total_column_count != sum(
            sheet.column_count for sheet in self.sheets
        ):
            raise ValueError("dataset column total 与 sheets 不一致")
        if self.dataset.total_non_empty_cell_count != sum(
            sheet.non_empty_cell_count for sheet in self.sheets
        ):
            raise ValueError("dataset non-empty total 与 sheets 不一致")
        if self.dataset.total_formula_like_cell_count != sum(
            sheet.formula_like_cell_count for sheet in self.sheets
        ):
            raise ValueError("dataset formula-like total 与 sheets 不一致")
        if self.dataset.total_formula_cell_count != sum(
            sheet.formula_cell_count for sheet in self.sheets
        ):
            raise ValueError("dataset formula total 与 sheets 不一致")
        if self.dataset.total_merged_range_count != sum(
            sheet.merged_range_count for sheet in self.sheets
        ):
            raise ValueError("dataset merged range total 与 sheets 不一致")
        if self.dataset.file_type == "csv" and (
            self.dataset.descriptor_sha256 != self.sheets[0].descriptor_sha256
        ):
            raise ValueError("CSV dataset descriptor 必须等于唯一 sheet descriptor")
        if self.dataset.file_type == "xlsx":
            metadata = self.xlsx_metadata
            if metadata.total_record_count != sum(
                sheet.record_count for sheet in self.sheets
            ):
                raise ValueError("XLSX total_record_count 与 sheets 不一致")
            expected_descriptor = build_research_xlsx_descriptor_sha256(
                date_system=metadata.date_system,
                workbook_sheet_count=metadata.workbook_sheet_count,
                empty_sheet_count=metadata.empty_sheet_count,
                sheets=self.sheets,
                total_record_count=metadata.total_record_count,
                total_data_row_count=self.dataset.total_data_row_count,
                total_non_empty_cell_count=self.dataset.total_non_empty_cell_count,
                total_formula_like_cell_count=(
                    self.dataset.total_formula_like_cell_count
                ),
                total_formula_cell_count=self.dataset.total_formula_cell_count,
                total_merged_range_count=self.dataset.total_merged_range_count,
            )
            if self.dataset.descriptor_sha256 != expected_descriptor:
                raise ValueError("XLSX dataset descriptor 与 workbook 不一致")
        return self


def build_research_dataset_materialization(
    ingestion_id: str,
    extracted: ExtractedResearchCsv | ExtractedResearchXlsx,
) -> ResearchDatasetMaterialization:
    if isinstance(extracted, ExtractedResearchCsv):
        extracted = ExtractedResearchCsv.model_validate(
            extracted.model_dump(mode="python")
        )
        return _build_research_csv_materialization(ingestion_id, extracted)
    if isinstance(extracted, ExtractedResearchXlsx):
        extracted = ExtractedResearchXlsx.model_validate(
            extracted.model_dump(mode="python")
        )
        return _build_research_xlsx_materialization(ingestion_id, extracted)
    raise TypeError("extracted 必须为 ExtractedResearchCsv 或 ExtractedResearchXlsx")


def _build_research_csv_materialization(
    ingestion_id: str,
    extracted: ExtractedResearchCsv,
) -> ResearchDatasetMaterialization:
    dataset_id = build_research_dataset_id(ingestion_id)
    sheet_id = build_research_dataset_sheet_id(dataset_id, 0, extracted.sheet_name)
    sheet = ResearchDatasetSheetEntity(
        id=sheet_id,
        dataset_id=dataset_id,
        ordinal=0,
        name=extracted.sheet_name,
        headers=extracted.headers,
        header_row_start=extracted.header_row_start,
        header_row_end=extracted.header_row_end,
        physical_line_count=extracted.physical_line_count,
        record_count=extracted.record_count,
        data_row_count=extracted.data_row_count,
        column_count=extracted.column_count,
        non_empty_cell_count=extracted.non_empty_cell_count,
        formula_like_cell_count=extracted.formula_like_cell_count,
        missing_value_counts=extracted.missing_value_counts,
        descriptor_sha256=extracted.descriptor_sha256,
    )
    row_chunks = tuple(
        ResearchDatasetRowChunkEntity(
            id=build_research_dataset_row_chunk_id(
                sheet_id,
                chunk.ordinal,
                chunk.payload_sha256,
            ),
            sheet_id=sheet_id,
            ordinal=chunk.ordinal,
            logical_row_start=chunk.logical_row_start,
            logical_row_end=chunk.logical_row_end,
            physical_row_start=chunk.physical_row_start,
            physical_row_end=chunk.physical_row_end,
            row_count=chunk.row_count,
            non_empty_cell_count=chunk.non_empty_cell_count,
            formula_like_cell_count=chunk.formula_like_cell_count,
            rows=chunk.rows,
            payload_sha256=chunk.payload_sha256,
        )
        for chunk in extracted.chunks
    )
    dataset = ResearchDatasetEntity(
        id=dataset_id,
        ingestion_id=ingestion_id,
        file_type="csv",
        sheet_count=1,
        total_data_row_count=extracted.data_row_count,
        total_column_count=extracted.column_count,
        total_non_empty_cell_count=extracted.non_empty_cell_count,
        total_formula_like_cell_count=extracted.formula_like_cell_count,
        descriptor_sha256=extracted.descriptor_sha256,
    )
    return ResearchDatasetMaterialization(
        dataset=dataset,
        sheets=(sheet,),
        row_chunks=row_chunks,
    )


def _build_research_xlsx_materialization(
    ingestion_id: str,
    extracted: ExtractedResearchXlsx,
) -> ResearchDatasetMaterialization:
    dataset_id = build_research_dataset_id(ingestion_id)
    sheets: list[ResearchDatasetSheetEntity] = []
    row_chunks: list[ResearchDatasetRowChunkEntity] = []
    for extracted_sheet in extracted.sheets:
        sheet_id = build_research_dataset_sheet_id(
            dataset_id,
            extracted_sheet.ordinal,
            extracted_sheet.name,
        )
        sheets.append(
            ResearchDatasetSheetEntity(
                id=sheet_id,
                dataset_id=dataset_id,
                ordinal=extracted_sheet.ordinal,
                name=extracted_sheet.name,
                visibility=extracted_sheet.visibility,
                headers=extracted_sheet.headers,
                header_row_start=extracted_sheet.header_row_start,
                header_row_end=extracted_sheet.header_row_end,
                physical_line_count=extracted_sheet.physical_line_count,
                record_count=extracted_sheet.record_count,
                data_row_count=extracted_sheet.data_row_count,
                column_count=extracted_sheet.column_count,
                non_empty_cell_count=extracted_sheet.non_empty_cell_count,
                formula_like_cell_count=(
                    extracted_sheet.formula_like_cell_count
                ),
                formula_cell_count=extracted_sheet.formula_cell_count,
                merged_range_count=extracted_sheet.merged_range_count,
                missing_value_counts=extracted_sheet.missing_value_counts,
                descriptor_sha256=extracted_sheet.descriptor_sha256,
            )
        )
        row_chunks.extend(
            ResearchDatasetRowChunkEntity(
                id=build_research_dataset_row_chunk_id(
                    sheet_id,
                    chunk.ordinal,
                    chunk.payload_sha256,
                ),
                sheet_id=sheet_id,
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
                rows=chunk.rows,
                payload_sha256=chunk.payload_sha256,
            )
            for chunk in extracted_sheet.chunks
        )
    dataset = ResearchDatasetEntity(
        id=dataset_id,
        ingestion_id=ingestion_id,
        file_type="xlsx",
        sheet_count=len(sheets),
        total_data_row_count=extracted.total_data_row_count,
        total_column_count=sum(sheet.column_count for sheet in extracted.sheets),
        total_non_empty_cell_count=extracted.total_non_empty_cell_count,
        total_formula_like_cell_count=extracted.total_formula_like_cell_count,
        total_formula_cell_count=extracted.total_formula_cell_count,
        total_merged_range_count=extracted.total_merged_range_count,
        descriptor_sha256=extracted.descriptor_sha256,
    )
    return ResearchDatasetMaterialization(
        dataset=dataset,
        sheets=tuple(sheets),
        row_chunks=tuple(row_chunks),
        xlsx_metadata=ResearchXlsxMaterializationMetadata(
            date_system=extracted.date_system,
            workbook_sheet_count=extracted.workbook_sheet_count,
            empty_sheet_count=extracted.empty_sheet_count,
            total_record_count=extracted.total_record_count,
        ),
    )


__all__ = [
    "ExtractedCsvChunk",
    "ExtractedCsvRow",
    "ExtractedResearchCsv",
    "ExtractedResearchXlsx",
    "ExtractedXlsxChunk",
    "ExtractedXlsxRow",
    "ExtractedXlsxSheet",
    "ResearchDatasetEntity",
    "ResearchDatasetMaterialization",
    "ResearchDatasetRowChunkEntity",
    "ResearchDatasetSheetEntity",
    "ResearchXlsxMaterializationMetadata",
    "build_research_csv_chunk_payload_sha256",
    "build_research_csv_descriptor_sha256",
    "build_research_dataset_id",
    "build_research_dataset_materialization",
    "build_research_dataset_row_chunk_id",
    "build_research_dataset_sheet_id",
    "build_research_xlsx_chunk_payload_sha256",
    "build_research_xlsx_descriptor_sha256",
    "build_research_xlsx_sheet_descriptor_sha256",
]
