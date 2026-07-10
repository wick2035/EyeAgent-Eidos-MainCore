from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from application.services.chat_turn_fingerprint import (
    fingerprint_turn_from_request,
    normalize_message,
)


TurnStatus = Literal[
    "prepared",
    "streaming",
    "completed",
    "failed",
    "cancelled",
]
ImplicitPromptId = Literal["attachment-analysis-v1"]


class InternalAttachmentDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment_id: str
    file_type: Literal["image", "pdf"]
    filename: str
    mime_type: Literal[
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    ]
    size_bytes: int = Field(gt=0, le=30 * 1024 * 1024)
    page_count: int | None = Field(default=None, ge=1, le=8)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_version: int = Field(ge=1)
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
        else:
            if self.mime_type != "application/pdf":
                raise ValueError("pdf 必须使用 application/pdf")
            if self.page_count is None:
                raise ValueError("pdf 必须提供 page_count")
        return self


class PreparePlatformChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    request_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation: Literal["normal", "edit_resend", "regenerate"]
    conversation_id: str
    session_id: str
    patient_id: str
    doctor_id: str
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
        if not self.message and not self.attachment_ids:
            raise ValueError("message 或 attachment_ids 至少提供一个")
        if not self.message and self.implicit_prompt_id != "attachment-analysis-v1":
            raise ValueError("纯附件必须使用 attachment-analysis-v1")
        if self.message and self.implicit_prompt_id is not None:
            raise ValueError("文字+附件不得使用隐式提示")
        if self.operation == "normal" and self.source_message_id is not None:
            raise ValueError("normal 不允许 source_message_id")
        if self.operation != "normal" and not self.source_message_id:
            raise ValueError("分支操作必须提供 source_message_id")
        if fingerprint_turn_from_request(self) != self.request_fingerprint:
            raise ValueError("REQUEST_IDEMPOTENCY_CONFLICT")
        return self


class PreparePlatformChatTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: TurnStatus
    attachment_only: bool
    implicit_prompt_id: ImplicitPromptId | None = None


class ExecutePlatformChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_id: str
    session_id: str
    patient_id: str
    doctor_id: str
    user_message_id: str
    assistant_message_id: str
    attachments: list[InternalAttachmentDescriptor] = Field(
        min_length=1,
        max_length=4,
    )

    @model_validator(mode="after")
    def validate_total_attachment_size(self) -> "ExecutePlatformChatTurnRequest":
        total_size = sum(attachment.size_bytes for attachment in self.attachments)
        if total_size > 40 * 1024 * 1024:
            raise ValueError("附件总量不得超过 40MB")
        return self


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


class PlatformChatTurnErrorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: Literal["error"]
    request_id: str
    user_message_id: str
    assistant_message_id: str
    error_code: str
