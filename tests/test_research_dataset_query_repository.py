import copy
import json
import unittest

from pydantic import ValidationError

from domain.models.research_dataset import (
    ExtractedCsvChunk,
    ExtractedCsvRow,
    ExtractedResearchCsv,
    ExtractedResearchXlsx,
    ExtractedXlsxChunk,
    ExtractedXlsxRow,
    ExtractedXlsxSheet,
    ResearchDatasetMaterialization,
    build_research_csv_chunk_payload_sha256,
    build_research_csv_descriptor_sha256,
    build_research_dataset_materialization,
    build_research_xlsx_chunk_payload_sha256,
    build_research_xlsx_descriptor_sha256,
    build_research_xlsx_sheet_descriptor_sha256,
)
from domain.models.research_dataset_query import ResearchDatasetAccessScope
from infrastructure.repositories.research_dataset_query_repository_impl import (
    ResearchDatasetQueryRepositoryImpl,
)


INGESTION_ID = "11111111-1111-5111-8111-111111111111"


class ScriptedDB:
    def __init__(self, rows):
        self.rows = rows
        self.operations = []

    def fetch_all(self, sql, params=None):
        self.operations.append(("fetch_all", sql, params))
        return self.rows


def _scope(processor_type="csv_dataset_v1"):
    return ResearchDatasetAccessScope(
        doctor_id="doctor-1",
        ingestion_id=INGESTION_ID,
        attachment_id="attachment-1",
        document_version=3,
        processor_type=processor_type,
    )


def _csv_materialization():
    rows = (
        ExtractedCsvRow(
            logical_row_number=1,
            physical_row_start=2,
            physical_row_end=2,
            values=("P001", "normal"),
        ),
    )
    chunk_fields = {
        "ordinal": 1,
        "logical_row_start": 1,
        "logical_row_end": 1,
        "physical_row_start": 2,
        "physical_row_end": 2,
        "row_count": 1,
        "non_empty_cell_count": 2,
        "formula_like_cell_count": 0,
        "rows": rows,
    }
    chunk = ExtractedCsvChunk(
        **chunk_fields,
        payload_sha256=build_research_csv_chunk_payload_sha256(**chunk_fields),
    )
    descriptor_fields = {
        "sheet_name": "CSV",
        "headers": ("patient_id", "result"),
        "header_row_start": 1,
        "header_row_end": 1,
        "physical_line_count": 2,
        "record_count": 2,
        "data_row_count": 1,
        "column_count": 2,
        "non_empty_cell_count": 4,
        "formula_like_cell_count": 0,
        "missing_value_counts": (0, 0),
    }
    extracted = ExtractedResearchCsv(
        **descriptor_fields,
        chunks=(chunk,),
        descriptor_sha256=build_research_csv_descriptor_sha256(
            **descriptor_fields
        ),
    )
    return build_research_dataset_materialization(INGESTION_ID, extracted)


def _xlsx_materialization():
    def make_row(logical, values, formulas=()):
        return ExtractedXlsxRow(
            logical_row_number=logical,
            physical_row_start=logical + 1,
            physical_row_end=logical + 1,
            values=values,
            formula_cell_indexes=formulas,
        )

    def make_sheet(ordinal, name, visibility, headers, rows, merged_count=0):
        chunk_fields = {
            "sheet_ordinal": ordinal,
            "ordinal": 1,
            "logical_row_start": 1,
            "logical_row_end": len(rows),
            "physical_row_start": 2,
            "physical_row_end": len(rows) + 1,
            "row_count": len(rows),
            "non_empty_cell_count": sum(
                value != "" for current in rows for value in current.values
            ),
            "formula_like_cell_count": sum(
                value.lstrip().startswith(("=", "+", "-", "@"))
                for current in rows
                for value in current.values
            ),
            "formula_cell_count": sum(
                len(current.formula_cell_indexes) for current in rows
            ),
            "rows": rows,
        }
        chunk = ExtractedXlsxChunk(
            **chunk_fields,
            payload_sha256=build_research_xlsx_chunk_payload_sha256(
                **chunk_fields
            ),
        )
        descriptor_fields = {
            "ordinal": ordinal,
            "name": name,
            "visibility": visibility,
            "headers": headers,
            "header_row_start": 1,
            "header_row_end": 1,
            "physical_line_count": len(rows) + 1,
            "record_count": len(rows) + 1,
            "data_row_count": len(rows),
            "column_count": len(headers),
            "non_empty_cell_count": len(headers) + chunk.non_empty_cell_count,
            "formula_like_cell_count": sum(
                header.lstrip().startswith(("=", "+", "-", "@"))
                for header in headers
            )
            + chunk.formula_like_cell_count,
            "formula_cell_count": chunk.formula_cell_count,
            "merged_range_count": merged_count,
            "missing_value_counts": tuple(
                sum(current.values[column] == "" for current in rows)
                for column in range(len(headers))
            ),
        }
        return ExtractedXlsxSheet(
            **descriptor_fields,
            chunks=(chunk,),
            descriptor_sha256=build_research_xlsx_sheet_descriptor_sha256(
                **descriptor_fields
            ),
        )

    sheets = (
        make_sheet(
            0,
            "Visible",
            "visible",
            ("name", "value"),
            (make_row(1, ("Alice", "=1+1"), (1,)),),
            1,
        ),
        make_sheet(
            2,
            "Hidden",
            "veryHidden",
            ("name", "note"),
            (make_row(1, ("Bob", "")),),
        ),
    )
    workbook_fields = {
        "date_system": "1904",
        "workbook_sheet_count": 3,
        "empty_sheet_count": 1,
        "sheets": sheets,
        "total_record_count": 4,
        "total_data_row_count": 2,
        "total_non_empty_cell_count": 7,
        "total_formula_like_cell_count": 1,
        "total_formula_cell_count": 1,
        "total_merged_range_count": 1,
    }
    extracted = ExtractedResearchXlsx(
        **workbook_fields,
        descriptor_sha256=build_research_xlsx_descriptor_sha256(
            **workbook_fields
        ),
    )
    return build_research_dataset_materialization(INGESTION_ID, extracted)


