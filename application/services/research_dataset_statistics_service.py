import copy
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, DecimalException, Inexact, Rounded, localcontext
from typing import Any

from domain.models.research_dataset import (
    ExtractedXlsxRow,
    ResearchDatasetMaterialization,
    ResearchDatasetSheetEntity,
)
from domain.models.research_dataset_query import ResearchDatasetAccessScope


RESEARCH_DATASET_STATS_SCHEMA_VERSION = "research_dataset_statistics_v1"
RESEARCH_DATASET_STATS_OPERATIONS = frozenset(
    {
        "count",
        "numeric_summary",
        "frequency",
        "grouped_numeric_summary",
    }
)
RESEARCH_DATASET_STATS_MIN_GROUP_SIZE = 5
RESEARCH_DATASET_STATS_MAX_GROUPS = 20

_ERROR_CODES = frozenset(
    {
        "RESEARCH_DATASET_STATS_UNAVAILABLE",
        "RESEARCH_DATASET_STATS_REQUEST_INVALID",
        "RESEARCH_DATASET_STATS_OPERATION_UNSUPPORTED",
        "RESEARCH_DATASET_STATS_TYPE_MISMATCH",
        "RESEARCH_DATASET_STATS_PRIVACY_LIMIT",
        "RESEARCH_DATASET_STATS_BUDGET_LIMIT",
        "RESEARCH_DATASET_STATS_FAILED",
    }
)
_NUMERIC_PATTERN = re.compile(
    r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?"
    r"(?:[eE][+-]?(?:0|[1-9][0-9]*))?\Z"
)
_SAFE_LABEL_PUNCTUATION = frozenset("._-/()[]+")
_DECIMAL_ACCUMULATION_PRECISION = 700
_DECIMAL_MEAN_PRECISION = 50


class ResearchDatasetStatisticsError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        if error_code not in _ERROR_CODES:
            raise ValueError("不允许的科研数据统计错误码")
        super().__init__(error_code)
        self.error_code = error_code


