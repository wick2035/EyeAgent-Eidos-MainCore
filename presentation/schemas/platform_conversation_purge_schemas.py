from pydantic import BaseModel


class PlatformConversationPurgeRequest(BaseModel):
    doctor_id: str
