import asyncio
import threading


class ChatTurnExecutionRegistry:
    """进程内执行取消信号；数据库终态仍是跨 worker 的事实来源。"""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], asyncio.Event] = {}
        self._signalled: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def register(self, doctor_id: str, request_id: str) -> asyncio.Event:
        key = (doctor_id, request_id)
        event = asyncio.Event()
        with self._lock:
            if key in self._signalled:
                event.set()
            self._events[key] = event
        return event

    def signal(self, doctor_id: str, request_id: str) -> None:
        key = (doctor_id, request_id)
        with self._lock:
            self._signalled.add(key)
            event = self._events.get(key)
        if event is not None:
            event.set()

    def unregister(
        self,
        doctor_id: str,
        request_id: str,
        event: asyncio.Event,
    ) -> None:
        key = (doctor_id, request_id)
        with self._lock:
            if self._events.get(key) is event:
                self._events.pop(key, None)
                self._signalled.discard(key)


_registry = ChatTurnExecutionRegistry()


def get_chat_turn_execution_registry() -> ChatTurnExecutionRegistry:
    return _registry
