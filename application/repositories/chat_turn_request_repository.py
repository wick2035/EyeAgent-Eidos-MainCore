from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence

from domain.models.chat_turn_request import ChatTurnRequestEntity


class ChatTurnRequestRepository(ABC):
    """附件回合幂等记录仓储接口。"""

    @abstractmethod
    def get(
        self,
        doctor_id: str,
        request_id: str,
    ) -> Optional[ChatTurnRequestEntity]:
        pass

    @abstractmethod
    def get_for_update(
        self,
        doctor_id: str,
        request_id: str,
    ) -> Optional[ChatTurnRequestEntity]:
        pass

    @abstractmethod
    def insert(self, entity: ChatTurnRequestEntity) -> ChatTurnRequestEntity:
        pass

    @abstractmethod
    def compare_and_set_status(
        self,
        doctor_id: str,
        request_id: str,
        expected_status: str | Sequence[str],
        new_status: str,
        error_code: Optional[str] = None,
        execute_started_at: Optional[datetime] = None,
        deadline_at: Optional[datetime] = None,
    ) -> bool:
        pass

    @abstractmethod
    def get_active_for_conversation(
        self,
        conversation_id: str,
        ignore_request_id: Optional[str] = None,
    ) -> Optional[ChatTurnRequestEntity]:
        pass

    @abstractmethod
    def expire_stale_turns(self, now: Optional[datetime] = None) -> int:
        pass
