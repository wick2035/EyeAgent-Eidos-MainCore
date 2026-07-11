import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from infrastructure.database.mysql_connection import get_db_connection
from infrastructure.repositories.chat_repository_impl import (
    get_conversation_repository,
    get_message_repository,
)
from infrastructure.repositories.chat_turn_request_repository_impl import (
    get_chat_turn_request_repository,
)


logger = logging.getLogger(__name__)

_PREPARED_MAX_AGE = timedelta(minutes=10)
_STREAMING_TIMEOUT_CODE = "ATTACHMENT_ANALYSIS_TIMEOUT"
_PREPARED_TIMEOUT_CODE = "TURN_EXPIRED"
_DEFAULT_INTERVAL_SECONDS = 30.0
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True)
class WatchdogResult:
    scanned: int = 0
    prepared_cancelled: int = 0
    streaming_failed: int = 0


class ChatTurnWatchdog:
    """在 MainCore 本地收敛失去执行者的附件回合。"""

    def __init__(
        self,
        *,
        db=None,
        turn_repo=None,
        conversation_repo=None,
        message_repo=None,
        interval_seconds: float = _DEFAULT_INTERVAL_SECONDS,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds 必须大于 0")
        self.db = db or get_db_connection()
        self.turn_repo = turn_repo or get_chat_turn_request_repository()
        self.conversation_repo = (
            conversation_repo or get_conversation_repository()
        )
        self.message_repo = message_repo or get_message_repository()
        self._interval_seconds = interval_seconds
        self._now = now

    def reconcile_once(self, now: datetime) -> WatchdogResult:
        candidates = self.turn_repo.list_stale(now)
        prepared_cancelled = 0
        streaming_failed = 0

        for candidate in candidates:
            with self.db.transaction():
                self._lock_conversation(candidate.conversation_id)
                entity = self.turn_repo.get_for_update(
                    candidate.doctor_id,
                    candidate.request_id,
                )
                if entity is None or entity.status in _TERMINAL_STATUSES:
                    continue

                if entity.status == "prepared":
                    if entity.create_time > now - _PREPARED_MAX_AGE:
                        continue
                    changed = self.turn_repo.compare_and_set_status(
                        entity.doctor_id,
                        entity.request_id,
                        "prepared",
                        "cancelled",
                        error_code=_PREPARED_TIMEOUT_CODE,
                    )
                    if not changed:
                        continue
                    self._hide_prepared_nodes(entity)
                    prepared_cancelled += 1
                    continue

                if (
                    entity.status != "streaming"
                    or entity.deadline_at is None
                    or entity.deadline_at > now
                ):
                    continue
                changed = self.turn_repo.compare_and_set_status(
                    entity.doctor_id,
                    entity.request_id,
                    "streaming",
                    "failed",
                    error_code=_STREAMING_TIMEOUT_CODE,
                )
                if not changed:
                    continue
                self._require_message_update(
                    entity.assistant_message_id,
                    {
                        "status": "failed",
                        "error_message": _STREAMING_TIMEOUT_CODE,
                    },
                )
                streaming_failed += 1

        return WatchdogResult(
            scanned=len(candidates),
            prepared_cancelled=prepared_cancelled,
            streaming_failed=streaming_failed,
        )

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                self.reconcile_once(self._now())
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # Watchdog 日志只记录错误类型，避免将 SQL、URL 或解析正文带出。
                logger.error(
                    "[ChatTurnWatchdog] 对账失败: %s",
                    type(error).__name__,
                )

            if stop.is_set():
                break
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self._interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

    def _hide_prepared_nodes(self, entity) -> None:
        if entity.operation != "regenerate":
            self._require_message_update(
                entity.user_message_id,
                {"status": "cancelled", "deleted": True},
            )
        self._require_message_update(
            entity.assistant_message_id,
            {"status": "cancelled", "deleted": True},
        )
        compare_and_set = getattr(
            self.conversation_repo,
            "compare_and_set_active_node",
            None,
        )
        if not callable(compare_and_set):
            raise RuntimeError("ACTIVE_NODE_CAS_UNAVAILABLE")
        compare_and_set(
            entity.conversation_id,
            entity.assistant_message_id,
            entity.previous_active_node_id,
        )

    def _lock_conversation(self, conversation_id: str):
        lock_by_id = getattr(self.conversation_repo, "lock_by_id", None)
        conversation = (
            lock_by_id(conversation_id)
            if callable(lock_by_id)
            else self.conversation_repo.get_by_id(conversation_id)
        )
        if conversation is None:
            raise RuntimeError("CHAT_CONVERSATION_NOT_FOUND")
        return conversation

    def _require_message_update(self, message_id: str, updates: dict) -> None:
        if not self.message_repo.update(message_id, updates):
            raise RuntimeError("CHAT_MESSAGE_UPDATE_FAILED")


_watchdog: ChatTurnWatchdog | None = None


def get_chat_turn_watchdog() -> ChatTurnWatchdog:
    global _watchdog
    if _watchdog is None:
        _watchdog = ChatTurnWatchdog()
    return _watchdog


__all__ = [
    "ChatTurnWatchdog",
    "WatchdogResult",
    "get_chat_turn_watchdog",
]
