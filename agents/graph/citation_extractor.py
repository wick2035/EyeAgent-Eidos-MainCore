"""
Citation 抽取与归一化工具。

从搜索工具返回的不稳定 output 中提取前端 CitationBlock 可消费的
CitationSource 结构，失败时返回空数组，不影响主流程。
"""
import json
from typing import Any, Dict, List, Optional


MAX_CITATIONS = 10
MAX_SNIPPET_LENGTH = 300
SOURCE_TYPE_MAP = {
    "general": "web",
    "web": "web",
    "pubmed": "pubmed",
    "scholar": "scholar",
    "local": "local",
    "record": "record",
}
VALID_SOURCE_TYPES = {"web", "pubmed", "scholar", "local", "record", "unknown"}


def normalize_citation(raw: dict, index: int) -> dict:
    """
    将单条搜索结果归一化为前端 CitationSource 结构。

    Args:
        raw: 搜索结果字典，可能包含 title/url/snippet/content/sourceType 等字段
        index: 从 0 开始的 citation 序号

    Returns:
        dict: 归一化后的 citation；无法识别 title/url/snippet 时返回空字典
    """
    if not isinstance(raw, dict):
        return {}

    title = _clean_text(
        raw.get("title")
        or raw.get("name")
        or raw.get("source")
        or raw.get("url")
    )
    url = _clean_text(raw.get("url") or raw.get("link"))
    snippet = _clean_text(
        raw.get("snippet")
        or raw.get("summary")
        or raw.get("description")
        or raw.get("content")
        or raw.get("abstract")
    )

    if not title and not url and not snippet:
        return {}

    source_type = _normalize_source_type(
        raw.get("sourceType")
        or raw.get("source_type")
        or raw.get("search_type")
        or raw.get("type")
    )

    citation: Dict[str, Any] = {
        "id": f"c{index + 1}",
        "title": title or url or f"Citation {index + 1}",
        "sourceType": source_type,
    }
    if url:
        citation["url"] = url
    if snippet:
        citation["snippet"] = snippet[:MAX_SNIPPET_LENGTH]
    return citation


def extract_citations_from_search_results(search_results) -> List[Dict[str, Any]]:
    """
    从搜索工具 output 中抽取 citations。

    支持 web_search_medical 返回的 results_by_type 结构，也兼容 list/dict/JSON string。
    普通文本或无法识别的结构返回空数组。
    """
    try:
        parsed = _parse_search_results(search_results)
        raw_items = _collect_raw_items(parsed)
        citations = [normalize_citation(item, index) for index, item in enumerate(raw_items)]
        return deduplicate_citations([item for item in citations if item])
    except Exception:
        # citation 仅用于历史展示增强，抽取失败不能影响主回复/落库。
        return []


def deduplicate_citations(citations) -> List[Dict[str, Any]]:
    """
    按 URL 优先、其次标题去重，并重新生成连续 id。
    """
    deduped: List[Dict[str, Any]] = []
    seen = set()

    for citation in citations if isinstance(citations, list) else []:
        if not isinstance(citation, dict):
            continue
        key = _dedupe_key(citation)
        if not key or key in seen:
            continue
        seen.add(key)
        normalized = dict(citation)
        normalized["id"] = f"c{len(deduped) + 1}"
        if normalized.get("snippet"):
            normalized["snippet"] = str(normalized["snippet"])[:MAX_SNIPPET_LENGTH]
        if normalized.get("sourceType") not in VALID_SOURCE_TYPES:
            normalized["sourceType"] = "unknown"
        deduped.append(normalized)
        if len(deduped) >= MAX_CITATIONS:
            break

    return deduped


def _parse_search_results(value: Any) -> Any:
    if hasattr(value, "content"):
        value = getattr(value, "content")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return value


def _collect_raw_items(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, dict):
        results_by_type = parsed.get("results_by_type")
        if isinstance(results_by_type, dict):
            items: List[Dict[str, Any]] = []
            for search_type, results in results_by_type.items():
                for item in _as_list(results):
                    if isinstance(item, dict):
                        enriched = dict(item)
                        enriched.setdefault("search_type", search_type)
                        items.append(enriched)
            return items

        for key in ("results", "items", "data", "citations", "sources"):
            if key in parsed:
                return [item for item in _as_list(parsed.get(key)) if isinstance(item, dict)]

        if any(key in parsed for key in ("title", "url", "snippet", "content")):
            return [parsed]
        return []

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]

    return []


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalize_source_type(value: Any) -> str:
    source_type = str(value or "unknown").strip().lower()
    return SOURCE_TYPE_MAP.get(source_type, source_type if source_type in VALID_SOURCE_TYPES else "unknown")


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe_key(citation: Dict[str, Any]) -> Optional[str]:
    url = _clean_text(citation.get("url"))
    if url:
        return f"url:{url.lower()}"
    title = _clean_text(citation.get("title"))
    if title:
        return f"title:{title.lower()}"
    return None
