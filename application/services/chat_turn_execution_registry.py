import asyncio
import threading


class ChatTurnExecutionDrainingError(RuntimeError):
    pass


class ChatTurnExecutionConflictError(RuntimeError):
    pass


class ChatTurnExecutionRegistry:
    """进程内执行取消信号；数据库终态仍是跨 worker 的事实来源。"""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], asyncio.Event] = {}
        self._signalled: set[tuple[str, str]] = set()
        self._lock = threading.Lock()
        self._draining = False
        self._idle = asyncio.Event()
        self._idle.set()

    def start_accepting(self) -> None:
        with self._lock:
            if self._events:
                raise RuntimeError(
                    "cannot accept new turns while executions are active"
                )
            self._draining = False

    def begin_drain(self) -> bool:
        with self._lock:
            if self._draining:
                return False
            self._draining = True
            return True

    def is_draining(self) -> bool:
        with self._lock:
            return self._draining

    def active_count(self) -> int:
        with self._lock:
            return len(self._events)

    async def wait_until_idle(self, timeout_seconds: float) -> bool:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must not be negative")
        if self.active_count() == 0:
            return True
        if timeout_seconds == 0:
            return False
        try:
            await asyncio.wait_for(
                self._idle.wait(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            return False
        return True

    def signal_all(self) -> int:
        with self._lock:
            keys = tuple(self._events)
            events = tuple(self._events.values())
            self._signalled.update(keys)
        for event in events:
            event.set()
        return len(events)

    def register_if_accepting(
        self,
        doctor_id: str,
        request_id: str,
    ) -> asyncio.Event:
        key = (doctor_id, request_id)
        with self._lock:
            if self._draining:
                raise ChatTurnExecutionDrainingError
            if key in self._events:
                raise ChatTurnExecutionConflictError
            return self._register_locked(key)

    def register(self, doctor_id: str, request_id: str) -> asyncio.Event:
        key = (doctor_id, request_id)
        with self._lock:
            return self._register_locked(key)

    def _register_locked(
        self,
        key: tuple[str, str],
    ) -> asyncio.Event:
        event = asyncio.Event()
        if key in self._signalled:
            event.set()
        self._events[key] = event
        self._idle.clear()
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
                if not self._events:
                    self._idle.set()


_registry = ChatTurnExecutionRegistry()


def get_chat_turn_execution_registry() -> ChatTurnExecutionRegistry:
    return _registry
