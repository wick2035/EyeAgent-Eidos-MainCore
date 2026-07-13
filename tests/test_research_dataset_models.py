import hashlib
import json
import re
import unittest
from pathlib import Path

from pydantic import ValidationError

from domain.models.research_dataset import (
    ExtractedCsvChunk,
    ExtractedCsvRow,
    ExtractedResearchCsv,
    ExtractedResearchXlsx,
    ExtractedXlsxChunk,
    ExtractedXlsxRow,
    ExtractedXlsxSheet,
    ResearchDatasetEntity,
    ResearchDatasetMaterialization,
    build_research_csv_chunk_payload_sha256,
    build_research_csv_descriptor_sha256,
    build_research_dataset_id,
    build_research_dataset_materialization,
    build_research_xlsx_chunk_payload_sha256,
    build_research_xlsx_descriptor_sha256,
    build_research_xlsx_sheet_descriptor_sha256,
)
from infrastructure.attachments.research_xlsx_contract import (
    XlsxChunk,
    XlsxDescriptor,
    XlsxRow,
    XlsxSheetDescriptor,
)


INGESTION_ID = "11111111-1111-5111-8111-111111111111"


def _row(logical, physical_start, physical_end, values):
    return ExtractedCsvRow(
        logical_row_number=logical,
        physical_row_start=physical_start,
        physical_row_end=physical_end,
        values=values,
    )


def _formula_like(value):
    return value.lstrip().startswith(("=", "+", "-", "@"))


def _chunk(ordinal, rows):
    non_empty = sum(value != "" for row in rows for value in row.values)
    formula_like = sum(
        _formula_like(value) for row in rows for value in row.values
    )
    fields = {
        "ordinal": ordinal,
        "logical_row_start": rows[0].logical_row_number,
        "logical_row_end": rows[-1].logical_row_number,
        "physical_row_start": rows[0].physical_row_start,
        "physical_row_end": rows[-1].physical_row_end,
        "row_count": len(rows),
        "non_empty_cell_count": non_empty,
        "formula_like_cell_count": formula_like,
        "rows": tuple(rows),
    }
    return ExtractedCsvChunk(
        **fields,
        payload_sha256=build_research_csv_chunk_payload_sha256(**fields),
    )


def _extracted():
    headers = ("patient_id", "=result")
    chunks = (
        _chunk(
            1,
            (
                _row(1, 4, 5, ("P1", "normal\ncontinued")),
                _row(2, 6, 6, ("P2", " +SUM(A1:A1)")),
            ),
        ),
        _chunk(2, (_row(3, 7, 8, ("P3", "")),)),
    )
    fields = {
        "sheet_name": "CSV",
        "headers": headers,
        "header_row_start": 2,
        "header_row_end": 3,
        "physical_line_count": 8,
        "record_count": 4,
        "data_row_count": 3,
        "column_count": 2,
        "non_empty_cell_count": 7,
        "formula_like_cell_count": 2,
        "missing_value_counts": (0, 1),
    }
    return ExtractedResearchCsv(
        **fields,
        chunks=chunks,
        descriptor_sha256=build_research_csv_descriptor_sha256(**fields),
    )


def _xlsx_row(logical, physical, values, formula_indexes=()):
    return ExtractedXlsxRow(
        logical_row_number=logical,
        physical_row_start=physical,
        physical_row_end=physical,
        values=values,
        formula_cell_indexes=formula_indexes,
    )


def _xlsx_chunk(sheet_ordinal, ordinal, rows):
    fields = {
        "sheet_ordinal": sheet_ordinal,
        "ordinal": ordinal,
        "logical_row_start": rows[0].logical_row_number,
        "logical_row_end": rows[-1].logical_row_number,
        "physical_row_start": rows[0].physical_row_start,
        "physical_row_end": rows[-1].physical_row_end,
        "row_count": len(rows),
        "non_empty_cell_count": sum(
            value != "" for row in rows for value in row.values
        ),
        "formula_like_cell_count": sum(
            _formula_like(value) for row in rows for value in row.values
        ),
        "formula_cell_count": sum(
            len(row.formula_cell_indexes) for row in rows
        ),
        "rows": tuple(rows),
    }
    return ExtractedXlsxChunk(
        **fields,
        payload_sha256=build_research_xlsx_chunk_payload_sha256(**fields),
    )


