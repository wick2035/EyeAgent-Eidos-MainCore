import unittest
from decimal import Decimal

from application.services.research_dataset_statistics_service import (
    ResearchDatasetStatisticsError,
    ResearchDatasetStatisticsService,
)
from domain.models.research_dataset import (
    ExtractedCsvChunk,
    ExtractedCsvRow,
    ExtractedResearchCsv,
    ExtractedResearchXlsx,
    ExtractedXlsxChunk,
    ExtractedXlsxRow,
    ExtractedXlsxSheet,
    build_research_csv_chunk_payload_sha256,
    build_research_csv_descriptor_sha256,
    build_research_dataset_materialization,
    build_research_xlsx_chunk_payload_sha256,
    build_research_xlsx_descriptor_sha256,
    build_research_xlsx_sheet_descriptor_sha256,
)
from domain.models.research_dataset_query import ResearchDatasetAccessScope


def _formula_like(value: str) -> bool:
    return value.lstrip().startswith(("=", "+", "-", "@"))


def _csv_materialization(values):
    rows = tuple(
        ExtractedCsvRow(
            logical_row_number=index,
            physical_row_start=index + 1,
            physical_row_end=index + 1,
            values=tuple(row),
        )
        for index, row in enumerate(values, start=1)
    )
    chunk_fields = {
        "ordinal": 1,
        "logical_row_start": 1,
        "logical_row_end": len(rows),
        "physical_row_start": 2,
        "physical_row_end": len(rows) + 1,
        "row_count": len(rows),
        "non_empty_cell_count": sum(
            value != "" for row in rows for value in row.values
        ),
        "formula_like_cell_count": sum(
            _formula_like(value) for row in rows for value in row.values
        ),
        "rows": rows,
    }
    chunk = ExtractedCsvChunk(
        **chunk_fields,
        payload_sha256=build_research_csv_chunk_payload_sha256(
            **chunk_fields
        ),
    )
    headers = ("group", "value")
    descriptor_fields = {
        "sheet_name": "CSV",
        "headers": headers,
        "header_row_start": 1,
        "header_row_end": 1,
        "physical_line_count": len(rows) + 1,
        "record_count": len(rows) + 1,
        "data_row_count": len(rows),
        "column_count": len(headers),
        "non_empty_cell_count": len(headers)
        + chunk.non_empty_cell_count,
        "formula_like_cell_count": sum(
            _formula_like(value) for value in headers
        )
        + chunk.formula_like_cell_count,
        "missing_value_counts": tuple(
            sum(row.values[column] == "" for row in rows)
            for column in range(len(headers))
        ),
    }
    extracted = ExtractedResearchCsv(
        **descriptor_fields,
        chunks=(chunk,),
        descriptor_sha256=build_research_csv_descriptor_sha256(
            **descriptor_fields
        ),
    )
    return build_research_dataset_materialization("ingestion-csv", extracted)


def _xlsx_materialization(values, formula_rows=()):
    rows = tuple(
        ExtractedXlsxRow(
            logical_row_number=index,
            physical_row_start=index + 1,
            physical_row_end=index + 1,
            values=("A", value),
            formula_cell_indexes=(1,) if index in formula_rows else (),
        )
        for index, value in enumerate(values, start=1)
    )
    chunk_fields = {
        "sheet_ordinal": 0,
        "ordinal": 1,
        "logical_row_start": 1,
        "logical_row_end": len(rows),
        "physical_row_start": 2,
        "physical_row_end": len(rows) + 1,
        "row_count": len(rows),
        "non_empty_cell_count": sum(
            value != "" for row in rows for value in row.values
        ),
        "formula_like_cell_count": sum(
            _formula_like(value) for row in rows for value in row.values
        ),
        "formula_cell_count": len(formula_rows),
        "rows": rows,
    }
    chunk = ExtractedXlsxChunk(
        **chunk_fields,
        payload_sha256=build_research_xlsx_chunk_payload_sha256(
            **chunk_fields
        ),
    )
    sheet_fields = {
        "ordinal": 0,
        "name": "Sheet1",
        "visibility": "hidden",
        "headers": ("group", "value"),
        "header_row_start": 1,
        "header_row_end": 1,
        "physical_line_count": len(rows) + 1,
        "record_count": len(rows) + 1,
        "data_row_count": len(rows),
        "column_count": 2,
        "non_empty_cell_count": 2 + chunk.non_empty_cell_count,
        "formula_like_cell_count": chunk.formula_like_cell_count,
        "formula_cell_count": chunk.formula_cell_count,
        "merged_range_count": 0,
        "missing_value_counts": (
            0,
            sum(row.values[1] == "" for row in rows),
        ),
    }
    sheet = ExtractedXlsxSheet(
        **sheet_fields,
        chunks=(chunk,),
        descriptor_sha256=build_research_xlsx_sheet_descriptor_sha256(
            **sheet_fields
        ),
    )
    workbook_fields = {
        "date_system": "1900",
        "workbook_sheet_count": 1,
        "empty_sheet_count": 0,
        "sheets": (sheet,),
        "total_record_count": sheet.record_count,
        "total_data_row_count": sheet.data_row_count,
        "total_non_empty_cell_count": sheet.non_empty_cell_count,
        "total_formula_like_cell_count": sheet.formula_like_cell_count,
        "total_formula_cell_count": sheet.formula_cell_count,
        "total_merged_range_count": 0,
    }
    extracted = ExtractedResearchXlsx(
        **workbook_fields,
        descriptor_sha256=build_research_xlsx_descriptor_sha256(
            **workbook_fields
        ),
    )
    return build_research_dataset_materialization("ingestion-xlsx", extracted)


