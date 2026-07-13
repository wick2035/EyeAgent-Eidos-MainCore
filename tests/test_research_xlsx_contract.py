import json
import unittest
from dataclasses import replace

from infrastructure.attachments.research_xlsx_contract import (
    RESEARCH_XLSX_ERROR_CODES,
    ResearchXlsxContractError,
    XlsxDescriptor,
    XlsxRow,
    XlsxSheetDescriptor,
    build_normalized_research_xlsx,
    rebuild_research_xlsx_from_canonical_bytes,
    validate_canonical_research_xlsx_chunk_bytes,
    validate_canonical_research_xlsx_descriptor_bytes,
)


def _normalized_workbook():
    sheets = (
        XlsxSheetDescriptor(
            ordinal=0,
            name="Visible",
            visibility="visible",
            headers=("patient_id", "score"),
            header_row_start=1,
            header_row_end=1,
            physical_line_count=2,
            record_count=2,
            data_row_count=1,
            column_count=2,
            non_empty_cell_count=4,
            formula_like_cell_count=1,
            formula_cell_count=1,
            merged_range_count=0,
            missing_value_counts=(0, 0),
        ),
        XlsxSheetDescriptor(
            ordinal=2,
            name="VeryHidden",
            visibility="veryHidden",
            headers=("value",),
            header_row_start=2,
            header_row_end=2,
            physical_line_count=3,
            record_count=2,
            data_row_count=1,
            column_count=1,
            non_empty_cell_count=2,
            formula_like_cell_count=0,
            formula_cell_count=0,
            merged_range_count=1,
            missing_value_counts=(0,),
        ),
    )
    descriptor = XlsxDescriptor(
        schema_version="research_xlsx_v1",
        date_system="1904",
        workbook_sheet_count=3,
        empty_sheet_count=1,
        sheets=sheets,
        total_record_count=4,
        total_data_row_count=2,
        total_non_empty_cell_count=6,
        total_formula_like_cell_count=1,
        total_formula_cell_count=1,
        total_merged_range_count=1,
    )
    rows = (
        (
            XlsxRow(
                logical_row_number=1,
                physical_row_start=2,
                physical_row_end=2,
                values=("P-1", "=1+1"),
                formula_cell_indexes=(1,),
            ),
        ),
        (
            XlsxRow(
                logical_row_number=1,
                physical_row_start=3,
                physical_row_end=3,
                values=("private",),
                formula_cell_indexes=(),
            ),
        ),
    )
    return build_normalized_research_xlsx(descriptor, rows)


class ResearchXlsxCanonicalContractTest(unittest.TestCase):
    def test_error_allowlist_is_the_frozen_c3_0_contract(self):
        self.assertEqual(
            RESEARCH_XLSX_ERROR_CODES,
            frozenset(
                {
                    "RESEARCH_XLSX_UNAVAILABLE",
                    "RESEARCH_XLSX_SIZE_LIMIT",
                    "RESEARCH_XLSX_INVALID",
                    "RESEARCH_XLSX_ENCRYPTED",
                    "RESEARCH_XLSX_STRUCTURE_LIMIT",
                    "RESEARCH_XLSX_FORMULA_UNSUPPORTED",
                    "RESEARCH_XLSX_CONTENT_LIMIT",
                    "RESEARCH_XLSX_PARSE_FAILED",
                }
            ),
        )

    def test_round_trip_binds_hashes_and_preserves_empty_sheet_ordinal_gap(self):
        normalized = _normalized_workbook()

        rebuilt = rebuild_research_xlsx_from_canonical_bytes(
            normalized.descriptor_canonical_json_bytes,
            normalized.chunk_canonical_json_bytes,
            descriptor_sha256=normalized.descriptor_sha256,
            chunk_sha256s=normalized.chunk_sha256s,
        )

        self.assertEqual(rebuilt, normalized)
        self.assertEqual(
            tuple(sheet.ordinal for sheet in rebuilt.descriptor.sheets),
            (0, 2),
        )
        self.assertEqual(
            tuple(chunk.sheet_ordinal for chunk in rebuilt.chunks),
            (0, 2),
        )

    def test_rebuild_rejects_cross_sheet_chunk_reordering(self):
        normalized = _normalized_workbook()

        with self.assertRaisesRegex(
            ResearchXlsxContractError,
            "RESEARCH_XLSX_INVALID",
        ):
            rebuild_research_xlsx_from_canonical_bytes(
                normalized.descriptor_canonical_json_bytes,
                tuple(reversed(normalized.chunk_canonical_json_bytes)),
            )

    def test_hash_and_noncanonical_json_tampering_are_rejected(self):
        normalized = _normalized_workbook()
        descriptor = normalized.descriptor_canonical_json_bytes

        with self.assertRaises(ResearchXlsxContractError):
            validate_canonical_research_xlsx_descriptor_bytes(
                descriptor,
                expected_sha256="0" * 64,
            )
        with self.assertRaises(ResearchXlsxContractError):
            validate_canonical_research_xlsx_descriptor_bytes(
                descriptor + b"\n",
            )

    def test_chunk_formula_indexes_are_strict_and_bound_to_formula_text(self):
        normalized = _normalized_workbook()
        payload = json.loads(normalized.chunk_canonical_json_bytes[0])
        payload["rows"][0]["formula_cell_indexes"] = [0]
        tampered = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()

        with self.assertRaises(ResearchXlsxContractError):
            validate_canonical_research_xlsx_chunk_bytes(tampered)

    def test_descriptor_rejects_casefold_duplicate_or_control_sheet_names(self):
        normalized = _normalized_workbook()
        first, second = normalized.descriptor.sheets
        duplicate = replace(second, name="visible")
        descriptor = replace(
            normalized.descriptor,
            sheets=(first, duplicate),
        )
        with self.assertRaises(ResearchXlsxContractError):
            descriptor.to_canonical_json_bytes()

        controlled = replace(first, name="Bad\u200bName")
        descriptor = replace(
            normalized.descriptor,
            sheets=(controlled, second),
        )
        with self.assertRaises(ResearchXlsxContractError):
            descriptor.to_canonical_json_bytes()

    def test_descriptor_rejects_unknown_or_duplicate_json_fields(self):
        normalized = _normalized_workbook()
        descriptor = normalized.descriptor_canonical_json_bytes
        decoded = descriptor.decode()
        duplicate = decoded.replace(
            '"schema_version":"research_xlsx_v1",',
            '"schema_version":"research_xlsx_v1",'
            '"schema_version":"research_xlsx_v1",',
            1,
        ).encode()
        with self.assertRaises(ResearchXlsxContractError):
            validate_canonical_research_xlsx_descriptor_bytes(duplicate)

        value = json.loads(descriptor)
        value["raw_rows"] = [["private"]]
        unknown = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        with self.assertRaises(ResearchXlsxContractError):
            validate_canonical_research_xlsx_descriptor_bytes(unknown)


if __name__ == "__main__":
    unittest.main()