class ResearchDatasetStatisticsService:
    def __init__(self, repository: Any) -> None:
        if repository is None or not callable(
            getattr(repository, "load_authorized", None)
        ):
            raise ValueError("dataset query repository 无效")
        self._repository = repository
        self._authorized_materializations: dict[
            int,
            ResearchDatasetMaterialization,
        ] = {}

    def load_authorized(
        self,
        scope: ResearchDatasetAccessScope,
    ) -> ResearchDatasetMaterialization:
        try:
            validated_scope = ResearchDatasetAccessScope.model_validate(
                copy.deepcopy(scope.model_dump(mode="python"))
            )
            loaded = self._repository.load_authorized(validated_scope)
            if loaded is None:
                raise ResearchDatasetStatisticsError(
                    "RESEARCH_DATASET_STATS_UNAVAILABLE"
                )
            materialization = ResearchDatasetMaterialization.model_validate(
                copy.deepcopy(loaded.model_dump(mode="python"))
            )
        except ResearchDatasetStatisticsError:
            raise
        except Exception:
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_FAILED"
            ) from None

        expected_file_type = (
            "csv"
            if validated_scope.processor_type == "csv_dataset_v1"
            else "xlsx"
        )
        if (
            materialization.dataset.ingestion_id
            != validated_scope.ingestion_id
            or materialization.dataset.file_type != expected_file_type
        ):
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_FAILED"
            )
        self._authorized_materializations[id(materialization)] = materialization
        return materialization

    def analyze(
        self,
        materialization: ResearchDatasetMaterialization,
        *,
        sheet_name: str,
        expected_row_start: int,
        expected_row_end: int,
        operation: str,
        value_column_index: int | None,
        group_column_index: int | None,
    ) -> dict[str, Any]:
        if type(operation) is not str:
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_REQUEST_INVALID"
            )
        if operation not in RESEARCH_DATASET_STATS_OPERATIONS:
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_OPERATION_UNSUPPORTED"
            )
        if (
            type(sheet_name) is not str
            or not sheet_name
            or type(expected_row_start) is not int
            or type(expected_row_end) is not int
            or expected_row_start < 1
            or expected_row_end < expected_row_start
        ):
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_REQUEST_INVALID"
            )
        validated = self._authorized_materializations.get(id(materialization))
        if validated is not materialization:
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_UNAVAILABLE"
            )
        sheet = next(
            (item for item in validated.sheets if item.name == sheet_name),
            None,
        )
        if (
            sheet is None
            or sheet.header_row_start != expected_row_start
            or sheet.physical_line_count != expected_row_end
        ):
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_UNAVAILABLE"
            )

        self._validate_operation_columns(
            operation,
            sheet,
            value_column_index,
            group_column_index,
        )
        if operation == "count":
            return self._count(
                validated,
                sheet,
                value_column_index,
            )
        if operation == "numeric_summary":
            return self._numeric_summary(
                validated,
                sheet,
                value_column_index,
            )
        if operation == "frequency":
            return self._frequency(
                validated,
                sheet,
                group_column_index,
            )
        return self._grouped_numeric_summary(
            validated,
            sheet,
            value_column_index,
            group_column_index,
        )

    @staticmethod
    def _validate_operation_columns(
        operation: str,
        sheet: ResearchDatasetSheetEntity,
        value_column_index: int | None,
        group_column_index: int | None,
    ) -> None:
        def valid_optional(value: int | None) -> bool:
            return value is None or (
                type(value) is int and 1 <= value <= sheet.column_count
            )

        if not valid_optional(value_column_index) or not valid_optional(
            group_column_index
        ):
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_REQUEST_INVALID"
            )
        valid = {
            "count": group_column_index is None,
            "numeric_summary": (
                value_column_index is not None and group_column_index is None
            ),
            "frequency": (
                value_column_index is None and group_column_index is not None
            ),
            "grouped_numeric_summary": (
                value_column_index is not None
                and group_column_index is not None
                and value_column_index != group_column_index
            ),
        }
        if not valid[operation]:
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_REQUEST_INVALID"
            )

    def _count(
        self,
        materialization: ResearchDatasetMaterialization,
        sheet: ResearchDatasetSheetEntity,
        value_column_index: int | None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "data_row_count": sheet.data_row_count,
        }
        if value_column_index is None:
            return result
        missing = 0
        formula = 0
        for value, is_formula in self._column_cells(
            materialization,
            sheet,
            value_column_index,
        ):
            missing += value == ""
            formula += is_formula
        result.update(
            {
                "value_column_index": value_column_index,
                "non_missing_count": sheet.data_row_count - missing,
                "missing_count": missing,
                "formula_count": formula,
            }
        )
        return result

    def _numeric_summary(
        self,
        materialization: ResearchDatasetMaterialization,
        sheet: ResearchDatasetSheetEntity,
        value_column_index: int | None,
    ) -> dict[str, Any]:
        assert value_column_index is not None
        summary = _summarize_numeric_cells(
            self._column_cells(
                materialization,
                sheet,
                value_column_index,
            )
        )
        if summary["valid_count"] < RESEARCH_DATASET_STATS_MIN_GROUP_SIZE:
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_PRIVACY_LIMIT"
            )
        return {
            "value_column_index": value_column_index,
            **_public_numeric_summary(summary),
        }

    def _frequency(
        self,
        materialization: ResearchDatasetMaterialization,
        sheet: ResearchDatasetSheetEntity,
        group_column_index: int | None,
    ) -> dict[str, Any]:
        assert group_column_index is not None
        counts: dict[str, int] = defaultdict(int)
        missing_count = 0
        formula_count = 0
        for value, is_formula in self._column_cells(
            materialization,
            sheet,
            group_column_index,
        ):
            if value == "":
                missing_count += 1
            elif is_formula:
                formula_count += 1
            else:
                counts[value] += 1

        visible, suppressed, other = _partition_groups(
            tuple(counts.items())
        )
        if suppressed or not visible:
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_PRIVACY_LIMIT"
            )
        return {
            "group_column_index": group_column_index,
            "groups": [
                {"label": label, "count": count}
                for label, count in visible
            ],
            "missing_count": missing_count,
            "formula_count": formula_count,
            "other_category_count": len(other),
            "other_row_count": sum(count for _, count in other),
        }

    def _grouped_numeric_summary(
        self,
        materialization: ResearchDatasetMaterialization,
        sheet: ResearchDatasetSheetEntity,
        value_column_index: int | None,
        group_column_index: int | None,
    ) -> dict[str, Any]:
        assert value_column_index is not None
        assert group_column_index is not None
        grouped: dict[str, list[tuple[str, bool]]] = defaultdict(list)
        group_missing_count = 0
        group_formula_count = 0
        for group_cell, value_cell in self._paired_column_cells(
            materialization,
            sheet,
            group_column_index,
            value_column_index,
        ):
            group_value, group_formula = group_cell
            if group_value == "":
                group_missing_count += 1
            elif group_formula:
                group_formula_count += 1
            else:
                grouped[group_value].append(value_cell)

        candidates = []
        suppressed = []
        for label, cells in grouped.items():
            numeric = _summarize_numeric_cells(cells)
            item = (label, len(cells), numeric)
            if (
                len(cells) < RESEARCH_DATASET_STATS_MIN_GROUP_SIZE
                or numeric["valid_count"]
                < RESEARCH_DATASET_STATS_MIN_GROUP_SIZE
                or not _safe_group_label(label)
            ):
                suppressed.append(item)
            else:
                candidates.append(item)
        candidates.sort(key=lambda item: (-item[1], item[0]))
        visible = candidates[:RESEARCH_DATASET_STATS_MAX_GROUPS]
        other = candidates[RESEARCH_DATASET_STATS_MAX_GROUPS:]
        if suppressed or not visible:
            raise ResearchDatasetStatisticsError(
                "RESEARCH_DATASET_STATS_PRIVACY_LIMIT"
            )
        return {
            "value_column_index": value_column_index,
            "group_column_index": group_column_index,
            "groups": [
                {
                    "label": label,
                    "row_count": row_count,
                    **_public_numeric_summary(numeric),
                }
                for label, row_count, numeric in visible
            ],
            "group_missing_count": group_missing_count,
            "group_formula_count": group_formula_count,
            "other_category_count": len(other),
            "other_row_count": sum(item[1] for item in other),
        }

    @staticmethod
    def _column_cells(
        materialization: ResearchDatasetMaterialization,
        sheet: ResearchDatasetSheetEntity,
        column_index: int,
    ):
        zero_based = column_index - 1
        for chunk in materialization.row_chunks:
            if chunk.sheet_id != sheet.id:
                continue
            for row in chunk.rows:
                formula_indexes = (
                    row.formula_cell_indexes
                    if isinstance(row, ExtractedXlsxRow)
                    else ()
                )
                yield row.values[zero_based], zero_based in formula_indexes

    @classmethod
    def _paired_column_cells(
        cls,
        materialization: ResearchDatasetMaterialization,
        sheet: ResearchDatasetSheetEntity,
        first_column_index: int,
        second_column_index: int,
    ):
        first = cls._column_cells(
            materialization,
            sheet,
            first_column_index,
        )
        second = cls._column_cells(
            materialization,
            sheet,
            second_column_index,
        )
        yield from zip(first, second)


