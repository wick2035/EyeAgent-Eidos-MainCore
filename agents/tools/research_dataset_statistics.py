import json
import logging
import threading
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from application.services.research_dataset_statistics_service import (
    RESEARCH_DATASET_STATS_SCHEMA_VERSION,
    ResearchDatasetStatisticsError,
    ResearchDatasetStatisticsService,
)
from application.services.research_document_context_selector import (
    ResearchCitationCandidate,
)
from application.services.research_document_segmenter import (
    validate_csv_structure_summary_content,
    validate_xlsx_structure_summary_content,
)
from domain.models.research_dataset_query import ResearchDatasetAccessScope
from infrastructure.repositories.research_dataset_query_repository_impl import (
    get_research_dataset_query_repository,
)


logger = logging.getLogger(__name__)

_MAX_CALLS_PER_TURN = 4
_MAX_RESULT_BYTES = 8 * 1024


class _ResearchDatasetStatisticsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_segment_id: StrictStr = Field(min_length=1, max_length=64)
    operation: StrictStr = Field(min_length=1, max_length=32)
    value_column_index: StrictInt | None = Field(
        default=None,
        ge=1,
        le=100,
    )
    group_column_index: StrictInt | None = Field(
        default=None,
        ge=1,
        le=100,
    )


@dataclass(frozen=True)
class _BoundDatasetSource:
    scope: ResearchDatasetAccessScope
    sheet_name: str
    row_start: int
    row_end: int


def build_research_dataset_statistics_tool(
    candidates: tuple[ResearchCitationCandidate, ...],
    doctor_id: str,
    *,
    service: ResearchDatasetStatisticsService | None = None,
) -> StructuredTool | None:
    sources = _build_sources(candidates, doctor_id)
    if not sources:
        return None
    statistics_service = service
    cache: dict[tuple[str, str, str, int, str], Any] = {}
    lock = threading.Lock()
    call_count = 0

    def prepared_dataset_statistics(
        source_segment_id: str,
        operation: str,
        value_column_index: int | None = None,
        group_column_index: int | None = None,
    ) -> str:
        """对当前科研回合已授权的数据附件执行固定白名单统计。"""
        nonlocal call_count, statistics_service
        with lock:
            call_count += 1
            if call_count > _MAX_CALLS_PER_TURN:
                return _serialize_error(
                    "RESEARCH_DATASET_STATS_BUDGET_LIMIT"
                )
            source = sources.get(source_segment_id)
            if source is None:
                return _serialize_error(
                    "RESEARCH_DATASET_STATS_REQUEST_INVALID"
                )
            try:
                if statistics_service is None:
                    statistics_service = ResearchDatasetStatisticsService(
                        get_research_dataset_query_repository()
                    )
                cache_key = (
                    source.scope.doctor_id,
                    source.scope.ingestion_id,
                    source.scope.attachment_id,
                    source.scope.document_version,
                    source.scope.processor_type,
                )
                materialization = cache.get(cache_key)
                if materialization is None:
                    materialization = statistics_service.load_authorized(
                        source.scope
                    )
                    cache[cache_key] = materialization
                payload = statistics_service.analyze(
                    materialization,
                    sheet_name=source.sheet_name,
                    expected_row_start=source.row_start,
                    expected_row_end=source.row_end,
                    operation=operation,
                    value_column_index=value_column_index,
                    group_column_index=group_column_index,
                )
                result = {
                    "schema_version": RESEARCH_DATASET_STATS_SCHEMA_VERSION,
                    "ok": True,
                    "source_segment_id": source_segment_id,
                    "operation": operation,
                    "result": payload,
                }
                return _serialize_result(result)
            except ResearchDatasetStatisticsError as error:
                return _serialize_error(error.error_code)
            except Exception as error:
                logger.error(
                    "[ResearchDatasetStats] failed, error_type=%s",
                    type(error).__name__,
                )
                return _serialize_error("RESEARCH_DATASET_STATS_FAILED")

    return StructuredTool.from_function(
        func=prepared_dataset_statistics,
        name="statistical_analysis",
        description=(
            "对本轮上传且已授权的 CSV/XLSX 工作表执行受限统计。"
            "source_segment_id 必须来自当前科研文档上下文；operation 仅允许 "
            "count、numeric_summary、frequency、grouped_numeric_summary；"
            "列使用 1-based index。不得提交原始行、SQL、Python 或表达式。"
            "成功后使用返回的 source_segment_id 调用 "
            "cite_research_document_segments。"
        ),
        args_schema=_ResearchDatasetStatisticsInput,
        handle_validation_error=_serialize_error(
            "RESEARCH_DATASET_STATS_REQUEST_INVALID"
        ),
    )


