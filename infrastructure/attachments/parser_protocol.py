import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from infrastructure.attachments.research_csv_contract import (
    MAX_RESEARCH_CSV_CANONICAL_BYTES,
    MAX_RESEARCH_CSV_CHUNK_BYTES,
    MAX_RESEARCH_CSV_CHUNK_RECORDS,
    MAX_RESEARCH_CSV_COLUMNS,
    MAX_RESEARCH_CSV_DESCRIPTOR_BYTES,
    MAX_RESEARCH_CSV_NON_EMPTY_CELLS,
    MAX_RESEARCH_CSV_PHYSICAL_LINES,
    MAX_RESEARCH_CSV_RECORDS,
    NormalizedResearchCsv,
)
from infrastructure.attachments.research_xlsx_contract import (
    MAX_RESEARCH_XLSX_CANONICAL_BYTES,
    MAX_RESEARCH_XLSX_CHUNK_BYTES,
    MAX_RESEARCH_XLSX_CHUNK_ROWS,
    MAX_RESEARCH_XLSX_DESCRIPTOR_BYTES,
    MAX_RESEARCH_XLSX_NON_EMPTY_CELLS,
    MAX_RESEARCH_XLSX_ROWS,
    MAX_RESEARCH_XLSX_SHEETS,
    NormalizedResearchXlsx,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_XLSX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


class AttachmentParserError(RuntimeError):
    def __init__(self, error_code: str, *, detail: str | None = None) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.detail = detail


@dataclass(frozen=True)
class WorkerRequest:
    input_filename: str
    file_type: str
    mime_type: str
    declared_page_count: int | None
    profile: str = "assistant_visual_v1"

    def __post_init__(self) -> None:
        path = Path(self.input_filename)
        if (
            not self.input_filename
            or path.name != self.input_filename
            or self.input_filename in {".", ".."}
        ):
            raise AttachmentParserError("ATTACHMENT_INPUT_PATH_INVALID")
        valid_contracts = {
            "image": {"image/jpeg", "image/png", "image/webp"},
            "pdf": {"application/pdf"},
            "text": {"text/plain"},
            "docx": {_DOCX_MIME_TYPE},
            "csv": {"text/csv"},
            "xlsx": {_XLSX_MIME_TYPE},
        }
        if (
            not isinstance(self.profile, str)
            or self.profile
            not in {
                "assistant_visual_v1",
                "research_pdf_v1",
                "research_text_v1",
                "research_docx_v1",
                "research_csv_v1",
                "research_xlsx_v1",
            }
        ):
            raise AttachmentParserError("ATTACHMENT_PROFILE_INVALID")
        if self.file_type not in valid_contracts or self.mime_type not in valid_contracts[
            self.file_type
        ]:
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if self.profile == "research_pdf_v1" and self.file_type != "pdf":
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if (
            self.profile == "research_text_v1"
            and self.file_type != "text"
        ) or (self.profile != "research_text_v1" and self.file_type == "text"):
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if (
            self.profile == "research_docx_v1"
            and self.file_type != "docx"
        ) or (self.profile != "research_docx_v1" and self.file_type == "docx"):
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if (
            self.profile == "research_csv_v1"
            and self.file_type != "csv"
        ) or (self.profile != "research_csv_v1" and self.file_type == "csv"):
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if (
            self.profile == "research_xlsx_v1"
            and self.file_type != "xlsx"
        ) or (self.profile != "research_xlsx_v1" and self.file_type == "xlsx"):
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if (
            self.file_type in {"image", "text", "docx", "csv", "xlsx"}
            and self.declared_page_count is not None
        ):
            raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_INVALID")
        if self.file_type == "pdf" and (
            not isinstance(self.declared_page_count, int)
            or isinstance(self.declared_page_count, bool)
            or not 1
            <= self.declared_page_count
            <= (100 if self.profile == "research_pdf_v1" else 8)
        ):
            raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_INVALID")

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "input_filename": self.input_filename,
                "file_type": self.file_type,
                "mime_type": self.mime_type,
                "declared_page_count": self.declared_page_count,
                "profile": self.profile,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "WorkerRequest":
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentParserError("ATTACHMENT_WORKER_REQUEST_INVALID") from exc
        if not isinstance(decoded, dict) or set(decoded) != {
            "input_filename",
            "file_type",
            "mime_type",
            "declared_page_count",
            "profile",
        }:
            raise AttachmentParserError("ATTACHMENT_WORKER_REQUEST_INVALID")
        try:
            return cls(**decoded)
        except TypeError as exc:
            raise AttachmentParserError("ATTACHMENT_WORKER_REQUEST_INVALID") from exc


@dataclass(frozen=True)
class WorkerPageManifest:
    page_number: int
    relative_path: str
    sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.page_number, int)
            or isinstance(self.page_number, bool)
            or self.page_number < 1
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        path = Path(self.relative_path)
        if (
            not self.relative_path
            or path.is_absolute()
            or ".." in path.parts
            or path.name != self.relative_path
        ):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        if not isinstance(self.sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.sha256
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")


@dataclass(frozen=True)
class WorkerManifest:
    pages: tuple[WorkerPageManifest, ...]

    def __post_init__(self) -> None:
        if not self.pages or len(self.pages) > 8:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        page_numbers = tuple(page.page_number for page in self.pages)
        if page_numbers != tuple(range(1, len(self.pages) + 1)):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        paths = tuple(page.relative_path for page in self.pages)
        if len(set(paths)) != len(paths):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "pages": [
                    {
                        "page_number": page.page_number,
                        "relative_path": page.relative_path,
                        "sha256": page.sha256,
                    }
                    for page in self.pages
                ]
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "WorkerManifest":
        try:
            decoded: Any = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID") from exc
        if not isinstance(decoded, dict) or set(decoded) != {"pages"}:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        raw_pages = decoded["pages"]
        if not isinstance(raw_pages, list):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        pages: list[WorkerPageManifest] = []
        for raw_page in raw_pages:
            if not isinstance(raw_page, dict) or set(raw_page) != {
                "page_number",
                "relative_path",
                "sha256",
            }:
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            try:
                pages.append(WorkerPageManifest(**raw_page))
            except TypeError as exc:
                raise AttachmentParserError(
                    "ATTACHMENT_WORKER_MANIFEST_INVALID"
                ) from exc
        return cls(tuple(pages))


@dataclass(frozen=True)
class ResearchPdfPageManifest:
    page_number: int
    text_relative_path: str
    text_sha256: str
    ocr_image_relative_path: str | None = None
    ocr_image_sha256: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.page_number, int)
            or isinstance(self.page_number, bool)
            or not 1 <= self.page_number <= 100
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        expected_text_path = f"page-{self.page_number:04d}.txt"
        if self.text_relative_path != expected_text_path:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        if not isinstance(self.text_sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.text_sha256
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        expected_ocr_path = f"page-{self.page_number:04d}-ocr.jpg"
        if (self.ocr_image_relative_path is None) != (
            self.ocr_image_sha256 is None
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if self.ocr_image_relative_path is not None:
            if self.ocr_image_relative_path != expected_ocr_path:
                raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
            if (
                not isinstance(self.ocr_image_sha256, str)
                or not _SHA256_PATTERN.fullmatch(self.ocr_image_sha256)
            ):
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")


@dataclass(frozen=True)
class ResearchPdfManifest:
    pages: tuple[ResearchPdfPageManifest, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.pages, tuple) or not 1 <= len(self.pages) <= 100:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        validated: list[ResearchPdfPageManifest] = []
        for raw_page in self.pages:
            if not isinstance(raw_page, ResearchPdfPageManifest):
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            validated.append(
                ResearchPdfPageManifest(
                    page_number=raw_page.page_number,
                    text_relative_path=raw_page.text_relative_path,
                    text_sha256=raw_page.text_sha256,
                    ocr_image_relative_path=raw_page.ocr_image_relative_path,
                    ocr_image_sha256=raw_page.ocr_image_sha256,
                )
            )
        page_numbers = tuple(page.page_number for page in validated)
        if page_numbers != tuple(range(1, len(validated) + 1)):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        paths = [page.text_relative_path for page in validated]
        paths.extend(
            page.ocr_image_relative_path
            for page in validated
            if page.ocr_image_relative_path is not None
        )
        if len(set(paths)) != len(paths):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        object.__setattr__(self, "pages", tuple(validated))

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "profile": "research_pdf_v1",
                "pages": [
                    {
                        "page_number": page.page_number,
                        "text_relative_path": page.text_relative_path,
                        "text_sha256": page.text_sha256,
                        "ocr_image_relative_path": page.ocr_image_relative_path,
                        "ocr_image_sha256": page.ocr_image_sha256,
                    }
                    for page in self.pages
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "ResearchPdfManifest":
        try:
            decoded: Any = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID") from exc
        if (
            not isinstance(decoded, dict)
            or set(decoded) != {"profile", "pages"}
            or decoded["profile"] != "research_pdf_v1"
            or not isinstance(decoded["pages"], list)
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        pages: list[ResearchPdfPageManifest] = []
        expected_fields = {
            "page_number",
            "text_relative_path",
            "text_sha256",
            "ocr_image_relative_path",
            "ocr_image_sha256",
        }
        for raw_page in decoded["pages"]:
            if not isinstance(raw_page, dict) or set(raw_page) != expected_fields:
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            try:
                pages.append(ResearchPdfPageManifest(**raw_page))
            except TypeError as exc:
                raise AttachmentParserError(
                    "ATTACHMENT_WORKER_MANIFEST_INVALID"
                ) from exc
        return cls(tuple(pages))


@dataclass(frozen=True)
class ResearchTextManifest:
    profile: str
    text_relative_path: str
    text_sha256: str
    character_count: int

    def __post_init__(self) -> None:
        if self.profile != "research_text_v1":
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if self.text_relative_path != "document.txt":
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        if not isinstance(self.text_sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.text_sha256
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if (
            type(self.character_count) is not int
            or not 1 <= self.character_count <= 500_000
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "profile": self.profile,
                "text_relative_path": self.text_relative_path,
                "text_sha256": self.text_sha256,
                "character_count": self.character_count,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "ResearchTextManifest":
        try:
            decoded: Any = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID") from exc
        if not isinstance(decoded, dict) or set(decoded) != {
            "profile",
            "text_relative_path",
            "text_sha256",
            "character_count",
        }:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        try:
            return cls(**decoded)
        except TypeError as exc:
            raise AttachmentParserError(
                "ATTACHMENT_WORKER_MANIFEST_INVALID"
            ) from exc


@dataclass(frozen=True)
class ResearchDocxManifest:
    profile: str
    text_relative_path: str
    text_sha256: str
    character_count: int

    def __post_init__(self) -> None:
        if self.profile != "research_docx_v1":
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if self.text_relative_path != "document.txt":
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        if not isinstance(self.text_sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.text_sha256
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if (
            type(self.character_count) is not int
            or not 1 <= self.character_count <= 500_000
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "profile": self.profile,
                "text_relative_path": self.text_relative_path,
                "text_sha256": self.text_sha256,
                "character_count": self.character_count,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "ResearchDocxManifest":
        try:
            decoded: Any = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentParserError(
                "ATTACHMENT_WORKER_MANIFEST_INVALID"
            ) from exc
        if not isinstance(decoded, dict) or set(decoded) != {
            "profile",
            "text_relative_path",
            "text_sha256",
            "character_count",
        }:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        try:
            return cls(**decoded)
        except TypeError as exc:
            raise AttachmentParserError(
                "ATTACHMENT_WORKER_MANIFEST_INVALID"
            ) from exc


@dataclass(frozen=True)
class ResearchCsvChunkManifest:
    ordinal: int
    relative_path: str
    sha256: str
    byte_count: int
    row_count: int
    logical_row_start: int
    logical_row_end: int
    physical_row_start: int
    physical_row_end: int

    def __post_init__(self) -> None:
        if (
            type(self.ordinal) is not int
            or not 1 <= self.ordinal <= MAX_RESEARCH_CSV_RECORDS
            or self.relative_path != f"chunk-{self.ordinal:05d}.json"
        ):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        if not isinstance(self.sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.sha256
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if (
            type(self.byte_count) is not int
            or not 1 <= self.byte_count <= MAX_RESEARCH_CSV_CHUNK_BYTES
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if (
            type(self.row_count) is not int
            or not 1 <= self.row_count <= MAX_RESEARCH_CSV_CHUNK_RECORDS
            or type(self.logical_row_start) is not int
            or type(self.logical_row_end) is not int
            or not 1 <= self.logical_row_start <= self.logical_row_end <= MAX_RESEARCH_CSV_RECORDS
            or self.logical_row_end - self.logical_row_start + 1 != self.row_count
            or type(self.physical_row_start) is not int
            or type(self.physical_row_end) is not int
            or not 1 <= self.physical_row_start <= self.physical_row_end <= MAX_RESEARCH_CSV_PHYSICAL_LINES
            or self.physical_row_end - self.physical_row_start + 1 < self.row_count
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")


@dataclass(frozen=True)
class ResearchCsvManifest:
    profile: str
    descriptor_relative_path: str
    descriptor_sha256: str
    descriptor_byte_count: int
    chunks: tuple[ResearchCsvChunkManifest, ...]
    physical_line_count: int
    record_count: int
    data_row_count: int
    column_count: int
    non_empty_cell_count: int
    formula_like_cell_count: int

    def __post_init__(self) -> None:
        if self.profile != "research_csv_v1":
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if self.descriptor_relative_path != "descriptor.json":
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        if not isinstance(
            self.descriptor_sha256, str
        ) or not _SHA256_PATTERN.fullmatch(self.descriptor_sha256):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if (
            type(self.descriptor_byte_count) is not int
            or not 1
            <= self.descriptor_byte_count
            <= MAX_RESEARCH_CSV_DESCRIPTOR_BYTES
            or not isinstance(self.chunks, tuple)
            or len(self.chunks) > MAX_RESEARCH_CSV_RECORDS
            or type(self.physical_line_count) is not int
            or not 1 <= self.physical_line_count <= MAX_RESEARCH_CSV_PHYSICAL_LINES
            or type(self.record_count) is not int
            or not 1 <= self.record_count <= MAX_RESEARCH_CSV_RECORDS
            or type(self.data_row_count) is not int
            or not 0 <= self.data_row_count < MAX_RESEARCH_CSV_RECORDS
            or self.record_count != self.data_row_count + 1
            or type(self.column_count) is not int
            or not 1 <= self.column_count <= MAX_RESEARCH_CSV_COLUMNS
            or type(self.non_empty_cell_count) is not int
            or not self.column_count
            <= self.non_empty_cell_count
            <= MAX_RESEARCH_CSV_NON_EMPTY_CELLS
            or type(self.formula_like_cell_count) is not int
            or not 0 <= self.formula_like_cell_count <= self.non_empty_cell_count
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")

        validated: list[ResearchCsvChunkManifest] = []
        for raw_chunk in self.chunks:
            if not isinstance(raw_chunk, ResearchCsvChunkManifest):
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            validated.append(
                ResearchCsvChunkManifest(
                    ordinal=raw_chunk.ordinal,
                    relative_path=raw_chunk.relative_path,
                    sha256=raw_chunk.sha256,
                    byte_count=raw_chunk.byte_count,
                    row_count=raw_chunk.row_count,
                    logical_row_start=raw_chunk.logical_row_start,
                    logical_row_end=raw_chunk.logical_row_end,
                    physical_row_start=raw_chunk.physical_row_start,
                    physical_row_end=raw_chunk.physical_row_end,
                )
            )
        chunks = tuple(validated)
        if bool(chunks) != bool(self.data_row_count):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if chunks:
            if (
                tuple(chunk.ordinal for chunk in chunks)
                != tuple(range(1, len(chunks) + 1))
                or chunks[0].logical_row_start != 1
                or chunks[-1].logical_row_end != self.data_row_count
                or chunks[-1].physical_row_end != self.physical_line_count
                or sum(chunk.row_count for chunk in chunks) != self.data_row_count
                or any(
                    current.logical_row_start != previous.logical_row_end + 1
                    or current.physical_row_start != previous.physical_row_end + 1
                    for previous, current in zip(chunks, chunks[1:])
                )
            ):
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if (
            self.descriptor_byte_count + sum(chunk.byte_count for chunk in chunks)
            > MAX_RESEARCH_CSV_CANONICAL_BYTES
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        object.__setattr__(self, "chunks", chunks)

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "profile": self.profile,
                "descriptor_relative_path": self.descriptor_relative_path,
                "descriptor_sha256": self.descriptor_sha256,
                "descriptor_byte_count": self.descriptor_byte_count,
                "chunks": [
                    {
                        "ordinal": chunk.ordinal,
                        "relative_path": chunk.relative_path,
                        "sha256": chunk.sha256,
                        "byte_count": chunk.byte_count,
                        "row_count": chunk.row_count,
                        "logical_row_start": chunk.logical_row_start,
                        "logical_row_end": chunk.logical_row_end,
                        "physical_row_start": chunk.physical_row_start,
                        "physical_row_end": chunk.physical_row_end,
                    }
                    for chunk in self.chunks
                ],
                "physical_line_count": self.physical_line_count,
                "record_count": self.record_count,
                "data_row_count": self.data_row_count,
                "column_count": self.column_count,
                "non_empty_cell_count": self.non_empty_cell_count,
                "formula_like_cell_count": self.formula_like_cell_count,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "ResearchCsvManifest":
        try:
            decoded: Any = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentParserError(
                "ATTACHMENT_WORKER_MANIFEST_INVALID"
            ) from exc
        expected_fields = {
            "profile",
            "descriptor_relative_path",
            "descriptor_sha256",
            "descriptor_byte_count",
            "chunks",
            "physical_line_count",
            "record_count",
            "data_row_count",
            "column_count",
            "non_empty_cell_count",
            "formula_like_cell_count",
        }
        if (
            not isinstance(decoded, dict)
            or set(decoded) != expected_fields
            or not isinstance(decoded["chunks"], list)
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        chunk_fields = {
            "ordinal",
            "relative_path",
            "sha256",
            "byte_count",
            "row_count",
            "logical_row_start",
            "logical_row_end",
            "physical_row_start",
            "physical_row_end",
        }
        chunks: list[ResearchCsvChunkManifest] = []
        for raw_chunk in decoded["chunks"]:
            if not isinstance(raw_chunk, dict) or set(raw_chunk) != chunk_fields:
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            try:
                chunks.append(ResearchCsvChunkManifest(**raw_chunk))
            except TypeError as exc:
                raise AttachmentParserError(
                    "ATTACHMENT_WORKER_MANIFEST_INVALID"
                ) from exc
        values = dict(decoded)
        values["chunks"] = tuple(chunks)
        try:
            manifest = cls(**values)
        except TypeError as exc:
            raise AttachmentParserError(
                "ATTACHMENT_WORKER_MANIFEST_INVALID"
            ) from exc
        if manifest.to_json_bytes() != payload:
            raise AttachmentParserError(
                "ATTACHMENT_WORKER_MANIFEST_INVALID"
            )
        return manifest


@dataclass(frozen=True)
class ResearchXlsxChunkManifest:
    sheet_ordinal: int
    ordinal: int
    relative_path: str
    sha256: str
    byte_count: int
    row_count: int
    logical_row_start: int
    logical_row_end: int
    physical_row_start: int
    physical_row_end: int
    non_empty_cell_count: int
    formula_like_cell_count: int
    formula_cell_count: int

    def __post_init__(self) -> None:
        expected_path = (
            f"sheet-{self.sheet_ordinal:03d}-chunk-{self.ordinal:05d}.json"
            if type(self.sheet_ordinal) is int and type(self.ordinal) is int
            else ""
        )
        if (
            type(self.sheet_ordinal) is not int
            or not 0 <= self.sheet_ordinal < MAX_RESEARCH_XLSX_SHEETS
            or type(self.ordinal) is not int
            or not 1 <= self.ordinal <= MAX_RESEARCH_XLSX_ROWS
            or self.relative_path != expected_path
        ):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        if not isinstance(self.sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.sha256
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if (
            type(self.byte_count) is not int
            or not 1 <= self.byte_count <= MAX_RESEARCH_XLSX_CHUNK_BYTES
            or type(self.row_count) is not int
            or not 1 <= self.row_count <= MAX_RESEARCH_XLSX_CHUNK_ROWS
            or type(self.logical_row_start) is not int
            or type(self.logical_row_end) is not int
            or not 1
            <= self.logical_row_start
            <= self.logical_row_end
            <= MAX_RESEARCH_XLSX_ROWS
            or self.logical_row_end - self.logical_row_start + 1
            != self.row_count
            or type(self.physical_row_start) is not int
            or type(self.physical_row_end) is not int
            or not 1
            <= self.physical_row_start
            <= self.physical_row_end
            <= MAX_RESEARCH_XLSX_ROWS
            or self.physical_row_end - self.physical_row_start + 1
            != self.row_count
            or type(self.non_empty_cell_count) is not int
            or not 0
            <= self.non_empty_cell_count
            <= MAX_RESEARCH_XLSX_NON_EMPTY_CELLS
            or type(self.formula_like_cell_count) is not int
            or not 0
            <= self.formula_like_cell_count
            <= self.non_empty_cell_count
            or type(self.formula_cell_count) is not int
            or not 0 <= self.formula_cell_count <= self.formula_like_cell_count
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")


@dataclass(frozen=True)
class ResearchXlsxManifest:
    profile: str
    descriptor_relative_path: str
    descriptor_sha256: str
    descriptor_byte_count: int
    chunks: tuple[ResearchXlsxChunkManifest, ...]
    date_system: str
    workbook_sheet_count: int
    empty_sheet_count: int
    total_record_count: int
    total_data_row_count: int
    total_non_empty_cell_count: int
    total_formula_like_cell_count: int
    total_formula_cell_count: int
    total_merged_range_count: int

    def __post_init__(self) -> None:
        if self.profile != "research_xlsx_v1":
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if self.descriptor_relative_path != "descriptor.json":
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        if not isinstance(
            self.descriptor_sha256, str
        ) or not _SHA256_PATTERN.fullmatch(self.descriptor_sha256):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        non_empty_sheet_count = (
            self.workbook_sheet_count - self.empty_sheet_count
            if type(self.workbook_sheet_count) is int
            and type(self.empty_sheet_count) is int
            else -1
        )
        if (
            type(self.descriptor_byte_count) is not int
            or not 1
            <= self.descriptor_byte_count
            <= MAX_RESEARCH_XLSX_DESCRIPTOR_BYTES
            or not isinstance(self.chunks, tuple)
            or len(self.chunks) > MAX_RESEARCH_XLSX_ROWS
            or self.date_system not in {"1900", "1904"}
            or type(self.workbook_sheet_count) is not int
            or not 1 <= self.workbook_sheet_count <= MAX_RESEARCH_XLSX_SHEETS
            or type(self.empty_sheet_count) is not int
            or not 0 <= self.empty_sheet_count < self.workbook_sheet_count
            or type(self.total_record_count) is not int
            or not non_empty_sheet_count
            <= self.total_record_count
            <= MAX_RESEARCH_XLSX_ROWS + MAX_RESEARCH_XLSX_SHEETS
            or type(self.total_data_row_count) is not int
            or not 0 <= self.total_data_row_count <= MAX_RESEARCH_XLSX_ROWS
            or self.total_record_count
            != self.total_data_row_count + non_empty_sheet_count
            or type(self.total_non_empty_cell_count) is not int
            or not non_empty_sheet_count
            <= self.total_non_empty_cell_count
            <= MAX_RESEARCH_XLSX_NON_EMPTY_CELLS
            or type(self.total_formula_like_cell_count) is not int
            or not 0
            <= self.total_formula_like_cell_count
            <= self.total_non_empty_cell_count
            or type(self.total_formula_cell_count) is not int
            or not 0
            <= self.total_formula_cell_count
            <= self.total_formula_like_cell_count
            or type(self.total_merged_range_count) is not int
            or not 0
            <= self.total_merged_range_count
            <= MAX_RESEARCH_XLSX_NON_EMPTY_CELLS
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")

        validated = tuple(
            ResearchXlsxChunkManifest(
                sheet_ordinal=chunk.sheet_ordinal,
                ordinal=chunk.ordinal,
                relative_path=chunk.relative_path,
                sha256=chunk.sha256,
                byte_count=chunk.byte_count,
                row_count=chunk.row_count,
                logical_row_start=chunk.logical_row_start,
                logical_row_end=chunk.logical_row_end,
                physical_row_start=chunk.physical_row_start,
                physical_row_end=chunk.physical_row_end,
                non_empty_cell_count=chunk.non_empty_cell_count,
                formula_like_cell_count=chunk.formula_like_cell_count,
                formula_cell_count=chunk.formula_cell_count,
            )
            for chunk in self.chunks
            if isinstance(chunk, ResearchXlsxChunkManifest)
        )
        if len(validated) != len(self.chunks):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if validated != tuple(
            sorted(validated, key=lambda chunk: (chunk.sheet_ordinal, chunk.ordinal))
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        chunks_by_sheet: dict[int, list[ResearchXlsxChunkManifest]] = {}
        for chunk in validated:
            if chunk.sheet_ordinal >= self.workbook_sheet_count:
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            chunks_by_sheet.setdefault(chunk.sheet_ordinal, []).append(chunk)
        for chunks in chunks_by_sheet.values():
            if tuple(chunk.ordinal for chunk in chunks) != tuple(
                range(1, len(chunks) + 1)
            ) or any(
                current.logical_row_start != previous.logical_row_end + 1
                or current.physical_row_start != previous.physical_row_end + 1
                for previous, current in zip(chunks, chunks[1:])
            ):
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        if (
            sum(chunk.row_count for chunk in validated)
            != self.total_data_row_count
            or sum(chunk.non_empty_cell_count for chunk in validated)
            > self.total_non_empty_cell_count
            or sum(chunk.formula_like_cell_count for chunk in validated)
            > self.total_formula_like_cell_count
            or sum(chunk.formula_cell_count for chunk in validated)
            > self.total_formula_cell_count
            or self.descriptor_byte_count
            + sum(chunk.byte_count for chunk in validated)
            > MAX_RESEARCH_XLSX_CANONICAL_BYTES
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        object.__setattr__(self, "chunks", validated)

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "profile": self.profile,
                "descriptor_relative_path": self.descriptor_relative_path,
                "descriptor_sha256": self.descriptor_sha256,
                "descriptor_byte_count": self.descriptor_byte_count,
                "chunks": [
                    {
                        "sheet_ordinal": chunk.sheet_ordinal,
                        "ordinal": chunk.ordinal,
                        "relative_path": chunk.relative_path,
                        "sha256": chunk.sha256,
                        "byte_count": chunk.byte_count,
                        "row_count": chunk.row_count,
                        "logical_row_start": chunk.logical_row_start,
                        "logical_row_end": chunk.logical_row_end,
                        "physical_row_start": chunk.physical_row_start,
                        "physical_row_end": chunk.physical_row_end,
                        "non_empty_cell_count": chunk.non_empty_cell_count,
                        "formula_like_cell_count": chunk.formula_like_cell_count,
                        "formula_cell_count": chunk.formula_cell_count,
                    }
                    for chunk in self.chunks
                ],
                "date_system": self.date_system,
                "workbook_sheet_count": self.workbook_sheet_count,
                "empty_sheet_count": self.empty_sheet_count,
                "total_record_count": self.total_record_count,
                "total_data_row_count": self.total_data_row_count,
                "total_non_empty_cell_count": self.total_non_empty_cell_count,
                "total_formula_like_cell_count": self.total_formula_like_cell_count,
                "total_formula_cell_count": self.total_formula_cell_count,
                "total_merged_range_count": self.total_merged_range_count,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "ResearchXlsxManifest":
        try:
            decoded: Any = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttachmentParserError(
                "ATTACHMENT_WORKER_MANIFEST_INVALID"
            ) from exc
        expected_fields = {
            "profile",
            "descriptor_relative_path",
            "descriptor_sha256",
            "descriptor_byte_count",
            "chunks",
            "date_system",
            "workbook_sheet_count",
            "empty_sheet_count",
            "total_record_count",
            "total_data_row_count",
            "total_non_empty_cell_count",
            "total_formula_like_cell_count",
            "total_formula_cell_count",
            "total_merged_range_count",
        }
        chunk_fields = {
            "sheet_ordinal",
            "ordinal",
            "relative_path",
            "sha256",
            "byte_count",
            "row_count",
            "logical_row_start",
            "logical_row_end",
            "physical_row_start",
            "physical_row_end",
            "non_empty_cell_count",
            "formula_like_cell_count",
            "formula_cell_count",
        }
        if (
            not isinstance(decoded, dict)
            or set(decoded) != expected_fields
            or not isinstance(decoded.get("chunks"), list)
        ):
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        chunks: list[ResearchXlsxChunkManifest] = []
        for raw_chunk in decoded["chunks"]:
            if not isinstance(raw_chunk, dict) or set(raw_chunk) != chunk_fields:
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            try:
                chunks.append(ResearchXlsxChunkManifest(**raw_chunk))
            except TypeError as exc:
                raise AttachmentParserError(
                    "ATTACHMENT_WORKER_MANIFEST_INVALID"
                ) from exc
        values = dict(decoded)
        values["chunks"] = tuple(chunks)
        try:
            manifest = cls(**values)
        except TypeError as exc:
            raise AttachmentParserError(
                "ATTACHMENT_WORKER_MANIFEST_INVALID"
            ) from exc
        if manifest.to_json_bytes() != payload:
            raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
        return manifest


@dataclass(frozen=True)
class ParsedAttachmentPage:
    page_number: int
    mime_type: str
    sha256: str
    content: bytes


@dataclass(frozen=True)
class ParsedAttachment:
    attachment_id: str
    file_type: str
    mime_type: str
    pages: tuple[ParsedAttachmentPage, ...]


@dataclass(frozen=True)
class ParsedResearchPdfPage:
    page_number: int
    text: str
    text_sha256: str
    ocr_image_content: bytes | None = None
    ocr_image_sha256: str | None = None


@dataclass(frozen=True)
class ParsedResearchPdf:
    attachment_id: str
    document_version: int
    mime_type: str
    pages: tuple[ParsedResearchPdfPage, ...]

    def __post_init__(self) -> None:
        if type(self.document_version) is not int or self.document_version < 1:
            raise AttachmentParserError("ATTACHMENT_DOCUMENT_VERSION_INVALID")


@dataclass(frozen=True)
class ParsedResearchText:
    attachment_id: str
    document_version: int
    mime_type: str
    text: str
    text_sha256: str
    character_count: int

    def __post_init__(self) -> None:
        if type(self.document_version) is not int or self.document_version < 1:
            raise AttachmentParserError("ATTACHMENT_DOCUMENT_VERSION_INVALID")


@dataclass(frozen=True)
class ParsedResearchDocx:
    attachment_id: str
    document_version: int
    mime_type: str
    text: str
    text_sha256: str
    character_count: int

    def __post_init__(self) -> None:
        if type(self.document_version) is not int or self.document_version < 1:
            raise AttachmentParserError("ATTACHMENT_DOCUMENT_VERSION_INVALID")


@dataclass(frozen=True)
class ParsedResearchCsv:
    attachment_id: str
    document_version: int
    mime_type: str
    normalized: NormalizedResearchCsv

    def __post_init__(self) -> None:
        if type(self.document_version) is not int or self.document_version < 1:
            raise AttachmentParserError("ATTACHMENT_DOCUMENT_VERSION_INVALID")


@dataclass(frozen=True)
class ParsedResearchXlsx:
    attachment_id: str
    document_version: int
    mime_type: str
    normalized: NormalizedResearchXlsx

    def __post_init__(self) -> None:
        if type(self.document_version) is not int or self.document_version < 1:
            raise AttachmentParserError("ATTACHMENT_DOCUMENT_VERSION_INVALID")
