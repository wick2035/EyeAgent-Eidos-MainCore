"""
tool_results 归一化工具。

把非流式 AIMessage.tool_calls/ToolMessage 和流式 on_tool_start/on_tool_end
收集到的事件统一成同一套可落库结构，保证历史消息展示一致。
"""
import json
from typing import Any, Dict, Iterable, List, Optional


UNIFIED_STATUS_STARTED = "started"
UNIFIED_STATUS_SUCCESS = "success"
UNIFIED_STATUS_ERROR = "error"


def normalize_from_tool_calls(tool_calls: Any, tool_messages: Any = None) -> List[Dict[str, Any]]:
    """
    从非流式图结果中的 tool_calls 和 ToolMessage 列表归一化工具结果。

    Args:
        tool_calls: AIMessage.tool_calls，通常为包含 id/name/args 的列表
        tool_messages: 本轮 ToolMessage 列表，用 tool_call_id 与 tool_calls 关联

    Returns:
        统一后的 tool_results 数组
    """
    normalized: List[Dict[str, Any]] = []
    tool_calls_list = _as_list(tool_calls)
    tool_messages_list = _as_list(tool_messages)
    messages_by_call_id = _index_tool_messages(tool_messages_list)
    matched_message_ids = set()

    for tool_call in tool_calls_list:
        tool_call_id = _get_value(tool_call, "id") or _get_value(tool_call, "tool_call_id")
        name = _get_tool_call_name(tool_call)
        args = _get_tool_call_args(tool_call)
        tool_message = messages_by_call_id.get(tool_call_id) if tool_call_id else None
        if tool_message is not None and tool_call_id is not None:
            matched_message_ids.add(tool_call_id)

        content = _get_tool_message_content(tool_message) if tool_message is not None else None
        status = _normalize_message_status(tool_message, content)
        error = _extract_error(tool_message, content, status)
        metadata = _extract_tool_message_metadata(tool_message)

        normalized.append(_build_item(
            tool_call_id=tool_call_id,
            name=name,
            args=args,
            status=status,
            content=content,
            error=error,
            metadata=metadata,
            text_offset=0,
        ))

    # 兜底保留没有匹配到 tool_call 的 ToolMessage，避免工具结果丢失。
    for tool_message in tool_messages_list:
        tool_call_id = _get_value(tool_message, "tool_call_id")
        if tool_call_id in matched_message_ids:
            continue
        content = _get_tool_message_content(tool_message)
        status = _normalize_message_status(tool_message, content)
        normalized.append(_build_item(
            tool_call_id=tool_call_id,
            name=_get_value(tool_message, "name") or "unknown",
            args={},
            status=status,
            content=content,
            error=_extract_error(tool_message, content, status),
            metadata=_extract_tool_message_metadata(tool_message),
            text_offset=0,
        ))

    return normalized


def normalize_from_stream_events(collected_tool_calls: Any) -> List[Dict[str, Any]]:
    """
    从流式 on_tool_start/on_tool_end 收集结果归一化工具结果。

    Args:
        collected_tool_calls: GraphManager.chat_stream_async 收集的旧结构

    Returns:
        统一后的 tool_results 数组
    """
    normalized: List[Dict[str, Any]] = []
    for event in _as_list(collected_tool_calls):
        name = _get_value(event, "name") or _get_value(event, "tool") or "unknown"
        args = _get_value(event, "args")
        if args is None:
            args = _get_value(event, "input")
        if args is None:
            args = {}

        raw_status = _get_value(event, "status")
        status = _normalize_stream_status(raw_status)
        content = _get_value(event, "content")
        if content is None:
            content = _get_value(event, "output")
        error = _get_value(event, "error")
        if status == UNIFIED_STATUS_ERROR and error is None and content is not None:
            error = _stringify_error(content)

        normalized.append(_build_item(
            tool_call_id=_get_value(event, "tool_call_id"),
            name=name,
            args=args,
            status=status,
            content=content,
            error=error,
            metadata=_get_value(event, "metadata") or {},
            text_offset=_safe_int(_get_value(event, "text_offset"), default=0),
        ))

    return normalized


