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
        candidate = candidate_by_id[segment_id]
        locator = _build_locator(candidate)
        citation = AttachmentCitation(
            source_type="attachment",
            attachment_id=candidate.attachment_id,
            document_version=candidate.document_version,
            segment_id=candidate.segment_id,
            locator=locator,
            excerpt=_normalize_excerpt(candidate.content),
        )
        citations.append(citation.model_dump(mode="json"))
    return citations


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
    if page_start is None and page_end is None:
        return {"type": "file"}
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


def _normalize_excerpt(content: str) -> str:
    return re.sub(r"\s+", " ", content).strip()[
        :MAX_ATTACHMENT_EXCERPT_LENGTH
    ]


__all__ = [
    "AttachmentCitationSelection",
    "CITATION_TOOL_NAME",
    "build_attachment_citation_tool",
    "build_attachment_citations",
    "extract_attachment_citations_from_tool_output",
]