def _xlsx_sheet(
    *,
    ordinal,
    name,
    visibility,
    header_row,
    headers,
    rows,
    merged_range_count=0,
):
    chunks = (_xlsx_chunk(ordinal, 1, rows),) if rows else ()
    fields = {
        "ordinal": ordinal,
        "name": name,
        "visibility": visibility,
        "headers": headers,
        "header_row_start": header_row,
        "header_row_end": header_row,
        "physical_line_count": header_row + len(rows),
        "record_count": len(rows) + 1,
        "data_row_count": len(rows),
        "column_count": len(headers),
        "non_empty_cell_count": len(headers)
        + sum(value != "" for row in rows for value in row.values),
        "formula_like_cell_count": sum(
            _formula_like(header) for header in headers
        )
        + sum(_formula_like(value) for row in rows for value in row.values),
        "formula_cell_count": sum(
            len(row.formula_cell_indexes) for row in rows
        ),
        "merged_range_count": merged_range_count,
        "missing_value_counts": tuple(
            sum(row.values[column] == "" for row in rows)
            for column in range(len(headers))
        ),
    }
    return ExtractedXlsxSheet(
        **fields,
        chunks=chunks,
        descriptor_sha256=build_research_xlsx_sheet_descriptor_sha256(**fields),
    )


def _extracted_xlsx():
    sheets = (
        _xlsx_sheet(
            ordinal=0,
            name="Visible",
            visibility="visible",
            header_row=1,
            headers=("patient", "score"),
            rows=(
                _xlsx_row(1, 2, ("Alice", "=A2"), (1,)),
                _xlsx_row(2, 3, ("", "")),
            ),
            merged_range_count=1,
        ),
        _xlsx_sheet(
            ordinal=2,
            name="Hidden",
            visibility="hidden",
            header_row=3,
            headers=("patient", "note"),
            rows=(_xlsx_row(1, 4, ("Bob", "")),),
        ),
    )
    fields = {
        "date_system": "1904",
        "workbook_sheet_count": 3,
        "empty_sheet_count": 1,
        "sheets": sheets,
        "total_record_count": 5,
        "total_data_row_count": 3,
        "total_non_empty_cell_count": 7,
        "total_formula_like_cell_count": 1,
        "total_formula_cell_count": 1,
        "total_merged_range_count": 1,
    }
    return ExtractedResearchXlsx(
        **fields,
        descriptor_sha256=build_research_xlsx_descriptor_sha256(**fields),
    )


