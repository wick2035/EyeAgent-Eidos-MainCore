import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProcessorType = Literal["pdf_hybrid_v1", "image_vision_v1"]
IngestionStatus = Literal["pending", "processing", "ready", "failed"]

_INGESTION_ID_NAMESPACE = uuid.UUID("abf84020-48f2-5d8a-b447-6bb07d0fcf65")
_SEGMENT_ID_NAMESPACE = uuid.UUID("eb903b83-f4ad-5083-9b81-c4e2a6da7b80")
_SAFE_SEGMENT_METADATA_KEYS = frozenset(
    {
        "block_index",
        "extraction_method",
        "extraction_mode",
        "heading",
        "ocr_applied",
        "ocr_page_count",
        "source_page_numbers",
    }
)


class IngestionIdentity(BaseModel):
    """解析前即可确定的七元摄取身份。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doctor_id: str = Field(min_length=1, max_length=36)
    attachment_id: str = Field(min_length=1, max_length=64)
    document_version: int = Field(ge=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    processor_type: ProcessorType
    extractor_version: str = Field(min_length=1, max_length=32)
    segment_schema_version: str = Field(min_length=1, max_length=32)


def build_research_document_ingestion_id(identity: IngestionIdentity) -> str:
    canonical = json.dumps(
        [
            identity.doctor_id,
            identity.attachment_id,
            identity.document_version,
            identity.content_sha256,
            identity.processor_type,
            identity.extractor_version,
            identity.segment_schema_version,
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(_INGESTION_ID_NAMESPACE, canonical))


def build_research_document_segment_id(
    ingestion_id: str,
    ordinal: int,
    content_sha256: str,
) -> str:
    canonical = json.dumps(
        [ingestion_id, ordinal, content_sha256],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(_SEGMENT_ID_NAMESPACE, canonical))


class ResearchDocumentIngestionEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    doctor_id: str
    attachment_id: str
    document_version: int = Field(ge=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    processor_type: ProcessorType
    extractor_version: str
    segment_schema_version: str
    status: IngestionStatus
    attempt_count: int = Field(ge=0)
    lease_expires_at: Optional[datetime] = None
    page_count: Optional[int] = Field(default=None, ge=0)
    error_code: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)

    @property
    def identity(self) -> IngestionIdentity:
        return IngestionIdentity(
            doctor_id=self.doctor_id,
            attachment_id=self.attachment_id,
            document_version=self.document_version,
            content_sha256=self.content_sha256,
            processor_type=self.processor_type,
            extractor_version=self.extractor_version,
            segment_schema_version=self.segment_schema_version,
        )


class ResearchDocumentSegmentEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = None
    ingestion_id: str
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1)
    content_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    page_start: Optional[int] = Field(default=None, ge=1)
    page_end: Optional[int] = Field(default=None, ge=1)
    sheet_name: Optional[str] = Field(default=None, max_length=128)
    row_start: Optional[int] = Field(default=None, ge=1)
    row_end: Optional[int] = Field(default=None, ge=1)
    token_count: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_stable_identity(self):
        digest = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if self.content_sha256 is not None and self.content_sha256 != digest:
            raise ValueError("content_sha256 与 segment 正文不一致")
        self.content_sha256 = digest

        expected_id = build_research_document_segment_id(
            self.ingestion_id,
            self.ordinal,
            digest,
        )
        if self.id is not None and self.id != expected_id:
            raise ValueError("segment id 必须由 ingestion、ordinal 与正文 hash 生成")
        self.id = expected_id

        unknown_metadata = set(self.metadata) - _SAFE_SEGMENT_METADATA_KEYS
        if unknown_metadata:
            raise ValueError("segment metadata 包含非白名单字段")
        self._validate_metadata_value_types()
        json.dumps(self.metadata, ensure_ascii=False)

        if self.page_start is not None and self.page_end is not None:
            if self.page_end < self.page_start:
                raise ValueError("page_end 不能小于 page_start")
        if self.row_start is not None and self.row_end is not None:
            if self.row_end < self.row_start:
                raise ValueError("row_end 不能小于 row_start")
        return self

    def _validate_metadata_value_types(self) -> None:
        metadata = self.metadata
        for key in ("block_index", "ocr_page_count"):
            if key in metadata and (
                type(metadata[key]) is not int or metadata[key] < 0
            ):
                raise ValueError(f"segment metadata {key} 必须是非负整数")

        for key in ("extraction_method", "extraction_mode", "heading"):
            if key in metadata and not isinstance(metadata[key], str):
                raise ValueError(f"segment metadata {key} 必须是字符串")

        if "ocr_applied" in metadata and type(metadata["ocr_applied"]) is not bool:
            raise ValueError("segment metadata ocr_applied 必须是布尔值")

        if "source_page_numbers" in metadata:
            pages = metadata["source_page_numbers"]
            if not isinstance(pages, list) or not all(
                type(page) is int and page >= 1 for page in pages
            ):
                raise ValueError(
                    "segment metadata source_page_numbers 必须是正整数数组"
                )


class ExtractedResearchPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    text: str
    extraction_method: Literal["digital_text", "ocr", "vision"]


class SelectedResearchSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str
    ingestion_id: str
    attachment_id: str
    document_version: int = Field(ge=1)
    content: str
    page_start: Optional[int] = Field(default=None, ge=1)
    page_end: Optional[int] = Field(default=None, ge=1)
    token_count: int = Field(ge=0)
    score: float = 0.0