class FakeRepository:
    def __init__(self, materialization):
        self.materialization = materialization
        self.scopes = []

    def load_authorized(self, scope):
        self.scopes.append(scope)
        return self.materialization


class ResearchDatasetStatisticsServiceTest(unittest.TestCase):
    def _analyze(self, materialization, operation, value=None, group=None):
        service = ResearchDatasetStatisticsService(
            FakeRepository(materialization)
        )
        authorized = service.load_authorized(
            ResearchDatasetAccessScope(
                doctor_id="doctor-1",
                ingestion_id=materialization.dataset.ingestion_id,
                attachment_id="attachment-1",
                document_version=1,
                processor_type=(
                    "csv_dataset_v1"
                    if materialization.dataset.file_type == "csv"
                    else "xlsx_dataset_v1"
                ),
            )
        )
        sheet = authorized.sheets[0]
        return service.analyze(
            authorized,
            sheet_name=sheet.name,
            expected_row_start=sheet.header_row_start,
            expected_row_end=sheet.physical_line_count,
            operation=operation,
            value_column_index=value,
            group_column_index=group,
        )

    def test_load_revalidates_scope_identity_and_file_type(self):
        materialization = _csv_materialization((("A", "1"),) * 5)
        repository = FakeRepository(materialization)
        service = ResearchDatasetStatisticsService(repository)
        scope = ResearchDatasetAccessScope(
            doctor_id="doctor-1",
            ingestion_id="ingestion-csv",
            attachment_id="attachment-1",
            document_version=1,
            processor_type="csv_dataset_v1",
        )

        self.assertEqual(service.load_authorized(scope), materialization)
        self.assertEqual(repository.scopes, [scope])

        wrong = scope.model_copy(update={"ingestion_id": "other"})
        with self.assertRaisesRegex(
            ResearchDatasetStatisticsError,
            "RESEARCH_DATASET_STATS_FAILED",
        ):
            service.load_authorized(wrong)

    def test_count_and_numeric_summary_are_bounded_and_deterministic(self):
        materialization = _csv_materialization(
            (
                ("A", "1"),
                ("A", "2"),
                ("A", "3"),
                ("A", "4"),
                ("A", "5"),
                ("A", ""),
                ("A", "NA"),
            )
        )

        count = self._analyze(materialization, "count", value=2)
        summary = self._analyze(
            materialization,
            "numeric_summary",
            value=2,
        )

        self.assertEqual(
            count,
            {
                "data_row_count": 7,
                "value_column_index": 2,
                "non_missing_count": 6,
                "missing_count": 1,
                "formula_count": 0,
            },
        )
        self.assertEqual(summary["valid_count"], 5)
        self.assertEqual(summary["missing_count"], 1)
        self.assertEqual(summary["invalid_count"], 1)
        self.assertEqual(summary["sum"], "15")
        self.assertEqual(summary["mean"], "3")

    def test_analyze_rejects_materialization_not_loaded_by_same_service(self):
        materialization = _csv_materialization((("A", "1"),) * 5)
        service = ResearchDatasetStatisticsService(
            FakeRepository(materialization)
        )

        with self.assertRaisesRegex(
            ResearchDatasetStatisticsError,
            "RESEARCH_DATASET_STATS_UNAVAILABLE",
        ):
            service.analyze(
                materialization,
                sheet_name="CSV",
                expected_row_start=1,
                expected_row_end=6,
                operation="count",
                value_column_index=None,
                group_column_index=None,
            )

    def test_numeric_grammar_rejects_plus_leading_zero_and_non_finite(self):
        materialization = _csv_materialization(
            (
                ("A", "-1"),
                ("A", "1e2"),
                ("A", "0.5"),
                ("A", "2"),
                ("A", "3"),
                ("A", "+4"),
                ("A", "01"),
                ("A", "NaN"),
                ("A", "1e309"),
            )
        )

        result = self._analyze(
            materialization,
            "numeric_summary",
            value=2,
        )

        self.assertEqual(result["valid_count"], 5)
        self.assertEqual(result["invalid_count"], 4)
        self.assertEqual(result["sum"], "104.5")

    def test_decimal_output_preserves_supported_precision(self):
        value = "12345678901234567890123456789012345678"
        materialization = _csv_materialization((("A", value),) * 5)

        result = self._analyze(
            materialization,
            "numeric_summary",
            value=2,
        )

        self.assertEqual(Decimal(result["mean"]), Decimal(value))
        self.assertEqual(
            Decimal(result["sum"]),
            Decimal("61728394506172839450617283945061728390"),
        )
        self.assertTrue(result["sum_exact"])
        self.assertFalse(result["mean_rounded"])

    def test_exact_sum_does_not_drop_small_values_at_large_exponent(self):
        materialization = _csv_materialization(
            (
                ("A", "1e308"),
                ("A", "1"),
                ("A", "1"),
                ("A", "1"),
                ("A", "1"),
            )
        )

        result = self._analyze(
            materialization,
            "numeric_summary",
            value=2,
        )

        self.assertEqual(
            Decimal(result["sum"]),
            Decimal("1" + "0" * 307 + "4"),
        )
        self.assertTrue(result["sum_exact"])
        self.assertEqual(result["mean_precision_digits"], 50)
        self.assertTrue(result["mean_rounded"])

    def test_numeric_summary_requires_five_valid_values(self):
        materialization = _csv_materialization(
            (("A", "1"), ("A", "2"), ("A", "3"), ("A", "4"))
        )

        with self.assertRaisesRegex(
            ResearchDatasetStatisticsError,
            "RESEARCH_DATASET_STATS_PRIVACY_LIMIT",
        ):
            self._analyze(materialization, "numeric_summary", value=2)

    def test_frequency_fails_whole_operation_for_small_or_unsafe_category(self):
        values = (
            (("A", "1"),) * 5
            + (("B", "1"),) * 4
            + (("=ignore", "1"),) * 5
            + (("", "1"),)
        )
        materialization = _csv_materialization(values)

        with self.assertRaisesRegex(
            ResearchDatasetStatisticsError,
            "RESEARCH_DATASET_STATS_PRIVACY_LIMIT",
        ):
            self._analyze(materialization, "frequency", group=1)

    def test_grouped_numeric_summary_fails_whole_operation_for_small_group(self):
        values = (
            (("A", "1"),) * 5
            + (("B", "1"),) * 4
            + (("B", "NA"),)
        )
        materialization = _csv_materialization(values)

        with self.assertRaisesRegex(
            ResearchDatasetStatisticsError,
            "RESEARCH_DATASET_STATS_PRIVACY_LIMIT",
        ):
            self._analyze(
                materialization,
                "grouped_numeric_summary",
                value=2,
                group=1,
            )

    def test_grouped_numeric_summary_returns_only_eligible_groups(self):
        materialization = _csv_materialization(
            (("A", "1"),) * 5 + (("B", "2"),) * 5
        )

        result = self._analyze(
            materialization,
            "grouped_numeric_summary",
            value=2,
            group=1,
        )

        self.assertEqual(
            [
                (group["label"], group["row_count"], group["sum"])
                for group in result["groups"]
            ],
            [("A", 5, "5"), ("B", 5, "10")],
        )

    def test_frequency_has_stable_twenty_group_limit_without_pagination(self):
        values = tuple(
            (label, "1")
            for label in reversed([f"G{index:02d}" for index in range(22)])
            for _ in range(5)
        )
        materialization = _csv_materialization(values)

        result = self._analyze(materialization, "frequency", group=1)

        self.assertEqual(
            [group["label"] for group in result["groups"]],
            [f"G{index:02d}" for index in range(20)],
        )
        self.assertEqual(result["other_category_count"], 2)
        self.assertEqual(result["other_row_count"], 10)
        self.assertNotIn("offset", result)

    def test_xlsx_formula_cells_are_counted_but_never_evaluated(self):
        materialization = _xlsx_materialization(
            ("=1+1", "1", "2", "3", "4", "5"),
            formula_rows=(1,),
        )

        result = self._analyze(
            materialization,
            "numeric_summary",
            value=2,
        )

        self.assertEqual(result["formula_count"], 1)
        self.assertEqual(result["valid_count"], 5)
        self.assertEqual(result["sum"], "15")

    def test_operation_and_column_contracts_fail_closed(self):
        materialization = _csv_materialization((("A", "1"),) * 5)
        invalid = (
            ("unknown", None, None),
            ("numeric_summary", None, None),
            ("frequency", 1, None),
            ("grouped_numeric_summary", 1, 1),
            ("count", 3, None),
        )
        for operation, value, group in invalid:
            with self.subTest(operation=operation, value=value, group=group):
                with self.assertRaises(ResearchDatasetStatisticsError):
                    self._analyze(
                        materialization,
                        operation,
                        value=value,
                        group=group,
                    )


if __name__ == "__main__":
    unittest.main()