class ResearchDatasetModelTest(unittest.TestCase):
    def test_build_materialization_is_stable_related_and_frozen(self):
        extracted = _extracted()

        first = build_research_dataset_materialization(INGESTION_ID, extracted)
        second = build_research_dataset_materialization(INGESTION_ID, extracted)

        self.assertEqual(first, second)
        self.assertEqual(first.dataset.id, build_research_dataset_id(INGESTION_ID))
        self.assertEqual(first.dataset.file_type, "csv")
        self.assertEqual(first.dataset.sheet_count, 1)
        self.assertEqual(first.dataset.total_data_row_count, 3)
        self.assertEqual(first.dataset.total_column_count, 2)
        self.assertEqual(first.dataset.total_non_empty_cell_count, 7)
        self.assertEqual(first.dataset.total_formula_like_cell_count, 2)
        self.assertEqual(first.sheets[0].name, "CSV")
        self.assertEqual(first.sheets[0].header_row_start, 2)
        self.assertEqual(first.sheets[0].header_row_end, 3)
        self.assertEqual(first.sheets[0].physical_line_count, 8)
        self.assertEqual(first.sheets[0].data_row_count, 3)
        self.assertEqual(first.sheets[0].dataset_id, first.dataset.id)
        self.assertEqual(
            [chunk.ordinal for chunk in first.row_chunks],
            [1, 2],
        )
        self.assertEqual(
            (first.row_chunks[0].physical_row_start,
             first.row_chunks[0].physical_row_end),
            (4, 6),
        )
        self.assertTrue(
            all(chunk.sheet_id == first.sheets[0].id for chunk in first.row_chunks)
        )
        with self.assertRaises(ValidationError):
            first.dataset.file_type = "xlsx"

    def test_quoted_multiline_rows_use_physical_ranges_and_data_logical_rows(self):
        extracted = _extracted()
        rows = tuple(row for chunk in extracted.chunks for row in chunk.rows)

        self.assertEqual([row.logical_row_number for row in rows], [1, 2, 3])
        self.assertEqual(
            [(row.physical_row_start, row.physical_row_end) for row in rows],
            [(4, 5), (6, 6), (7, 8)],
        )
        invalid = rows[0].model_dump() | {"physical_row_end": 3}
        with self.assertRaisesRegex(ValidationError, "不能小于"):
            ExtractedCsvRow(**invalid)
        with self.assertRaises(ValidationError):
            ExtractedCsvRow(**(rows[0].model_dump() | {"values": ("P1", 3)}))

    def test_rejects_header_gap_chunk_gap_bad_ordinals_and_rectangles(self):
        extracted = _extracted()
        base = extracted.model_dump()

        invalid_updates = (
            {
                "chunks": (
                    extracted.chunks[0].model_copy(
                        update={"physical_row_start": 5}
                    ),
                    extracted.chunks[1],
                )
            },
            {
                "chunks": (
                    extracted.chunks[0],
                    extracted.chunks[1].model_copy(
                        update={"physical_row_start": 8}
                    ),
                )
            },
            {
                "chunks": (
                    extracted.chunks[0],
                    extracted.chunks[1].model_copy(update={"ordinal": 3}),
                )
            },
            {
                "chunks": (
                    extracted.chunks[0],
                    extracted.chunks[1].model_copy(
                        update={
                            "rows": (
                                extracted.chunks[1].rows[0].model_copy(
                                    update={"values": ("P3",)}
                                ),
                            )
                        }
                    ),
                )
            },
        )
        for update in invalid_updates:
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ExtractedResearchCsv(**(base | update))

    def test_recomputes_header_inclusive_counts_missing_and_hashes(self):
        extracted = _extracted()
        base = extracted.model_dump()

        invalid_updates = (
            {"headers": ("patient_id", "patient_id")},
            {"headers": ("patient_id", "   ")},
            {"record_count": 3},
            {"data_row_count": 2},
            {"missing_value_counts": (0, 0)},
            {"missing_value_counts": (0,)},
            {"non_empty_cell_count": 5},
            {"formula_like_cell_count": 1},
            {"descriptor_sha256": "0" * 64},
        )
        for update in invalid_updates:
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ExtractedResearchCsv(**(base | update))

        chunk = extracted.chunks[0]
        chunk_updates = (
            {"non_empty_cell_count": 3},
            {"formula_like_cell_count": 0},
            {"payload_sha256": "f" * 64},
        )
        for update in chunk_updates:
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ExtractedCsvChunk(**(chunk.model_dump() | update))

    def test_csv_sheet_is_fixed_but_persistence_type_allows_xlsx(self):
        base = _extracted().model_dump()
        with self.assertRaises(ValidationError):
            ExtractedResearchCsv(**(base | {"sheet_name": "Sheet1"}))

        entity = ResearchDatasetEntity(
            id=build_research_dataset_id(INGESTION_ID),
            ingestion_id=INGESTION_ID,
            file_type="xlsx",
            sheet_count=2,
            total_data_row_count=0,
            total_column_count=2,
            total_non_empty_cell_count=2,
            total_formula_like_cell_count=0,
            descriptor_sha256="a" * 64,
        )
        self.assertEqual(entity.file_type, "xlsx")

    def test_materialization_rechecks_dataset_totals_and_relationships(self):
        materialization = build_research_dataset_materialization(
            INGESTION_ID,
            _extracted(),
        )
        wrong_total = materialization.dataset.model_copy(
            update={"total_data_row_count": 4}
        )
        with self.assertRaisesRegex(ValidationError, "data row total"):
            ResearchDatasetMaterialization(
                dataset=wrong_total,
                sheets=materialization.sheets,
                row_chunks=materialization.row_chunks,
            )

        foreign_chunk = materialization.row_chunks[0].model_copy(
            update={"sheet_id": "foreign-sheet"}
        )
        with self.assertRaisesRegex(ValidationError, "row chunk id"):
            ResearchDatasetMaterialization(
                dataset=materialization.dataset,
                sheets=materialization.sheets,
                row_chunks=(foreign_chunk, materialization.row_chunks[1]),
            )

    def test_xlsx_materialization_preserves_workbook_ordinals_and_security_counts(self):
        extracted = _extracted_xlsx()

        first = build_research_dataset_materialization(INGESTION_ID, extracted)
        second = build_research_dataset_materialization(INGESTION_ID, extracted)

        self.assertEqual(first, second)
        self.assertEqual(first.dataset.file_type, "xlsx")
        self.assertEqual(first.dataset.sheet_count, 2)
        self.assertEqual(first.dataset.total_data_row_count, 3)
        self.assertEqual(first.dataset.total_formula_cell_count, 1)
        self.assertEqual(first.dataset.total_merged_range_count, 1)
        self.assertEqual([sheet.ordinal for sheet in first.sheets], [0, 2])
        self.assertEqual(
            [sheet.visibility for sheet in first.sheets],
            ["visible", "hidden"],
        )
        self.assertEqual(first.xlsx_metadata.date_system, "1904")
        self.assertEqual(first.xlsx_metadata.empty_sheet_count, 1)
        self.assertEqual(
            first.row_chunks[0].rows[0].formula_cell_indexes,
            (1,),
        )
        self.assertEqual(
            [chunk.schema_version for chunk in first.row_chunks],
            ["research_xlsx_chunk_v1", "research_xlsx_chunk_v1"],
        )

    def test_xlsx_hash_builders_match_parser_contract_bytes(self):
        extracted = _extracted_xlsx()
        extracted_sheet = extracted.sheets[0]
        extracted_chunk = extracted_sheet.chunks[0]
        contract_rows = tuple(
            XlsxRow(**row.model_dump()) for row in extracted_chunk.rows
        )
        contract_chunk = XlsxChunk(
            schema_version=extracted_chunk.schema_version,
            sheet_ordinal=extracted_chunk.sheet_ordinal,
            ordinal=extracted_chunk.ordinal,
            logical_row_start=extracted_chunk.logical_row_start,
            logical_row_end=extracted_chunk.logical_row_end,
            physical_row_start=extracted_chunk.physical_row_start,
            physical_row_end=extracted_chunk.physical_row_end,
            row_count=extracted_chunk.row_count,
            non_empty_cell_count=extracted_chunk.non_empty_cell_count,
            formula_like_cell_count=extracted_chunk.formula_like_cell_count,
            formula_cell_count=extracted_chunk.formula_cell_count,
            rows=contract_rows,
        )
        contract_sheets = tuple(
            XlsxSheetDescriptor(
                **sheet.model_dump(
                    exclude={"chunks", "descriptor_sha256"}
                )
            )
            for sheet in extracted.sheets
        )
        contract_descriptor = XlsxDescriptor(
            schema_version=extracted.schema_version,
            date_system=extracted.date_system,
            workbook_sheet_count=extracted.workbook_sheet_count,
            empty_sheet_count=extracted.empty_sheet_count,
            sheets=contract_sheets,
            total_record_count=extracted.total_record_count,
            total_data_row_count=extracted.total_data_row_count,
            total_non_empty_cell_count=extracted.total_non_empty_cell_count,
            total_formula_like_cell_count=extracted.total_formula_like_cell_count,
            total_formula_cell_count=extracted.total_formula_cell_count,
            total_merged_range_count=extracted.total_merged_range_count,
        )

        self.assertEqual(extracted_chunk.payload_sha256, contract_chunk.sha256)
        sheet_bytes = json.dumps(
            contract_sheets[0].to_json_value(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(
            extracted_sheet.descriptor_sha256,
            hashlib.sha256(sheet_bytes).hexdigest(),
        )
        self.assertEqual(extracted.descriptor_sha256, contract_descriptor.sha256)

    def test_xlsx_rejects_formula_hash_descriptor_and_aggregate_tampering(self):
        extracted = _extracted_xlsx()
        first_sheet = extracted.sheets[0]
        first_chunk = first_sheet.chunks[0]

        invalid_row_fields = (
            {"physical_row_end": 3},
            {"formula_cell_indexes": (0, 0)},
            {"formula_cell_indexes": (0,)},
            {"formula_cell_indexes": (2,)},
        )
        for update in invalid_row_fields:
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ExtractedXlsxRow(**(first_chunk.rows[0].model_dump() | update))

        with self.assertRaisesRegex(ValidationError, "payload_sha256"):
            ExtractedXlsxChunk(
                **(first_chunk.model_dump() | {"payload_sha256": "0" * 64})
            )
        with self.assertRaisesRegex(ValidationError, "descriptor_sha256"):
            ExtractedXlsxSheet(
                **(first_sheet.model_dump() | {"descriptor_sha256": "0" * 64})
            )
        for update in (
            {"total_formula_cell_count": 0},
            {"total_merged_range_count": 0},
            {"descriptor_sha256": "0" * 64},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ExtractedResearchXlsx(**(extracted.model_dump() | update))

    def test_xlsx_rejects_non_dense_rows_and_casefold_duplicate_sheet_names(self):
        extracted = _extracted_xlsx()
        first_sheet = extracted.sheets[0]
        second_row = first_sheet.chunks[0].rows[1]
        gapped_row = second_row.model_copy(
            update={"physical_row_start": 4, "physical_row_end": 4}
        )
        with self.assertRaisesRegex(ValidationError, "physical_row|physical row"):
            ExtractedXlsxChunk(
                **(
                    first_sheet.chunks[0].model_dump()
                    | {"rows": (first_sheet.chunks[0].rows[0], gapped_row)}
                )
            )

        duplicate_name_sheet = _xlsx_sheet(
            ordinal=2,
            name="visible",
            visibility="hidden",
            header_row=3,
            headers=("patient", "note"),
            rows=(_xlsx_row(1, 4, ("Bob", "")),),
        )
        with self.assertRaisesRegex(ValidationError, "casefold"):
            ExtractedResearchXlsx(
                **(
                    extracted.model_dump()
                    | {"sheets": (extracted.sheets[0], duplicate_name_sheet)}
                )
            )
        with self.assertRaisesRegex(ValidationError, "控制字符"):
            ExtractedXlsxSheet(
                **(first_sheet.model_dump() | {"name": "bad\nname"})
            )
        with self.assertRaises(ValidationError):
            ExtractedXlsxSheet(
                **(first_sheet.model_dump() | {"name": "x" * 32})
            )

    def test_xlsx_enforces_shared_workbook_and_sheet_budgets(self):
        extracted = _extracted_xlsx()
        for update in (
            {"workbook_sheet_count": 11},
            {"total_data_row_count": 50_001},
            {"total_non_empty_cell_count": 2_000_001},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ExtractedResearchXlsx(**(extracted.model_dump() | update))

        first_sheet = extracted.sheets[0]
        with self.assertRaises(ValidationError):
            ExtractedXlsxSheet(
                **(
                    first_sheet.model_dump()
                    | {"headers": tuple(f"column-{index}" for index in range(101))}
                )
            )

    def test_csv_materialization_keeps_c3_1_hash_identity_and_xlsx_defaults(self):
        extracted = _extracted()
        materialization = build_research_dataset_materialization(
            INGESTION_ID,
            extracted,
        )

        self.assertEqual(
            materialization.dataset.descriptor_sha256,
            extracted.descriptor_sha256,
        )
        self.assertEqual(
            extracted.descriptor_sha256,
            "b867a8cc14dffc8dcc5bc3482deba6d32bb2b68776431fb39d473f7871221954",
        )
        self.assertEqual(
            materialization.dataset.id,
            "944d95a6-bccd-528b-b4a5-79f049a501f5",
        )
        self.assertEqual(
            materialization.sheets[0].id,
            "92fd7683-7d7e-544e-ba71-c9ef76f9d936",
        )
        self.assertEqual(
            [chunk.id for chunk in materialization.row_chunks],
            [
                "c3a33f0d-a180-5977-98bd-7d8bcbe28b1b",
                "37b37e55-8ddd-5a1f-a7de-f5feb242d565",
            ],
        )
        self.assertEqual(materialization.dataset.total_formula_cell_count, 0)
        self.assertEqual(materialization.dataset.total_merged_range_count, 0)
        self.assertEqual(materialization.sheets[0].visibility, "visible")
        self.assertEqual(materialization.sheets[0].formula_cell_count, 0)
        self.assertEqual(materialization.sheets[0].merged_range_count, 0)
        self.assertIsNone(materialization.xlsx_metadata)


class ResearchDatasetDdlTest(unittest.TestCase):
    def test_three_level_schema_has_json_hash_ordinals_and_cascades(self):
        sql = (
            Path(__file__).parents[1]
            / "scripts"
            / "create_research_document_tables.sql"
        ).read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", sql.lower())

        for table in (
            "research_dataset",
            "research_dataset_sheet",
            "research_dataset_row_chunk",
        ):
            self.assertIn(f"create table if not exists {table}", normalized)
        for json_column in (
            "header_json json not null",
            "missing_value_counts_json json not null",
            "rows_json json not null",
        ):
            self.assertIn(json_column, normalized)
        for column in (
            "header_row_start int unsigned not null",
            "header_row_end int unsigned not null",
            "physical_line_count int unsigned not null",
            "data_row_count int unsigned not null",
            "formula_like_cell_count bigint unsigned not null",
            "descriptor_sha256 char(64) not null",
            "payload_sha256 char(64) not null",
        ):
            self.assertIn(column, normalized)
        self.assertIn("(dataset_id, ordinal)", normalized)
        self.assertIn("(sheet_id, ordinal)", normalized)
        self.assertEqual(normalized.count("on delete cascade"), 4)
        self.assertGreaterEqual(normalized.count("engine=innodb"), 5)
        self.assertGreaterEqual(normalized.count("charset=utf8mb4"), 5)

    def test_c3_2_schema_and_upgrade_are_replayable_and_binary_sheet_names(self):
        scripts = Path(__file__).parents[1] / "scripts"
        create_sql = (scripts / "create_research_document_tables.sql").read_text(
            encoding="utf-8"
        )
        upgrade_sql = (scripts / "upgrade_research_dataset_c3_2.sql").read_text(
            encoding="utf-8"
        )
        normalized_create = re.sub(r"\s+", " ", create_sql.lower())
        normalized_upgrade = re.sub(r"\s+", " ", upgrade_sql.lower())

        for column in (
            "date_system varchar(4) null",
            "workbook_sheet_count smallint unsigned null",
            "empty_sheet_count smallint unsigned null",
            "total_record_count int unsigned null",
            "total_formula_cell_count bigint unsigned not null",
            "total_merged_range_count bigint unsigned not null",
            "visibility varchar(16) not null",
            "formula_cell_count bigint unsigned not null",
            "merged_range_count bigint unsigned not null",
        ):
            self.assertIn(column, normalized_create)
        self.assertIn("collate utf8mb4_bin", normalized_create)
        self.assertIn("information_schema.columns", normalized_upgrade)
        self.assertIn("character_set_name <> 'utf8mb4'", normalized_upgrade)
        self.assertIn("collation_name <> 'utf8mb4_bin'", normalized_upgrade)
        self.assertIn("create procedure upgrade_research_dataset_c3_2", normalized_upgrade)
        self.assertIn("call upgrade_research_dataset_c3_2()", normalized_upgrade)
        self.assertIn("collate utf8mb4_bin", normalized_upgrade)
        for column in (
            "date_system",
            "workbook_sheet_count",
            "empty_sheet_count",
            "total_record_count",
            "total_formula_cell_count",
            "total_merged_range_count",
            "visibility",
            "formula_cell_count",
            "merged_range_count",
        ):
            self.assertIn(f"column_name = '{column}'", normalized_upgrade)


if __name__ == "__main__":
    unittest.main()
