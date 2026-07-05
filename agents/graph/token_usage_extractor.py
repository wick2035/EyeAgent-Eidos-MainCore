"""
Token usage 提取工具。

不同 LLM provider 在 LangChain 消息中暴露 usage 的字段并不完全一致，
这里统一做鸭子类型读取：字段缺失或格式不符合预期时返回 None，避免影响主对话流程。
"""
from collections.abc import Mapping
from typing import Any, Optional


def extract_token_used_from_ai_message(message: Any) -> Optional[int]:
    """从 LangChain AIMessage 或兼容对象中提取 token_used。"""
    if message is None:
        return None

    usage_metadata = _get_value(message, "usage_metadata")
    response_metadata = _get_value(message, "response_metadata")

    # 优先级 1/2：usage_metadata.total_tokens 或 usage_metadata["total_tokens"]。
    token_used = _extract_total_tokens(usage_metadata)
    if token_used is not None:
        return token_used

    # 优先级 3/4：response_metadata 内 provider 原始 usage 字段。
    token_used = extract_token_used_from_response_metadata(response_metadata)
    if token_used is not None:
        return token_used

    # 优先级 5/6：usage_metadata 内 input/output 或 prompt/completion 兜底。
    return _extract_token_sum(usage_metadata)


def extract_token_used_from_response_metadata(response_metadata: Any) -> Optional[int]:
    """从 response_metadata 中提取 token_used。"""
    if response_metadata is None:
        return None

    token_usage = _get_value(response_metadata, "token_usage")
    usage = _get_value(response_metadata, "usage")

    for candidate in (token_usage, usage, response_metadata):
        token_used = _extract_total_tokens(candidate)
        if token_used is not None:
            return token_used

    for candidate in (token_usage, usage, response_metadata):
        token_used = _extract_token_sum(candidate)
        if token_used is not None:
            return token_used

    return None


def extract_token_used_from_stream_event(event: Any) -> Optional[int]:
    """从 LangChain astream_events 的 on_chat_model_end 事件中提取 token_used。"""
    if not isinstance(event, Mapping):
        return None
    if event.get("event") != "on_chat_model_end":
        return None

    data = event.get("data") or {}
    return _extract_token_used_from_any(data)


def merge_token_used(current: Optional[int], incoming: Optional[int]) -> Optional[int]:
    """合并多次模型调用的 token_used；任一侧缺失时保留已知值。"""
    normalized_current = _to_int(current)
    normalized_incoming = _to_int(incoming)

    if normalized_current is None:
        return normalized_incoming
    if normalized_incoming is None:
        return normalized_current
    return normalized_current + normalized_incoming


def _extract_token_used_from_any(value: Any) -> Optional[int]:
    """递归处理 astream_events 中可能出现的 output/generations/llm_output 结构。"""
    if value is None:
        return None

    token_used = extract_token_used_from_ai_message(value)
    if token_used is not None:
        return token_used

    if isinstance(value, Mapping):
        for key in ("llm_output", "response_metadata", "usage_metadata"):
            metadata_token = extract_token_used_from_response_metadata(value.get(key))
            if metadata_token is not None:
                return metadata_token

        for key in ("output", "response", "message", "chunk", "generations"):
            nested_token = _extract_token_used_from_any(value.get(key))
            if nested_token is not None:
                return nested_token

    elif isinstance(value, (list, tuple)):
        for item in value:
            nested_token = _extract_token_used_from_any(item)
            if nested_token is not None:
                return nested_token

    else:
        for attr in ("llm_output", "response_metadata", "usage_metadata"):
            metadata_token = extract_token_used_from_response_metadata(_get_value(value, attr))
            if metadata_token is not None:
                return metadata_token
        for attr in ("output", "response", "message", "chunk", "generations"):
            nested_token = _extract_token_used_from_any(_get_value(value, attr))
            if nested_token is not None:
                return nested_token

    return None


def _extract_total_tokens(container: Any) -> Optional[int]:
    """读取 total_tokens，兼容对象属性和字典键。"""
    if container is None:
        return None
    return _to_int(_get_value(container, "total_tokens"))


def _extract_token_sum(container: Any) -> Optional[int]:
    """从 input/output 或 prompt/completion 分项相加。"""
    if container is None:
        return None

    input_tokens = _to_int(_get_value(container, "input_tokens"))
    output_tokens = _to_int(_get_value(container, "output_tokens"))
    if input_tokens is not None and output_tokens is not None:
        return input_tokens + output_tokens

    prompt_tokens = _to_int(_get_value(container, "prompt_tokens"))
    completion_tokens = _to_int(_get_value(container, "completion_tokens"))
    if prompt_tokens is not None and completion_tokens is not None:
        return prompt_tokens + completion_tokens

    return None


def _get_value(container: Any, key: str) -> Any:
    """兼容 Mapping 和普通对象属性读取。"""
    if container is None:
        return None
    if isinstance(container, Mapping):
        return container.get(key)
    return getattr(container, key, None)


def _to_int(value: Any) -> Optional[int]:
    """把 provider 返回的数值规范成 int；无效值返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        token_value = int(value)
    except (TypeError, ValueError):
        return None
    if token_value < 0:
        return None
    return token_value


__all__ = [
    "extract_token_used_from_ai_message",
    "extract_token_used_from_response_metadata",
    "extract_token_used_from_stream_event",
    "merge_token_used",
]