def _joined_rows(
    materialization: ResearchDatasetMaterialization,
    processor_type: str,
):
    dataset = materialization.dataset
    metadata = materialization.xlsx_metadata
    result = []
    for sheet in materialization.sheets:
        sheet_chunks = [
            chunk
            for chunk in materialization.row_chunks
            if chunk.sheet_id == sheet.id
        ] or [None]
        for chunk in sheet_chunks:
            row = {
                "ingestion_id": INGESTION_ID,
                "ingestion_doctor_id": "doctor-1",
                "ingestion_attachment_id": "attachment-1",
                "ingestion_document_version": 3,
                "ingestion_status": "ready",
                "ingestion_processor_type": processor_type,
                "ingestion_page_count": 0,
                "dataset_id": dataset.id,
                "dataset_ingestion_id": dataset.ingestion_id,
                "dataset_file_type": dataset.file_type,
                "dataset_date_system": (
                    metadata.date_system if metadata is not None else None
                ),
                "dataset_workbook_sheet_count": (
                    metadata.workbook_sheet_count if metadata is not None else None
                ),
                "dataset_empty_sheet_count": (
                    metadata.empty_sheet_count if metadata is not None else None
                ),
                "dataset_total_record_count": (
                    metadata.total_record_count if metadata is not None else None
                ),
                "dataset_sheet_count": dataset.sheet_count,
                "dataset_total_data_row_count": dataset.total_data_row_count,
                "dataset_total_column_count": dataset.total_column_count,
                "dataset_total_non_empty_cell_count": (
                    dataset.total_non_empty_cell_count
                ),
                "dataset_total_formula_like_cell_count": (
                    dataset.total_formula_like_cell_count
                ),
                "dataset_total_formula_cell_count": (
                    dataset.total_formula_cell_count
                ),
                "dataset_total_merged_range_count": (
                    dataset.total_merged_range_count
                ),
                "dataset_descriptor_sha256": dataset.descriptor_sha256,
                "sheet_id": sheet.id,
                "sheet_dataset_id": sheet.dataset_id,
                "sheet_ordinal": sheet.ordinal,
                "sheet_name": sheet.name,
                "sheet_visibility": sheet.visibility,
                "sheet_header_json": json.dumps(
                    list(sheet.headers), ensure_ascii=False
                ),
                "sheet_header_row_start": sheet.header_row_start,
                "sheet_header_row_end": sheet.header_row_end,
                "sheet_physical_line_count": sheet.physical_line_count,
                "sheet_record_count": sheet.record_count,
                "sheet_data_row_count": sheet.data_row_count,
                "sheet_column_count": sheet.column_count,
                "sheet_missing_value_counts_json": json.dumps(
                    list(sheet.missing_value_counts)
                ).encode(),
                "sheet_non_empty_cell_count": sheet.non_empty_cell_count,
                "sheet_formula_like_cell_count": (
                    sheet.formula_like_cell_count
                ),
                "sheet_formula_cell_count": sheet.formula_cell_count,
                "sheet_merged_range_count": sheet.merged_range_count,
                "sheet_descriptor_sha256": sheet.descriptor_sha256,
            }
            if chunk is None:
                row.update(
                    {
                        column: None
                        for column in ResearchDatasetQueryRepositoryImpl._CHUNK_COLUMNS
                    }
                )
            else:
                decoded_rows = [
                    item.model_dump(mode="json") for item in chunk.rows
                ]
                row.update(
                    {
                        "chunk_id": chunk.id,
                        "chunk_sheet_id": chunk.sheet_id,
                        "chunk_ordinal": chunk.ordinal,
                        "chunk_physical_row_start": chunk.physical_row_start,
                        "chunk_physical_row_end": chunk.physical_row_end,
                        "chunk_logical_row_start": chunk.logical_row_start,
                        "chunk_logical_row_end": chunk.logical_row_end,
                        "chunk_row_count": chunk.row_count,
                        "chunk_non_empty_cell_count": (
                            chunk.non_empty_cell_count
                        ),
                        "chunk_formula_like_cell_count": (
                            chunk.formula_like_cell_count
                        ),
                        "chunk_formula_cell_count": chunk.formula_cell_count,
                        "chunk_rows_json": (
                            decoded_rows
                            if dataset.file_type == "csv"
                            else json.dumps(decoded_rows, ensure_ascii=False)
                        ),
                        "chunk_payload_sha256": chunk.payload_sha256,
                    }
                )
            result.append(row)
    return result


