import secrets
import threading
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Literal, MutableMapping


_CONFIG_KEY = "attachment_analysis_handle"


class TransientAttachmentContextError(RuntimeError):
    pass


@dataclass(frozen=True)
class AttachmentAnalysis:
    attachment_id: str
    untrusted_text: str


@dataclass(frozen=True)
class TransientAttachmentContext:
    implicit_prompt_id: Literal["attachment-analysis-v1"] | None
    analyses: tuple[AttachmentAnalysis, ...]


@dataclass(frozen=True)
class AttachmentAnalysisBinding:
    handle: str
    _token: Token


_attachment_analysis_handle: ContextVar[str | None] = ContextVar(
    "attachment_analysis_handle",
    default=None,
)
_registry: dict[str, TransientAttachmentContext] = {}
_registry_lock = threading.Lock()


def bind_attachment_analysis(
    context: TransientAttachmentContext,
    runnable_config: MutableMapping | None = None,
) -> AttachmentAnalysisBinding:
    if not isinstance(context, TransientAttachmentContext):
        raise TransientAttachmentContextError("ATTACHMENT_CONTEXT_INCONSISTENT")
    handle = secrets.token_urlsafe(32)
    with _registry_lock:
        while handle in _registry:
            handle = secrets.token_urlsafe(32)
        _registry[handle] = context
    token = _attachment_analysis_handle.set(handle)
    if runnable_config is not None:
        configurable = runnable_config.setdefault("configurable", {})
        if not isinstance(configurable, MutableMapping):
            with _registry_lock:
                _registry.pop(handle, None)
            _attachment_analysis_handle.reset(token)
            raise TransientAttachmentContextError("ATTACHMENT_CONTEXT_INCONSISTENT")
        configurable[_CONFIG_KEY] = handle
    return AttachmentAnalysisBinding(handle=handle, _token=token)


def get_attachment_analysis(
    runnable_config: MutableMapping | None = None,
) -> TransientAttachmentContext:
    handle: object
    if runnable_config is None:
        handle = _attachment_analysis_handle.get()
    else:
        configurable = runnable_config.get("configurable", {})
        handle = configurable.get(_CONFIG_KEY) if isinstance(
            configurable, MutableMapping
        ) else None
    if not isinstance(handle, str) or not handle:
        raise TransientAttachmentContextError("ATTACHMENT_CONTEXT_UNAVAILABLE")
    with _registry_lock:
        context = _registry.get(handle)
    if context is None:
        raise TransientAttachmentContextError("ATTACHMENT_CONTEXT_UNAVAILABLE")
    return context


def reset_attachment_analysis(
    binding: AttachmentAnalysisBinding,
    runnable_config: MutableMapping | None = None,
) -> None:
    with _registry_lock:
        _registry.pop(binding.handle, None)
    if runnable_config is not None:
        configurable = runnable_config.get("configurable", {})
        if (
            isinstance(configurable, MutableMapping)
            and configurable.get(_CONFIG_KEY) == binding.handle
        ):
            configurable.pop(_CONFIG_KEY, None)
    try:
        _attachment_analysis_handle.reset(binding._token)
    except (RuntimeError, ValueError):
        _attachment_analysis_handle.set(None)
