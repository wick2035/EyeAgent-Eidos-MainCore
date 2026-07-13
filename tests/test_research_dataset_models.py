import re
import unittest
from pathlib import Path

from pydantic import ValidationError

from domain.models.research_dataset import (
    ExtractedCsvChunk,
    ExtractedCsvRow,
    ExtractedResearchCsv,
    ResearchDatasetEntity,
    ResearchDatasetMaterialization,
    build_research_csv_chunk_payload_sha256,
    build_research_csv_descriptor_sha256,
    build_research_dataset_id,
    build_research_dataset_materialization,
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


if __name__ == "__main__":
    unittest.main()
