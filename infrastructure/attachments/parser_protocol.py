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
        if self.file_type not in valid_contracts or self.mime_type not in valid_contracts[
            self.file_type
        ]:
            raise AttachmentParserError("ATTACHMENT_TYPE_INVALID")
        if self.file_type == "image" and self.declared_page_count is not None:
            raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_INVALID")
        if self.file_type == "pdf" and (
            not isinstance(self.declared_page_count, int)
            or isinstance(self.declared_page_count, bool)
            or not 1 <= self.declared_page_count <= 8
        ):
            raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_INVALID")

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "input_filename": self.input_filename,
                "file_type": self.file_type,
                "mime_type": self.mime_type,
                "declared_page_count": self.declared_page_count,
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