class ResearchDatasetAccessScopeTest(unittest.TestCase):
    def test_scope_is_strict_frozen_and_forbids_extra_fields(self):
        scope = _scope()
        with self.assertRaises(ValidationError):
            scope.doctor_id = "changed"
        invalid = (
            scope.model_dump() | {"doctor_id": ""},
            scope.model_dump() | {"doctor_id": "d" * 37},
            scope.model_dump() | {"ingestion_id": "i" * 65},
            scope.model_dump() | {"attachment_id": "a" * 65},
            scope.model_dump() | {"document_version": 0},
            scope.model_dump() | {"document_version": "3"},
            scope.model_dump() | {"processor_type": "pdf_hybrid_v1"},
            scope.model_dump() | {"unexpected": True},
        )
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ResearchDatasetAccessScope.model_validate(payload)


class ResearchDatasetQueryRepositoryTest(unittest.TestCase):
    def test_loads_csv_and_accepts_str_bytes_and_decoded_mysql_json(self):
        expected = _csv_materialization()
        rows = _joined_rows(expected, "csv_dataset_v1")
        db = ScriptedDB(rows)

        actual = ResearchDatasetQueryRepositoryImpl(db=db).load_authorized(
            _scope()
        )

        self.assertEqual(actual, expected)
        self.assertIsInstance(rows[0]["sheet_header_json"], str)
        self.assertIsInstance(rows[0]["sheet_missing_value_counts_json"], bytes)
        self.assertIsInstance(rows[0]["chunk_rows_json"], list)

    def test_loads_multi_sheet_xlsx_with_visibility_formula_and_metadata(self):
        expected = _xlsx_materialization()
        rows = _joined_rows(expected, "xlsx_dataset_v1")
        rows[0]["sheet_header_json"] = rows[0]["sheet_header_json"].encode()
        rows[0]["sheet_missing_value_counts_json"] = [0, 0]

        actual = ResearchDatasetQueryRepositoryImpl(
            db=ScriptedDB(rows)
        ).load_authorized(_scope("xlsx_dataset_v1"))

        self.assertEqual(actual, expected)
        self.assertEqual([sheet.ordinal for sheet in actual.sheets], [0, 2])
        self.assertEqual(actual.sheets[1].visibility, "veryHidden")
        self.assertEqual(actual.xlsx_metadata.date_system, "1904")
        self.assertEqual(
            actual.row_chunks[0].rows[0].formula_cell_indexes,
            (1,),
        )

    def test_query_is_fixed_parameterized_and_exactly_scoped(self):
        db = ScriptedDB([])
        scope = _scope("xlsx_dataset_v1")

        self.assertIsNone(
            ResearchDatasetQueryRepositoryImpl(db=db).load_authorized(scope)
        )

        self.assertEqual(len(db.operations), 1)
        operation, sql, params = db.operations[0]
        self.assertEqual(operation, "fetch_all")
        self.assertEqual(
            params,
            (
                scope.ingestion_id,
                scope.doctor_id,
                scope.attachment_id,
                scope.document_version,
                scope.processor_type,
            ),
        )
        self.assertEqual(sql.count("%s"), 5)
        for predicate in (
            "i.id = %s",
            "i.doctor_id = %s",
            "i.attachment_id = %s",
            "i.document_version = %s",
            "i.status = 'ready'",
            "i.processor_type = %s",
            "ORDER BY s.ordinal ASC, c.ordinal ASC",
        ):
            self.assertIn(predicate, sql)
        self.assertNotIn(scope.doctor_id, sql)
        self.assertNotIn("JSON_", sql.upper())

    def test_cross_doctor_and_non_ready_filters_return_none_when_db_is_empty(self):
        for label in ("cross-doctor", "not-ready"):
            with self.subTest(label=label):
                self.assertIsNone(
                    ResearchDatasetQueryRepositoryImpl(
                        db=ScriptedDB([])
                    ).load_authorized(_scope())
                )

    def test_join_row_outside_scope_or_processor_file_type_mismatch_is_rejected(self):
        base_rows = _joined_rows(_csv_materialization(), "csv_dataset_v1")
        changes = (
            {"ingestion_doctor_id": "doctor-2"},
            {"ingestion_status": "processing"},
            {"ingestion_page_count": 1},
            {"dataset_file_type": "xlsx"},
        )
        for change in changes:
            rows = copy.deepcopy(base_rows)
            rows[0].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(
                ValueError,
                "scope|类型",
            ):
                ResearchDatasetQueryRepositoryImpl(
                    db=ScriptedDB(rows)
                ).load_authorized(_scope())

    def test_rejects_duplicate_keys_nan_non_container_and_extra_row_fields(self):
        base_rows = _joined_rows(_csv_materialization(), "csv_dataset_v1")
        malformed_values = (
            (
                "chunk_rows_json",
                '[{"logical_row_number":1,"logical_row_number":1,'
                '"physical_row_start":2,"physical_row_end":2,'
                '"values":["P001","normal"]}]',
                "duplicate",
            ),
            (
                "chunk_rows_json",
                '[{"logical_row_number":1,"physical_row_start":2,'
                '"physical_row_end":2,"values":[NaN,"normal"]}]',
                "NaN",
            ),
            (
                "chunk_rows_json",
                [
                    {
                        "logical_row_number": 1,
                        "physical_row_start": 2,
                        "physical_row_end": 2,
                        "values": ["P001", float("inf")],
                    }
                ],
                "Infinity",
            ),
            ("sheet_header_json", '{"header":"not-list"}', "顶层"),
            ("chunk_rows_json", '["not-object"]', "object"),
            (
                "chunk_rows_json",
                '[{"logical_row_number":1,"physical_row_start":2,'
                '"physical_row_end":2,"values":["P001","normal"],'
                '"extra":true}]',
                "额外字段",
            ),
        )
        for field, value, message in malformed_values:
            rows = copy.deepcopy(base_rows)
            rows[0][field] = value
            with self.subTest(field=field, message=message), self.assertRaisesRegex(
                ValueError,
                message,
            ):
                ResearchDatasetQueryRepositoryImpl(
                    db=ScriptedDB(rows)
                ).load_authorized(_scope())

    def test_hash_ordinal_and_xlsx_metadata_tampering_fail_closed(self):
        materialization = _xlsx_materialization()
        base_rows = _joined_rows(materialization, "xlsx_dataset_v1")
        changes = (
            ({"chunk_payload_sha256": "0" * 64}, False),
            ({"chunk_ordinal": 2}, False),
            ({"dataset_total_record_count": 999}, True),
            ({"dataset_empty_sheet_count": 0}, True),
        )
        for change, apply_to_all_rows in changes:
            rows = copy.deepcopy(base_rows)
            target_rows = rows if apply_to_all_rows else rows[:1]
            for row in target_rows:
                row.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                ResearchDatasetQueryRepositoryImpl(
                    db=ScriptedDB(rows)
                ).load_authorized(_scope("xlsx_dataset_v1"))

    def test_csv_rejects_any_non_null_xlsx_metadata_column(self):
        base_rows = _joined_rows(_csv_materialization(), "csv_dataset_v1")
        for field, value in (
            ("dataset_date_system", "1900"),
            ("dataset_workbook_sheet_count", 1),
            ("dataset_empty_sheet_count", 0),
            ("dataset_total_record_count", 2),
        ):
            rows = copy.deepcopy(base_rows)
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError,
                "全部为 NULL",
            ):
                ResearchDatasetQueryRepositoryImpl(
                    db=ScriptedDB(rows)
                ).load_authorized(_scope())


if __name__ == "__main__":
    unittest.main()
