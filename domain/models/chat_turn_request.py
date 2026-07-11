import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatTurnRequestEntity(BaseModel):
    """附件回合幂等记录，对应 ``chat_turn_request`` 表。"""

    doctor_id: str
    request_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation: str
    conversation_id: str
    session_id: str
    patient_id: str
    source_message_id: Optional[str] = None
    implicit_prompt_id: Optional[str] = None
    attachment_ids_json: str
    user_message_id: str
    assistant_message_id: str
    previous_active_node_id: Optional[str] = None
    status: str = "prepared"
    error_code: Optional[str] = None
    execute_started_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)

    @property
    def attachment_ids(self) -> list[str]:
        value = json.loads(self.attachment_ids_json)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("attachment_ids_json 必须是字符串数组")
        return value

    @property
    def attachment_only(self) -> bool:
        return self.implicit_prompt_id == "attachment-analysis-v1"