def _summarize_numeric_cells(
    cells,
) -> dict[str, Any]:
    valid_count = 0
    missing_count = 0
    invalid_count = 0
    formula_count = 0
    try:
        with localcontext() as context:
            context.prec = _DECIMAL_ACCUMULATION_PRECISION
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            total = Decimal(0)
            for value, is_formula in cells:
                if value == "":
                    missing_count += 1
                    continue
                if is_formula:
                    formula_count += 1
                    continue
                numeric = _parse_decimal(value)
                if numeric is None:
                    invalid_count += 1
                    continue
                total += numeric
                valid_count += 1
    except DecimalException:
        raise ResearchDatasetStatisticsError(
            "RESEARCH_DATASET_STATS_FAILED"
        ) from None
    mean = None
    mean_rounded = False
    if valid_count:
        with localcontext() as context:
            context.prec = _DECIMAL_MEAN_PRECISION
            mean = total / Decimal(valid_count)
            mean_rounded = bool(
                context.flags[Inexact] or context.flags[Rounded]
            )
    return {
        "valid_count": valid_count,
        "missing_count": missing_count,
        "invalid_count": invalid_count,
        "formula_count": formula_count,
        "sum": total,
        "mean": mean,
        "mean_rounded": mean_rounded,
    }


def _public_numeric_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid_count": summary["valid_count"],
        "missing_count": summary["missing_count"],
        "invalid_count": summary["invalid_count"],
        "formula_count": summary["formula_count"],
        "sum": _decimal_text(summary["sum"]),
        "mean": _decimal_text(summary["mean"]),
        "sum_exact": True,
        "mean_precision_digits": _DECIMAL_MEAN_PRECISION,
        "mean_rounded": summary["mean_rounded"],
    }


