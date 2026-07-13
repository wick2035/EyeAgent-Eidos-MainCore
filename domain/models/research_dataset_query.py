from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class ResearchDatasetAccessScope(BaseModel):
    """一次科研数据集读取的完整授权边界。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doctor_id: StrictStr = Field(min_length=1, max_length=36)
    ingestion_id: StrictStr = Field(min_length=1, max_length=64)
    attachment_id: StrictStr = Field(min_length=1, max_length=64)
    document_version: StrictInt = Field(ge=1)
    processor_type: Literal["csv_dataset_v1", "xlsx_dataset_v1"]
