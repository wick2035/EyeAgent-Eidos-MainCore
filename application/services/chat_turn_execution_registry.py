import asyncio
import threading


class ChatTurnExecutionRegistry:
    """进程内执行取消信号；数据库终态仍是跨 worker 的事实来源。"""

    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._signalled: set[str] = set()
        self._lock = threading.Lock()

    def register(self, request_id: str) -> asyncio.Event:
        event = asyncio.Event()
        with self._lock:
            if request_id in self._signalled:
                event.set()
            self._events[request_id] = event
        return event

    def signal(self, request_id: str) -> None:
        with self._lock:
            self._signalled.add(request_id)
            event = self._events.get(request_id)
        if event is not None:
            event.set()

    def unregister(self, request_id: str, event: asyncio.Event) -> None:
        with self._lock:
            if self._events.get(request_id) is event:
                self._events.pop(request_id, None)
                self._signalled.discard(request_id)


_registry = ChatTurnExecutionRegistry()


def get_chat_turn_execution_registry() -> ChatTurnExecutionRegistry:
    return _registry
