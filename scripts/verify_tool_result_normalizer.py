"""
本地验证 tool_results 归一化逻辑。

运行方式：
    python scripts/verify_tool_result_normalizer.py
"""
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NORMALIZER_PATH = PROJECT_ROOT / "agents" / "graph" / "tool_result_normalizer.py"

spec = importlib.util.spec_from_file_location("tool_result_normalizer", NORMALIZER_PATH)
if spec is None or spec.loader is None:
    raise ModuleNotFoundError(f"Cannot load tool_result_normalizer from {NORMALIZER_PATH}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

normalize_from_tool_calls = module.normalize_from_tool_calls
normalize_from_stream_events = module.normalize_from_stream_events


class FakeToolMessage:
    def __init__(self, content, tool_call_id=None, name=None, status="success", additional_kwargs=None):
        self.content = content
        self.tool_call_id = tool_call_id
        self.name = name
        self.status = status
        self.additional_kwargs = additional_kwargs or {}


def assert_equal(actual, expected, case_name):
    if actual != expected:
        raise AssertionError(f"{case_name}: expected {expected!r}, got {actual!r}")


def assert_has_unified_keys(item, case_name):
    required_keys = {
        "tool_call_id",
        "name",
        "args",
        "status",
        "content",
        "error",
        "metadata",
        "text_offset",
        # 前端 ToolBlock 兼容字段
        "tool",
        "input",
        "output",
    }
    missing = required_keys - set(item.keys())
    if missing:
        raise AssertionError(f"{case_name}: missing keys {sorted(missing)} in {item!r}")


def verify_non_stream_tool_calls():
    tool_calls = [
        {
            "id": "call_1",
            "name": "search_doctor",
            "args": {"department": "ophthalmology"},
        },
        {
            "id": "call_2",
            "name": "lookup_slot",
            "args": {"doctor_id": "d-1"},
        },
    ]
    tool_messages = [
        FakeToolMessage("医生列表", tool_call_id="call_1", name="search_doctor"),
        FakeToolMessage("slot failed", tool_call_id="call_2", name="lookup_slot", status="error"),
    ]

    results = normalize_from_tool_calls(tool_calls, tool_messages)

    assert_equal(len(results), 2, "non-stream result count")
    for index, item in enumerate(results):
        assert_has_unified_keys(item, f"non-stream item {index}")

    assert_equal(results[0]["tool_call_id"], "call_1", "non-stream tool_call_id")
    assert_equal(results[0]["name"], "search_doctor", "non-stream name")
    assert_equal(results[0]["tool"], "search_doctor", "non-stream legacy tool")
    assert_equal(results[0]["args"], {"department": "ophthalmology"}, "non-stream args")
    assert_equal(results[0]["input"], {"department": "ophthalmology"}, "non-stream legacy input")
    assert_equal(results[0]["status"], "success", "non-stream success status")
    assert_equal(results[0]["content"], "医生列表", "non-stream content")
    assert_equal(results[0]["output"], "医生列表", "non-stream legacy output")
    assert_equal(results[0]["text_offset"], 0, "non-stream default text_offset")

    assert_equal(results[1]["status"], "error", "non-stream error status")
    assert_equal(results[1]["error"], "slot failed", "non-stream error message")


def verify_stream_events():
    collected_tool_calls = [
        {
            "tool": "search_doctor",
            "status": "start",
            "input": {"department": "ophthalmology"},
            "text_offset": 12,
        },
        {
            "tool": "lookup_slot",
            "status": "end",
            "input": {"doctor_id": "d-1"},
            "output": {"slot": "09:00"},
            "text_offset": 20,
        },
        {
            "tool": "fetch_report",
            "status": "error",
            "input": {"report_id": "r-1"},
            "output": "not found",
            "text_offset": 30,
        },
    ]

    results = normalize_from_stream_events(collected_tool_calls)

    assert_equal(len(results), 3, "stream result count")
    for index, item in enumerate(results):
        assert_has_unified_keys(item, f"stream item {index}")

    assert_equal(results[0]["name"], "search_doctor", "stream start name")
    assert_equal(results[0]["tool"], "search_doctor", "stream start legacy tool")
    assert_equal(results[0]["status"], "started", "stream started status")
    assert_equal(results[0]["content"], None, "stream started content")
    assert_equal(results[0]["input"], {"department": "ophthalmology"}, "stream started input")
    assert_equal(results[0]["text_offset"], 12, "stream text_offset")

    assert_equal(results[1]["status"], "success", "stream success status")
    assert_equal(results[1]["content"], {"slot": "09:00"}, "stream success content")
    assert_equal(results[1]["output"], {"slot": "09:00"}, "stream success output")

    assert_equal(results[2]["status"], "error", "stream error status")
    assert_equal(results[2]["error"], "not found", "stream error output mapped to error")


def verify_shape_consistency_between_sources():
    non_stream = normalize_from_tool_calls(
        [{"id": "call_same", "name": "same_tool", "args": {"x": 1}}],
        [FakeToolMessage({"ok": True}, tool_call_id="call_same", name="same_tool")],
    )
    stream = normalize_from_stream_events(
        [{"tool": "same_tool", "status": "end", "input": {"x": 1}, "output": {"ok": True}, "text_offset": 0}],
    )

    assert_equal(set(non_stream[0].keys()), set(stream[0].keys()), "unified key set")
    assert_equal(non_stream[0]["name"], stream[0]["name"], "same name")
    assert_equal(non_stream[0]["args"], stream[0]["args"], "same args")
    assert_equal(non_stream[0]["status"], stream[0]["status"], "same status")
    assert_equal(non_stream[0]["content"], stream[0]["content"], "same content")


def main():
    verify_non_stream_tool_calls()
    verify_stream_events()
    verify_shape_consistency_between_sources()
    print("tool_result_normalizer verification passed")


if __name__ == "__main__":
    main()