def _parse_decimal(value: str) -> Decimal | None:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 128
        or _NUMERIC_PATTERN.fullmatch(value) is None
    ):
        return None
    exponent_text = value.lower().partition("e")[2]
    if exponent_text and abs(int(exponent_text)) > 308:
        return None
    try:
        parsed = Decimal(value)
    except (DecimalException, ValueError):
        return None
    if not parsed.is_finite() or len(parsed.as_tuple().digits) > 38:
        return None
    if parsed != 0 and abs(parsed.adjusted()) > 308:
        return None
    return parsed


def _decimal_text(value: Decimal | None) -> str:
    if value is None:
        raise ResearchDatasetStatisticsError(
            "RESEARCH_DATASET_STATS_TYPE_MISMATCH"
        )
    if value == 0:
        return "0"
    with localcontext() as context:
        context.prec = _DECIMAL_ACCUMULATION_PRECISION
        normalized = value.normalize()
        if -6 <= normalized.adjusted() <= 20:
            return format(normalized, "f")
        mantissa, exponent = format(normalized, "E").split("E", 1)
    return f"{mantissa}e{int(exponent)}"


def _partition_groups(
    items: tuple[tuple[str, int], ...],
) -> tuple[
    list[tuple[str, int]],
    list[tuple[str, int]],
    list[tuple[str, int]],
]:
    candidates = []
    suppressed = []
    for label, count in items:
        if (
            count < RESEARCH_DATASET_STATS_MIN_GROUP_SIZE
            or not _safe_group_label(label)
        ):
            suppressed.append((label, count))
        else:
            candidates.append((label, count))
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return (
        candidates[:RESEARCH_DATASET_STATS_MAX_GROUPS],
        suppressed,
        candidates[RESEARCH_DATASET_STATS_MAX_GROUPS:],
    )


def _safe_group_label(value: str) -> bool:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 64
        or value.strip() != value
        or not unicodedata.is_normalized("NFC", value)
        or value[0] in "=+-@"
    ):
        return False
    for character in value:
        category = unicodedata.category(character)
        if (
            category.startswith(("L", "N", "M"))
            or category == "Zs"
            or character in _SAFE_LABEL_PUNCTUATION
        ):
            continue
        return False
    return True


__all__ = [
    "RESEARCH_DATASET_STATS_MAX_GROUPS",
    "RESEARCH_DATASET_STATS_MIN_GROUP_SIZE",
    "RESEARCH_DATASET_STATS_OPERATIONS",
    "RESEARCH_DATASET_STATS_SCHEMA_VERSION",
    "ResearchDatasetStatisticsError",
    "ResearchDatasetStatisticsService",
]
