"""科研附件引用工具与服务端映射。"""

import json
import re
from typing import Any, Iterable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from application.services.research_document_context_selector import (
    ResearchCitationCandidate,
)
from domain.models.chat_entity import AttachmentCitation


CITATION_TOOL_NAME = "cite_research_document_segments"
MAX_ATTACHMENT_CITATIONS = 10
MAX_ATTACHMENT_EXCERPT_LENGTH = 300
_DATASET_STATISTICS_SCHEMA_VERSION = "research_dataset_statistics_v1"
_DATASET_STATISTICS_OPERATIONS = frozenset(
    {
        "count",
        "numeric_summary",
        "frequency",
        "grouped_numeric_summary",
    }
)
_DATASET_STATISTICS_SUCCESS_KEYS = frozenset(
    {
        "schema_version",
        "ok",
        "source_segment_id",
        "operation",
        "result",
    }
)


class AttachmentCitationSelection(BaseModel):
    """模型唯一可提交的引用选择。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    segment_ids: list[StrictStr] = Field(
        strict=True,
        min_length=1,
        max_length=MAX_ATTACHMENT_CITATIONS,
    )

    @field_validator("segment_ids")
    @classmethod
    def require_unique_segment_ids(cls, value: list[str]) -> list[str]:
        if any(not segment_id for segment_id in value):
            raise ValueError("segment_id 不能为空")
        if len(set(value)) != len(value):
            raise ValueError("segment_ids 不得重复")
        return value


def build_attachment_citation_tool(
    candidates: Iterable[ResearchCitationCandidate],
) -> StructuredTool:
    """构建只接受本轮 segment ID 的结构化工具。"""

    candidate_tuple = tuple(candidates)
    candidate_ids = _candidate_map(candidate_tuple)
    if not candidate_ids:
        raise ValueError("citation candidates 不能为空")

    def select_segments(segment_ids: list[str]) -> dict[str, list[str]]:
        selection = AttachmentCitationSelection.model_validate(
            {"segment_ids": segment_ids},
            strict=True,
        )
        unknown = [
            segment_id
            for segment_id in selection.segment_ids
            if segment_id not in candidate_ids
        ]
        if unknown:
            raise ValueError("引用了本轮候选集合之外的 segment_id")
        return selection.model_dump(mode="json")

    allowed_ids = json.dumps(
        list(candidate_ids),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return StructuredTool.from_function(
        func=select_segments,
        name=CITATION_TOOL_NAME,
        description=(
            "选择支撑当前回答的科研文档片段。只能提交 segment_ids，"
            f"允许值为 {allowed_ids}。"
        ),
        args_schema=AttachmentCitationSelection,
        infer_schema=False,
    )


def build_attachment_citations(
    segment_ids: list[str],
    candidates: Iterable[ResearchCitationCandidate],
) -> list[dict[str, Any]]:
    """用服务端 candidate 元数据映射 canonical attachment citations。"""

    selection = AttachmentCitationSelection.model_validate(
        {"segment_ids": segment_ids},
        strict=True,
    )
    candidate_by_id = _candidate_map(tuple(candidates))
    unknown = [
        segment_id
        for segment_id in selection.segment_ids
        if segment_id not in candidate_by_id
    ]
    if unknown:
        raise ValueError("引用了本轮候选集合之外的 segment_id")

    citations: list[dict[str, Any]] = []
    for segment_id in selection.segment_ids:
        citations.append(
            _build_attachment_citation(candidate_by_id[segment_id])
        )
    return citations


def build_attachment_citation_fallback(
    candidates: Iterable[ResearchCitationCandidate],
) -> list[dict[str, Any]]:
    """按服务端候选顺序构建每附件优先的确定性 provenance。"""

    candidate_tuple = tuple(candidates)
    candidate_by_id = _candidate_map(candidate_tuple)
    if not candidate_by_id:
        raise ValueError("citation candidates 不能为空")

    # fallback 是服务端 provenance，必须先验证整个候选集合；不能只验证最终
    # 选中的前 10 条，否则尾部损坏候选会被静默掩盖。
    for candidate in candidate_tuple:
        _build_attachment_citation(candidate)

    first_per_attachment: list[str] = []
    seen_attachments: set[str] = set()
    for candidate in candidate_tuple:
        if candidate.attachment_id in seen_attachments:
            continue
        seen_attachments.add(candidate.attachment_id)
        if len(seen_attachments) > MAX_ATTACHMENT_CITATIONS:
            raise ValueError("附件数量超过 citation 上限")
        first_per_attachment.append(candidate.segment_id)

    selected_ids = list(first_per_attachment)
    selected = set(selected_ids)
    for candidate in candidate_tuple:
        if len(selected_ids) >= MAX_ATTACHMENT_CITATIONS:
            break
        if candidate.segment_id in selected:
            continue
        selected.add(candidate.segment_id)
        selected_ids.append(candidate.segment_id)
    return build_attachment_citations(selected_ids, candidate_tuple)


def extract_attachment_citations_from_tool_output(
    output: Any,
    candidates: Iterable[ResearchCitationCandidate],
) -> list[dict[str, Any]]:
    """解析 exact citation tool output；非法输出静默丢弃。"""

    try:
        value = getattr(output, "content", output)
        if isinstance(value, str):
            value = json.loads(value)
        selection = AttachmentCitationSelection.model_validate(
            value,
            strict=True,
        )
        return build_attachment_citations(selection.segment_ids, candidates)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def extract_attachment_citations_from_statistics_output(
    output: Any,
    candidates: Iterable[ResearchCitationCandidate],
) -> list[dict[str, Any]]:
    """从成功的受限统计结果映射服务端可信的 exact sheet citation。"""

    try:
        value = getattr(output, "content", output)
        if isinstance(value, str):
            value = json.loads(value)
        if (
            not isinstance(value, dict)
            or frozenset(value) != _DATASET_STATISTICS_SUCCESS_KEYS
            or value.get("schema_version")
            != _DATASET_STATISTICS_SCHEMA_VERSION
            or value.get("ok") is not True
            or type(value.get("source_segment_id")) is not str
            or not value["source_segment_id"]
            or value.get("operation")
            not in _DATASET_STATISTICS_OPERATIONS
            or not isinstance(value.get("result"), dict)
        ):
            return []
        citations = build_attachment_citations(
            [value["source_segment_id"]],
            candidates,
        )
        if (
            len(citations) != 1
            or citations[0].get("locator", {}).get("type")
            != "sheet_rows"
        ):
            return []
        return citations
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _candidate_map(
    candidates: tuple[ResearchCitationCandidate, ...],
) -> dict[str, ResearchCitationCandidate]:
    result: dict[str, ResearchCitationCandidate] = {}
    for candidate in candidates:
        if not isinstance(candidate, ResearchCitationCandidate):
            raise ValueError("citation candidate 类型无效")
        segment_id = candidate.segment_id
        if not isinstance(segment_id, str) or not segment_id:
            raise ValueError("candidate segment_id 无效")
        if segment_id in result:
            raise ValueError("candidate segment_id 不得重复")
        if (
            not isinstance(candidate.attachment_id, str)
            or not candidate.attachment_id
            or type(candidate.document_version) is not int
            or candidate.document_version < 1
            or not isinstance(candidate.content, str)
        ):
            raise ValueError("citation candidate 元数据无效")
        result[segment_id] = candidate
    return result


def _build_locator(candidate: ResearchCitationCandidate) -> dict[str, Any]:
    page_start = candidate.page_start
    page_end = candidate.page_end
    sheet_name = candidate.sheet_name
    row_start = candidate.row_start
    row_end = candidate.row_end
    page_values = (page_start, page_end)
    sheet_values = (sheet_name, row_start, row_end)
    if all(value is None for value in page_values + sheet_values):
        return {"type": "file"}
    if all(value is None for value in sheet_values):
        if (
            type(page_start) is not int
            or type(page_end) is not int
            or page_start < 1
            or page_end < page_start
        ):
            raise ValueError("citation candidate 页码无效")
        return {
            "type": "page",
            "page_start": page_start,
            "page_end": page_end,
        }
    if all(value is None for value in page_values):
        if (
            not isinstance(sheet_name, str)
            or type(row_start) is not int
            or type(row_end) is not int
            or row_start < 1
            or row_end < row_start
        ):
            raise ValueError("citation candidate 工作表行范围无效")
        return {
            "type": "sheet_rows",
            "sheet_name": sheet_name,
            "row_start": row_start,
            "row_end": row_end,
        }
    raise ValueError("citation candidate locator 字段混用")


def _build_attachment_citation(
    candidate: ResearchCitationCandidate,
) -> dict[str, Any]:
    citation = AttachmentCitation(
        source_type="attachment",
        attachment_id=candidate.attachment_id,
        document_version=candidate.document_version,
        segment_id=candidate.segment_id,
        locator=_build_locator(candidate),
        excerpt=_normalize_excerpt(candidate.content),
    )
    return citation.model_dump(mode="json")


def _normalize_excerpt(content: str) -> str:
    return re.sub(r"\s+", " ", content).strip()[
        :MAX_ATTACHMENT_EXCERPT_LENGTH
    ]


__all__ = [
    "AttachmentCitationSelection",
    "CITATION_TOOL_NAME",
    "build_attachment_citation_fallback",
    "build_attachment_citation_tool",
    "build_attachment_citations",
    "extract_attachment_citations_from_tool_output",
    "extract_attachment_citations_from_statistics_output",
]
