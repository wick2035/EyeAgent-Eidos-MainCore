import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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
        }
        if (
            not isinstance(self.profile, str)
            or self.profile not in {"assistant_visual_v1", "research_pdf_v1"}
        ):
            raise AttachmentParserError("ATTACHMENT_PROFILE_INVALID")
        if self.file_type not in valid_contracts or self.mime_type not in valid_contracts[
            self.file_type
        ]:
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if self.profile == "research_pdf_v1" and self.file_type != "pdf":
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if self.file_type == "image" and self.declared_page_count is not None:
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