def _build_sources(
    candidates: tuple[ResearchCitationCandidate, ...],
    doctor_id: str,
) -> dict[str, _BoundDatasetSource]:
    if (
        not isinstance(candidates, tuple)
        or not isinstance(doctor_id, str)
        or not doctor_id
        or doctor_id.strip() != doctor_id
    ):
        raise ValueError("RESEARCH_DATASET_STATS_CAPABILITY_INVALID")
    sources: dict[str, _BoundDatasetSource] = {}
    for candidate in candidates:
        if not isinstance(candidate, ResearchCitationCandidate):
            raise ValueError("RESEARCH_DATASET_STATS_CAPABILITY_INVALID")
        processor_type = _dataset_processor_type(candidate.content)
        if processor_type is None:
            continue
        if (
            not isinstance(candidate.segment_id, str)
            or not candidate.segment_id
            or not isinstance(candidate.ingestion_id, str)
            or not candidate.ingestion_id
            or not isinstance(candidate.attachment_id, str)
            or not candidate.attachment_id
            or type(candidate.document_version) is not int
            or candidate.document_version < 1
            or not isinstance(candidate.sheet_name, str)
            or not candidate.sheet_name
            or type(candidate.row_start) is not int
            or type(candidate.row_end) is not int
            or not 1 <= candidate.row_start <= candidate.row_end <= 50_000
            or candidate.segment_id in sources
        ):
            raise ValueError("RESEARCH_DATASET_STATS_CAPABILITY_INVALID")
        sources[candidate.segment_id] = _BoundDatasetSource(
            scope=ResearchDatasetAccessScope(
                doctor_id=doctor_id,
                ingestion_id=candidate.ingestion_id,
                attachment_id=candidate.attachment_id,
                document_version=candidate.document_version,
                processor_type=processor_type,
            ),
            sheet_name=candidate.sheet_name,
            row_start=candidate.row_start,
            row_end=candidate.row_end,
        )
    return sources


def _dataset_processor_type(content: str) -> str | None:
    try:
        validate_csv_structure_summary_content(content)
        return "csv_dataset_v1"
    except ValueError:
        pass
    try:
        validate_xlsx_structure_summary_content(content)
        return "xlsx_dataset_v1"
    except ValueError:
        return None


def _serialize_error(error_code: str) -> str:
    return _serialize_result(
        {
            "schema_version": RESEARCH_DATASET_STATS_SCHEMA_VERSION,
            "ok": False,
            "error_code": error_code,
        }
    )


def _serialize_result(result: dict[str, Any]) -> str:
    try:
        serialized = json.dumps(
            result,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        serialized = json.dumps(
            {
                "error_code": "RESEARCH_DATASET_STATS_FAILED",
                "ok": False,
                "schema_version": RESEARCH_DATASET_STATS_SCHEMA_VERSION,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    if len(serialized.encode("utf-8")) <= _MAX_RESULT_BYTES:
        return serialized
    return json.dumps(
        {
            "error_code": "RESEARCH_DATASET_STATS_BUDGET_LIMIT",
            "ok": False,
            "schema_version": RESEARCH_DATASET_STATS_SCHEMA_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = ["build_research_dataset_statistics_tool"]
