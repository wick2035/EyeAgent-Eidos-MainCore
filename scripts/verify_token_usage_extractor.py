"""
本地验证 token usage 提取逻辑。

运行方式：
    python scripts/verify_token_usage_extractor.py
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR_PATH = PROJECT_ROOT / "agents" / "graph" / "token_usage_extractor.py"

spec = importlib.util.spec_from_file_location("token_usage_extractor", EXTRACTOR_PATH)
if spec is None or spec.loader is None:
    raise ModuleNotFoundError(f"Cannot load token_usage_extractor from {EXTRACTOR_PATH}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

extract_token_used_from_ai_message = module.extract_token_used_from_ai_message
extract_token_used_from_response_metadata = module.extract_token_used_from_response_metadata
extract_token_used_from_stream_event = module.extract_token_used_from_stream_event
merge_token_used = module.merge_token_used


class FakeMessage:
    def __init__(self, usage_metadata=None, response_metadata=None):
        self.usage_metadata = usage_metadata
        self.response_metadata = response_metadata


def assert_equal(actual, expected, case_name):
    if actual != expected:
        raise AssertionError(f"{case_name}: expected {expected!r}, got {actual!r}")


def verify_response_metadata_extraction():
    assert_equal(
        extract_token_used_from_response_metadata({"token_usage": {"total_tokens": 42}}),
        42,
        "response_metadata.token_usage.total_tokens",
    )
    assert_equal(
        extract_token_used_from_response_metadata({"usage": {"total_tokens": 43}}),
        43,
        "response_metadata.usage.total_tokens",
    )
    assert_equal(
        extract_token_used_from_response_metadata({"usage": {"input_tokens": 20, "output_tokens": 23}}),
        43,
        "response_metadata input_tokens + output_tokens",
    )
    assert_equal(
        extract_token_used_from_response_metadata({"token_usage": {"prompt_tokens": 19, "completion_tokens": 24}}),
        43,
        "response_metadata prompt_tokens + completion_tokens",
    )
    assert_equal(
        extract_token_used_from_response_metadata({"usage": {"total_tokens": "44"}}),
        44,
        "response_metadata numeric string total_tokens",
    )
    assert_equal(
        extract_token_used_from_response_metadata({"usage": {"total_tokens": "bad"}}),
        None,
        "response_metadata invalid token value",
    )


def verify_ai_message_extraction():
    assert_equal(
        extract_token_used_from_ai_message(FakeMessage(usage_metadata=SimpleNamespace(total_tokens=51))),
        51,
        "AIMessage usage_metadata.total_tokens attribute",
    )
    assert_equal(
        extract_token_used_from_ai_message(FakeMessage(usage_metadata={"total_tokens": 52})),
        52,
        "AIMessage usage_metadata['total_tokens']",
    )
    assert_equal(
        extract_token_used_from_ai_message(FakeMessage(usage_metadata={"input_tokens": 25, "output_tokens": 28})),
        53,
        "AIMessage usage_metadata input_tokens + output_tokens",
    )
    assert_equal(
        extract_token_used_from_ai_message(FakeMessage(usage_metadata={"prompt_tokens": 26, "completion_tokens": 28})),
        54,
        "AIMessage usage_metadata prompt_tokens + completion_tokens",
    )
    assert_equal(
        extract_token_used_from_ai_message(
            FakeMessage(response_metadata={"token_usage": {"total_tokens": 55}})
        ),
        55,
        "AIMessage response_metadata fallback",
    )
    assert_equal(
        extract_token_used_from_ai_message(FakeMessage()),
        None,
        "AIMessage missing usage",
    )


def verify_stream_event_extraction():
    message = FakeMessage(usage_metadata={"total_tokens": 61})
    assert_equal(
        extract_token_used_from_stream_event({"event": "on_chat_model_end", "data": {"output": message}}),
        61,
        "stream event output AIMessage",
    )
    assert_equal(
        extract_token_used_from_stream_event({
            "event": "on_chat_model_end",
            "data": {"output": {"generations": [[{"message": FakeMessage(usage_metadata={"total_tokens": 62})}]]}},
        }),
        62,
        "stream event nested generations message",
    )
    assert_equal(
        extract_token_used_from_stream_event({
            "event": "on_chat_model_end",
            "data": {"output": {"llm_output": {"token_usage": {"total_tokens": 63}}}},
        }),
        63,
        "stream event llm_output token_usage",
    )
    assert_equal(
        extract_token_used_from_stream_event({"event": "on_chat_model_stream", "data": {"chunk": message}}),
        None,
        "stream event ignores non-end events",
    )


def verify_merge_token_used():
    assert_equal(merge_token_used(None, None), None, "merge none + none")
    assert_equal(merge_token_used(None, 7), 7, "merge none + incoming")
    assert_equal(merge_token_used(5, None), 5, "merge current + none")
    assert_equal(merge_token_used(5, 7), 12, "merge current + incoming")


def main():
    verify_response_metadata_extraction()
    verify_ai_message_extraction()
    verify_stream_event_extraction()
    verify_merge_token_used()
    print("token_usage_extractor verification passed")


if __name__ == "__main__":
    main()
