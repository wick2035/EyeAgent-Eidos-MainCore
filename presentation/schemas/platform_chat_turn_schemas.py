from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    field_validator,
    model_serializer,
    model_validator,
)

from application.services.chat_turn_fingerprint import (
    fingerprint_turn_from_request,
    normalize_message,
)
from domain.models.chat_entity import canonicalize_citations


TurnStatus = Literal[
    "prepared",
    "streaming",
    "completed",
    "failed",
    "cancelled",
]
ImplicitPromptId = Literal[
    "attachment-analysis-v1",
    "research-document-analysis-v1",
]
AgentType = Literal["health", "research"]
AttachmentScope = Literal["patient", "research"]
ResearchType = Literal["general", "pubmed", "scholar"]


class ResearchOptionsV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable_institution_data: StrictBool
    enable_web_search: StrictBool
    types: list[ResearchType]

    @model_validator(mode="after")
    def normalize_types(self) -> "ResearchOptionsV2":
        if not self.enable_web_search:
            self.types = []
            return self
        selected = set(self.types)
        self.types = [
            search_type
            for search_type in ("general", "pubmed", "scholar")
            if search_type in selected
        ]
        self.enable_web_search = bool(self.types)
        return self


class InternalAttachmentDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment_id: str
    file_type: Literal["image", "pdf", "text"]
    filename: str
    mime_type: Literal[
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
        "text/plain",
    ]
    size_bytes: int = Field(strict=True, gt=0, le=30 * 1024 * 1024)
    page_count: int | None = Field(default=None, strict=True, ge=1, le=100)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_version: int = Field(strict=True, ge=1)
    analysis_attempt_id: str
    download_url: str

    @model_validator(mode="after")
    def validate_file_type_contract(self) -> "InternalAttachmentDescriptor":
        if self.file_type == "image":
            if not self.mime_type.startswith("image/"):
                raise ValueError("image 必须使用 image MIME type")
            if self.size_bytes > 10 * 1024 * 1024:
                raise ValueError("image size_bytes 不得超过 10MB")
            if self.page_count is not None:
                raise ValueError("image 不允许 page_count")
        elif self.file_type == "pdf":
            if self.mime_type != "application/pdf":
                raise ValueError("pdf 必须使用 application/pdf")
            if self.page_count is None:
                raise ValueError("pdf 必须提供 page_count")
        elif self.file_type == "text":
            if (
                self.mime_type != "text/plain"
                or self.size_bytes > 512 * 1024
                or self.page_count is not None
            ):
                raise ValueError("text descriptor invalid")
        return self


class PreparePlatformChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1, 2] = 1
    request_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation: Literal["normal", "edit_resend", "regenerate"]
    conversation_id: str
    session_id: str
    patient_id: str | None
    doctor_id: str
    agent_type: AgentType | None = None
    attachment_scope: AttachmentScope | None = None
    research_options: ResearchOptionsV2 | None = None
    message: str = ""
    source_message_id: str | None = None
    implicit_prompt_id: ImplicitPromptId | None = None
    attachment_ids: list[str] = Field(min_length=1, max_length=4)

    @property
    def attachment_only(self) -> bool:
        return not bool(self.message)

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "PreparePlatformChatTurnRequest":
        self.message = normalize_message(self.message)
        self._validate_agent_contract()
        if not self.message and not self.attachment_ids:
            raise ValueError("message 或 attachment_ids 至少提供一个")
        expected_prompt = (
            "research-document-analysis-v1"
            if self.agent_type == "research"
            else "attachment-analysis-v1"
        )
        if not self.message and self.implicit_prompt_id != expected_prompt:
            raise ValueError(f"纯附件必须使用 {expected_prompt}")
        if self.message and self.implicit_prompt_id is not None:
            raise ValueError("文字+附件不得使用隐式提示")
        if self.operation == "normal" and self.source_message_id is not None:
            raise ValueError("normal 不允许 source_message_id")
        if self.operation != "normal" and not self.source_message_id:
            raise ValueError("分支操作必须提供 source_message_id")
        if fingerprint_turn_from_request(self) != self.request_fingerprint:
            raise ValueError("REQUEST_IDEMPOTENCY_CONFLICT")
        return self

    def _validate_agent_contract(self) -> None:
        v2_fields = {
            "patient_id",
            "doctor_id",
            "agent_type",
            "attachment_scope",
            "research_options",
        }
        if self.version == 1:
            if self.model_fields_set & (v2_fields - {"patient_id", "doctor_id"}):
                raise ValueError("v1 仅允许 health/patient")
            if not isinstance(self.patient_id, str) or not self.patient_id.strip():
                raise ValueError("v1 patient_id 不得为空")
            return
        missing = v2_fields - self.model_fields_set
        if missing:
            raise ValueError(f"v2 缺少字段: {','.join(sorted(missing))}")
        if self.agent_type == "health":
            if (
                self.attachment_scope != "patient"
                or not isinstance(self.patient_id, str)
                or not self.patient_id.strip()
                or self.research_options is not None
            ):
                raise ValueError("health 仅允许 patient scope")
            return
        if (
            self.agent_type != "research"
            or self.attachment_scope != "research"
            or self.patient_id is not None
            or self.research_options is None
        ):
            raise ValueError("research 仅允许 research scope")

    @model_serializer(mode="wrap")
    def serialize_versioned(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict:
        data = handler(self)
        if self.version == 1:
            data.pop("agent_type", None)
            data.pop("attachment_scope", None)
            data.pop("research_options", None)
        return data

class PreparePlatformChatTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: TurnStatus
    attachment_only: bool
    implicit_prompt_id: ImplicitPromptId | None = None


class ExecutePlatformChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1, 2] = 1
    request_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_id: str
    session_id: str
    patient_id: str | None
    doctor_id: str
    agent_type: AgentType | None = None
    attachment_scope: AttachmentScope | None = None
    research_options: ResearchOptionsV2 | None = None
    user_message_id: str
    assistant_message_id: str
    attachments: list[InternalAttachmentDescriptor] = Field(
        min_length=1,
        max_length=4,
    )

    @model_validator(mode="after")
    def validate_total_attachment_size(self) -> "ExecutePlatformChatTurnRequest":
        self._validate_agent_contract()
        if any(
            attachment.file_type == "text" for attachment in self.attachments
        ) and (
            self.version != 2
            or self.agent_type != "research"
            or self.attachment_scope != "research"
            or self.patient_id is not None
        ):
            raise ValueError("text 仅允许 v2 research/research/null-patient")
        total_size = sum(attachment.size_bytes for attachment in self.attachments)
        if total_size > 40 * 1024 * 1024:
            raise ValueError("附件总量不得超过 40MB")
        pdf_pages = [
            attachment.page_count or 0
            for attachment in self.attachments
            if attachment.file_type == "pdf"
        ]
        if self.attachment_scope in (None, "patient") and any(
            page_count > 8 for page_count in pdf_pages
        ):
            raise ValueError("PATIENT PDF 不得超过 8 页")
        if self.attachment_scope == "research" and sum(pdf_pages) > 120:
            raise ValueError("RESEARCH PDF 总页数不得超过 120")
        return self

    def _validate_agent_contract(self) -> None:
        v2_fields = {
            "patient_id",
            "doctor_id",
            "agent_type",
            "attachment_scope",
            "research_options",
        }
        if self.version == 1:
            if self.model_fields_set & (v2_fields - {"patient_id", "doctor_id"}):
                raise ValueError("v1 仅允许 health/patient")
            if not isinstance(self.patient_id, str) or not self.patient_id.strip():
                raise ValueError("v1 patient_id 不得为空")
            return
        missing = v2_fields - self.model_fields_set
        if missing:
            raise ValueError(f"v2 缺少字段: {','.join(sorted(missing))}")
        if self.agent_type == "health":
            if (
                self.attachment_scope != "patient"
                or not isinstance(self.patient_id, str)
                or not self.patient_id.strip()
                or self.research_options is not None
            ):
                raise ValueError("health 仅允许 patient scope")
            return
        if (
            self.agent_type != "research"
            or self.attachment_scope != "research"
            or self.patient_id is not None
            or self.research_options is None
        ):
            raise ValueError("research 仅允许 research scope")

    @model_serializer(mode="wrap")
    def serialize_versioned(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict:
        data = handler(self)
        if self.version == 1:
            data.pop("version", None)
            data.pop("agent_type", None)
            data.pop("attachment_scope", None)
            data.pop("research_options", None)
        return data


class AbortPlatformChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    doctor_id: str


class AbortPlatformChatTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    conversation_id: str
    status: Literal["cancelled"]


class PlatformChatTurnStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: TurnStatus
    session_id: str
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    error_code: str | None = None
    updated_at: str


class PlatformChatTurnExecutionStartedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["execution_started"]
    request_id: str
    user_message_id: str
    assistant_message_id: str


class PlatformAttachmentStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["attachment_status"]
    request_id: str
    user_message_id: str
    assistant_message_id: str
    attachment_id: str
    analysis_attempt_id: str
    sequence: int
    status: Literal["processing", "ready", "failed"]
    error_code: str | None = None


class PlatformChatTurnDoneEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["done"]
    request_id: str
    user_message_id: str
    assistant_message_id: str
    citations: list[dict[str, Any]]

    @field_validator("citations", mode="before")
    @classmethod
    def validate_citations(cls, value):
        return canonicalize_citations(value)


class PlatformChatTurnErrorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["error"]
    request_id: str
    user_message_id: str
    assistant_message_id: str
    error_code: str
