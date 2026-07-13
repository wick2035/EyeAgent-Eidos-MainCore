"""科研文档平台接口 DTO。"""

from pydantic import BaseModel, ConfigDict, Field, StrictStr


UUID_PATTERN = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
    r"-[0-9a-f]{4}-[0-9a-f]{12}$"
)
PLATFORM_PRINCIPAL_ID_PATTERN = (
    r"^(?:[0-9a-f]{32}|"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}"
    r"-[89ab][0-9a-f]{3}-[0-9a-f]{12})$"
)


class PurgeResearchDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    doctor_id: StrictStr = Field(pattern=PLATFORM_PRINCIPAL_ID_PATTERN)


__all__ = [
    "PLATFORM_PRINCIPAL_ID_PATTERN",
    "PurgeResearchDocumentRequest",
    "UUID_PATTERN",
]
