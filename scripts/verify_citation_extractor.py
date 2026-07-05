"""
验证 citation_extractor 与 MessageContext.citations 的基础行为。
"""
import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 避免触发 agents/__init__.py 导入 graph_manager，从而让验证脚本只依赖本任务文件。
spec = importlib.util.spec_from_file_location(
    "citation_extractor",
    PROJECT_ROOT / "agents" / "graph" / "citation_extractor.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("无法加载 citation_extractor.py")
citation_extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(citation_extractor)

MAX_CITATIONS = citation_extractor.MAX_CITATIONS
MAX_SNIPPET_LENGTH = citation_extractor.MAX_SNIPPET_LENGTH
deduplicate_citations = citation_extractor.deduplicate_citations
extract_citations_from_search_results = citation_extractor.extract_citations_from_search_results
normalize_citation = citation_extractor.normalize_citation

if importlib.util.find_spec("pydantic") is None:
    import types

    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for name in getattr(self.__class__, "__annotations__", {}):
                setattr(self, name, kwargs.get(name, getattr(self.__class__, name, None)))

    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default

    setattr(pydantic_stub, "BaseModel", BaseModel)
    setattr(pydantic_stub, "Field", Field)
    sys.modules["pydantic"] = pydantic_stub

chat_entity_spec = importlib.util.spec_from_file_location(
    "chat_entity",
    PROJECT_ROOT / "domain" / "models" / "chat_entity.py",
)
if chat_entity_spec is None or chat_entity_spec.loader is None:
    raise RuntimeError("无法加载 chat_entity.py")
chat_entity = importlib.util.module_from_spec(chat_entity_spec)
chat_entity_spec.loader.exec_module(chat_entity)
MessageContext = chat_entity.MessageContext


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def verify_normalize_citation():
    citation = normalize_citation(
        {
            "title": "AAO guideline",
            "url": "https://example.com/guideline",
            "snippet": "Relevant excerpt",
            "search_type": "general",
        },
        0,
    )
    assert_equal(citation["id"], "c1", "citation id 应连续生成")
    assert_equal(citation["title"], "AAO guideline", "title 应保留")
    assert_equal(citation["url"], "https://example.com/guideline", "url 应保留")
    assert_equal(citation["sourceType"], "web", "general 应映射为 web")
    assert_equal(citation["snippet"], "Relevant excerpt", "snippet 应保留")


def verify_extract_from_web_search_json():
    payload = {
        "query": "glaucoma guideline",
        "total_results": 3,
        "results_by_type": {
            "general": [
                {
                    "title": "AAO guideline",
                    "url": "https://example.com/guideline",
                    "snippet": "Relevant excerpt",
                }
            ],
            "pubmed": [
                {
                    "title": "PubMed article",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/1",
                    "snippet": "Abstract excerpt",
                }
            ],
        },
    }
    citations = extract_citations_from_search_results(json.dumps(payload, ensure_ascii=False))
    assert_equal(len(citations), 2, "应从 results_by_type 抽取两条 citation")
    assert_equal(citations[0]["sourceType"], "web", "general 来源应为 web")
    assert_equal(citations[1]["sourceType"], "pubmed", "pubmed 来源应保留")


def verify_extract_from_list_and_invalid_input():
    citations = extract_citations_from_search_results([
        {"title": "Scholar paper", "link": "https://scholar.example/a", "type": "scholar"},
        {"message": "not a citation"},
    ])
    assert_equal(len(citations), 1, "list 输入应只保留可识别 citation")
    assert_equal(citations[0]["url"], "https://scholar.example/a", "link 应映射为 url")
    assert_equal(citations[0]["sourceType"], "scholar", "scholar 来源应保留")

    assert_equal(extract_citations_from_search_results("plain text"), [], "普通文本应返回空数组")
    assert_equal(extract_citations_from_search_results({"error": True}), [], "错误结构应返回空数组")


def verify_deduplicate_limit_and_snippet():
    long_snippet = "眼" * (MAX_SNIPPET_LENGTH + 20)
    citations = [
        {
            "id": f"old-{idx}",
            "title": f"Title {idx}",
            "url": f"https://example.com/{idx if idx != 1 else 0}",
            "sourceType": "web",
            "snippet": long_snippet,
        }
        for idx in range(MAX_CITATIONS + 5)
    ]
    deduped = deduplicate_citations(citations)
    assert_equal(len(deduped), MAX_CITATIONS, "citations 应限制最多 10 条")
    assert_equal(deduped[0]["id"], "c1", "去重后 id 应重排")
    assert_equal(deduped[1]["id"], "c2", "重复 URL 应被跳过后继续重排 id")
    assert_true(len(deduped[0]["snippet"]) == MAX_SNIPPET_LENGTH, "snippet 应截断到 300 字符")


def verify_message_context_roundtrip():
    citations = [
        {
            "id": "c1",
            "title": "AAO guideline",
            "url": "https://example.com/guideline",
            "sourceType": "web",
            "snippet": "Relevant excerpt",
        }
    ]
    context = MessageContext(
        conversation_stage="research",
        tool_results=[{"tool": "web_search_medical", "output": "..."}],
        citations=citations,
        metadata={"agent_type": "research"},
    )
    context_list = context.to_context_list()
    assert_true({"citations": citations} in context_list, "to_context_list 应包含 citations")
    restored = MessageContext.from_context_list(context_list)
    assert_equal(restored.citations, citations, "from_context_list 应还原 citations")


def main():
    verify_normalize_citation()
    verify_extract_from_web_search_json()
    verify_extract_from_list_and_invalid_input()
    verify_deduplicate_limit_and_snippet()
    verify_message_context_roundtrip()
    print("citation_extractor verification passed")


if __name__ == "__main__":
    main()