def _build_item(
    tool_call_id: Optional[str],
    name: str,
    args: Any,
    status: str,
    content: Any,
    error: Optional[str],
    metadata: Any,
    text_offset: int,
) -> Dict[str, Any]:
    normalized_name = name or "unknown"
    normalized_args = args if isinstance(args, dict) else ({} if args is None else args)
    normalized_args = _to_json_safe(normalized_args)
    normalized_content = _to_json_safe(content)
    normalized_metadata = _to_json_safe(metadata if isinstance(metadata, dict) else {})
    if not isinstance(normalized_metadata, dict):
        normalized_metadata = {}
    normalized_status = status if status in {
        UNIFIED_STATUS_STARTED,
        UNIFIED_STATUS_SUCCESS,
        UNIFIED_STATUS_ERROR,
    } else UNIFIED_STATUS_SUCCESS

    return {
        "tool_call_id": tool_call_id,
        "name": normalized_name,
        "args": normalized_args,
        "status": normalized_status,
        "content": normalized_content,
        "error": error,
        "metadata": normalized_metadata,
        "text_offset": text_offset,
        # 前端 ToolBlock 兼容字段：当前历史展示读取这些字段。
        "tool": normalized_name,
        "input": normalized_args,
        "output": normalized_content,
    }


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _index_tool_messages(tool_messages: Iterable[Any]) -> Dict[Any, Any]:
    messages_by_call_id: Dict[Any, Any] = {}
    for message in tool_messages:
        tool_call_id = _get_value(message, "tool_call_id")
        if tool_call_id is not None:
            messages_by_call_id[tool_call_id] = message
    return messages_by_call_id


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _get_tool_call_name(tool_call: Any) -> str:
    function_info = _get_value(tool_call, "function")
    return (
        _get_value(tool_call, "name")
        or _get_value(function_info, "name")
        or "unknown"
    )


def _get_tool_call_args(tool_call: Any) -> Any:
    function_info = _get_value(tool_call, "function")
    args = _get_value(tool_call, "args")
    if args is None:
        args = _get_value(function_info, "arguments")
    return args if args is not None else {}


def _get_tool_message_content(tool_message: Any) -> Any:
    return _get_value(tool_message, "content")


def _normalize_message_status(tool_message: Any, content: Any) -> str:
    if tool_message is None:
        return UNIFIED_STATUS_STARTED
    raw_status = str(_get_value(tool_message, "status", "success") or "success").lower()
    if raw_status in {"error", "failed", "fail", "failure"}:
        return UNIFIED_STATUS_ERROR
    if _get_value(tool_message, "error"):
        return UNIFIED_STATUS_ERROR
    return UNIFIED_STATUS_SUCCESS if content is not None else UNIFIED_STATUS_STARTED


def _normalize_stream_status(raw_status: Any) -> str:
    status = str(raw_status or "success").lower()
    if status in {"start", "started", "running"}:
        return UNIFIED_STATUS_STARTED
    if status in {"error", "failed", "fail", "failure"}:
        return UNIFIED_STATUS_ERROR
    return UNIFIED_STATUS_SUCCESS


def _extract_error(tool_message: Any, content: Any, status: str) -> Optional[str]:
    explicit_error = _get_value(tool_message, "error")
    if explicit_error is not None:
        return _stringify_error(explicit_error)

    additional_kwargs = _get_value(tool_message, "additional_kwargs") or {}
    if isinstance(additional_kwargs, dict):
        for key in ("error", "exception"):
            if additional_kwargs.get(key) is not None:
                return _stringify_error(additional_kwargs[key])

    if status == UNIFIED_STATUS_ERROR and content is not None:
        return _stringify_error(content)
    return None


def _extract_tool_message_metadata(tool_message: Any) -> Dict[str, Any]:
    if tool_message is None:
        return {}
    metadata: Dict[str, Any] = {}
    for key in ("response_metadata", "additional_kwargs", "artifact"):
        value = _get_value(tool_message, key)
        if value:
            metadata[key] = value
    return metadata


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_json_safe(value: Any) -> Any:
    # context 最终会 json.dumps，非 JSON 类型统一转字符串，避免落库失败。
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        if isinstance(value, dict):
            return {str(key): _to_json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_to_json_safe(item) for item in value]
        return str(value)


def _stringify_error(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(value)
