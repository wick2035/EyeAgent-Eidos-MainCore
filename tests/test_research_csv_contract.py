import dataclasses
import hashlib
import json
import unittest
from unittest import mock

from infrastructure.attachments import research_csv_contract as contract
from infrastructure.attachments.research_csv_contract import (
    CsvChunk,
    CsvDescriptor,
    CsvRow,
    RESEARCH_CSV_ERROR_CODES,
    ResearchCsvContractError,
    parse_research_csv_bytes,
    rebuild_research_csv_from_canonical_bytes,
    validate_canonical_research_csv_chunk_bytes,
    validate_canonical_research_csv_descriptor_bytes,
)


class ResearchCsvContractTest(unittest.TestCase):
    def test_parses_bom_nfc_leading_empty_records_and_multiline_rows(self):
        result = parse_research_csv_bytes(
            b'\xef\xbb\xbf\r\n  Cafe\xcc\x81  ,Value\r\nAlice,"first\r\nsecond"\r\nBob,\r\n'
        )

        self.assertEqual(result.descriptor.headers, ("Caf\u00e9", "Value"))
        self.assertEqual(result.descriptor.header_row_start, 2)
        self.assertEqual(result.descriptor.header_row_end, 2)
        self.assertEqual(result.descriptor.physical_line_count, 5)
        self.assertEqual(result.descriptor.record_count, 3)
        self.assertEqual(result.descriptor.data_row_count, 2)
        self.assertEqual(result.descriptor.missing_value_counts, (0, 1))
        self.assertEqual(result.rows[0].logical_row_number, 1)
        self.assertEqual(
            (result.rows[0].physical_row_start, result.rows[0].physical_row_end),
            (3, 4),
        )
        self.assertEqual(result.rows[0].values, ("Alice", "first\nsecond"))
        self.assertEqual(
            (result.rows[1].physical_row_start, result.rows[1].physical_row_end),
            (5, 5),
        )

    def test_counts_header_and_data_formula_like_cells_without_rewriting(self):
        result = parse_research_csv_bytes(
            b"=Header,Normal\n  +data,-other\n@value, plain"
        )

        self.assertEqual(result.descriptor.non_empty_cell_count, 6)
        self.assertEqual(result.descriptor.formula_like_cell_count, 4)
        self.assertEqual(result.chunks[0].non_empty_cell_count, 4)
        self.assertEqual(result.chunks[0].formula_like_cell_count, 3)
        self.assertEqual(result.rows[0].values[0], "  +data")

    def test_header_is_trimmed_nonempty_and_case_sensitive_unique(self):
        result = parse_research_csv_bytes(b" Name ,name\nA,B")
        self.assertEqual(result.descriptor.headers, ("Name", "name"))

        for raw in (b"A,A\n1,2", b"A, \n1,2"):
            with self.subTest(raw=raw):
                self._assert_error(raw, "RESEARCH_CSV_INVALID")

    def test_descriptor_above_legacy_64_kib_stays_within_canonical_budget(self):
        header = "H" + ("x" * 70_000)
        result = parse_research_csv_bytes((header + "\nvalue").encode("utf-8"))

        self.assertGreater(len(result.descriptor_canonical_json_bytes), 64 * 1024)
        self.assertLessEqual(
            len(result.descriptor_canonical_json_bytes),
            contract.MAX_RESEARCH_CSV_DESCRIPTOR_BYTES,
        )

    def test_requires_rectangular_records_after_header(self):
        for raw in (b"A,B\n1", b"A,B\n1,2,3", b"A,B\n\n"):
            with self.subTest(raw=raw):
                self._assert_error(raw, "RESEARCH_CSV_INVALID")

    def test_rejects_empty_non_bytes_utf16_invalid_utf8_and_nul(self):
        for raw in (b"", None, bytearray(b"A\n1")):
            with self.subTest(raw=raw):
                self._assert_error(raw, "RESEARCH_CSV_INVALID")
        for raw in (b"\xff\xfeA\x00", b"\xfe\xff\x00A", b"A\xff"):
            with self.subTest(raw=raw):
                self._assert_error(raw, "RESEARCH_CSV_ENCODING_UNSUPPORTED")
        self._assert_error(b"A\nvalue\x00", "RESEARCH_CSV_INVALID")

    def test_rejects_non_rfc4180_quote_syntax_as_invalid_input(self):
        for raw in (b'A\n"unterminated', b'A\nabc"def', b'A\n"abc"tail'):
            with self.subTest(raw=raw):
                self._assert_error(raw, "RESEARCH_CSV_INVALID")
        with mock.patch.object(
            contract,
            "_normalize_cell",
            side_effect=RuntimeError("private parser detail"),
        ):
            self._assert_error(b"A\n1", "RESEARCH_CSV_PARSE_FAILED")

    def test_enforces_size_structure_and_content_limits(self):
        with mock.patch.object(contract, "MAX_RESEARCH_CSV_BYTES", 3):
            self._assert_error(b"A\n12", "RESEARCH_CSV_SIZE_LIMIT")
        with mock.patch.object(contract, "MAX_RESEARCH_CSV_PHYSICAL_LINES", 2):
            self._assert_error(b"A\n1\n2", "RESEARCH_CSV_STRUCTURE_LIMIT")
        with mock.patch.object(contract, "MAX_RESEARCH_CSV_RECORDS", 2):
            self._assert_error(b"\nA\n1", "RESEARCH_CSV_STRUCTURE_LIMIT")
        with mock.patch.object(contract, "MAX_RESEARCH_CSV_COLUMNS", 1):
            self._assert_error(b"A,B\n1,2", "RESEARCH_CSV_STRUCTURE_LIMIT")
        with mock.patch.object(contract, "MAX_RESEARCH_CSV_NON_EMPTY_CELLS", 2):
            self._assert_error(b"A,B\n1,", "RESEARCH_CSV_CONTENT_LIMIT")
        with mock.patch.object(contract, "MAX_RESEARCH_CSV_DESCRIPTOR_BYTES", 8):
            self._assert_error(b"A\n1", "RESEARCH_CSV_CONTENT_LIMIT")
        with mock.patch.object(contract, "MAX_RESEARCH_CSV_CHUNK_BYTES", 8):
            self._assert_error(b"A\n1", "RESEARCH_CSV_CONTENT_LIMIT")
        with mock.patch.object(contract, "MAX_RESEARCH_CSV_CANONICAL_BYTES", 8):
            self._assert_error(b"A\n1", "RESEARCH_CSV_CONTENT_LIMIT")

    def test_chunks_at_500_records_and_256_kib_target(self):
        many_rows = b"A\n" + b"x\n" * 501
        result = parse_research_csv_bytes(many_rows)
        self.assertEqual([chunk.row_count for chunk in result.chunks], [500, 1])
        self.assertEqual([chunk.ordinal for chunk in result.chunks], [1, 2])

        large_cell = "x" * 140_000
        result = parse_research_csv_bytes(
            f"A\n{large_cell}\n{large_cell}".encode("utf-8")
        )
        self.assertEqual([chunk.row_count for chunk in result.chunks], [1, 1])

    def test_header_only_csv_has_no_chunks(self):
        result = parse_research_csv_bytes(b"A,B")
        self.assertEqual(result.rows, ())
        self.assertEqual(result.chunks, ())
        self.assertEqual(result.descriptor.record_count, 1)
        self.assertEqual(result.descriptor.non_empty_cell_count, 2)

    def test_descriptor_and_chunk_emit_exact_canonical_json_and_hash(self):
        result = parse_research_csv_bytes(b"A,B\n1,")
        expected_descriptor = (
            b'{"schema_version":"research_csv_v1","sheet_name":"CSV",'
            b'"headers":["A","B"],"header_row_start":1,"header_row_end":1,'
            b'"physical_line_count":2,"record_count":2,"data_row_count":1,'
            b'"column_count":2,"non_empty_cell_count":3,'
            b'"formula_like_cell_count":0,"missing_value_counts":[0,1]}'
        )
        self.assertEqual(result.descriptor.canonical_json_bytes, expected_descriptor)
        self.assertEqual(
            result.descriptor.sha256,
            hashlib.sha256(expected_descriptor).hexdigest(),
        )
        expected_chunk = (
            b'{"schema_version":"research_csv_chunk_v1","ordinal":1,'
            b'"logical_row_start":1,"logical_row_end":1,'
            b'"physical_row_start":2,"physical_row_end":2,"row_count":1,'
            b'"non_empty_cell_count":1,"formula_like_cell_count":0,"rows":'
            b'[{"logical_row_number":1,"physical_row_start":2,'
            b'"physical_row_end":2,"values":["1",""]}]}'
        )
        self.assertEqual(result.chunks[0].canonical_json_bytes, expected_chunk)
        self.assertEqual(
            result.chunks[0].sha256,
            hashlib.sha256(expected_chunk).hexdigest(),
        )

    def test_canonical_round_trip_with_hash_validation(self):
        original = parse_research_csv_bytes(b"A,B\n1,2\n3,")

        rebuilt = rebuild_research_csv_from_canonical_bytes(
            original.descriptor.canonical_json_bytes,
            original.chunk_canonical_json_bytes,
            descriptor_sha256=original.descriptor_sha256,
            chunk_sha256s=original.chunk_sha256s,
        )

        self.assertEqual(rebuilt, original)
        self.assertEqual(
            validate_canonical_research_csv_descriptor_bytes(
                original.descriptor.canonical_json_bytes,
                expected_sha256=original.descriptor.sha256,
            ),
            original.descriptor,
        )
        self.assertEqual(
            validate_canonical_research_csv_chunk_bytes(
                original.chunks[0].canonical_json_bytes,
                expected_sha256=original.chunks[0].sha256,
            ),
            original.chunks[0],
        )

    def test_rejects_noncanonical_extra_fields_and_hash_drift(self):
        result = parse_research_csv_bytes(b"A\n1")
        canonical = result.descriptor.canonical_json_bytes
        variants = (
            canonical + b"\n",
            canonical.replace(b'{', b'{"extra":1,', 1),
            canonical.replace(b'"sheet_name":"CSV"', b'"sheet_name": "CSV"'),
        )
        for content in variants:
            with self.subTest(content=content):
                self._assert_canonical_error(
                    lambda: validate_canonical_research_csv_descriptor_bytes(content)
                )
        self._assert_canonical_error(
            lambda: validate_canonical_research_csv_descriptor_bytes(
                canonical,
                expected_sha256="0" * 64,
            )
        )

    def test_rebuild_rejects_count_and_continuity_drift(self):
        result = parse_research_csv_bytes(b"A\n1\n2")
        descriptor_value = json.loads(result.descriptor.canonical_json_bytes)
        descriptor_value["data_row_count"] = 3
        drifted_descriptor = self._canonical_json(descriptor_value)
        self._assert_canonical_error(
            lambda: rebuild_research_csv_from_canonical_bytes(
                drifted_descriptor,
                result.chunk_canonical_json_bytes,
            )
        )

        chunk_value = json.loads(result.chunks[0].canonical_json_bytes)
        chunk_value["logical_row_start"] = 2
        chunk_value["logical_row_end"] = 3
        for row in chunk_value["rows"]:
            row["logical_row_number"] += 1
        drifted_chunk = self._canonical_json(chunk_value)
        self._assert_canonical_error(
            lambda: rebuild_research_csv_from_canonical_bytes(
                result.descriptor.canonical_json_bytes,
                [drifted_chunk],
            )
        )

    def test_public_models_are_frozen_and_error_codes_are_closed(self):
        for model in (CsvDescriptor, CsvRow, CsvChunk):
            self.assertTrue(model.__dataclass_params__.frozen)
        self.assertEqual(
            RESEARCH_CSV_ERROR_CODES,
            {
                "RESEARCH_CSV_UNAVAILABLE",
                "RESEARCH_CSV_SIZE_LIMIT",
                "RESEARCH_CSV_INVALID",
                "RESEARCH_CSV_ENCODING_UNSUPPORTED",
                "RESEARCH_CSV_STRUCTURE_LIMIT",
                "RESEARCH_CSV_CONTENT_LIMIT",
                "RESEARCH_CSV_PARSE_FAILED",
            },
        )
        with self.assertRaises(ValueError):
            ResearchCsvContractError("PRIVATE_DETAIL")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result = parse_research_csv_bytes(b"A\n1")
            result.rows[0].logical_row_number = 2

    def _assert_error(self, raw, expected_code):
        with self.assertRaises(ResearchCsvContractError) as captured:
            parse_research_csv_bytes(raw)
        self.assertEqual(captured.exception.error_code, expected_code)
        self.assertEqual(str(captured.exception), expected_code)
        self.assertEqual(captured.exception.args, (expected_code,))

    def _assert_canonical_error(self, operation):
        with self.assertRaises(ResearchCsvContractError) as captured:
            operation()
        self.assertEqual(captured.exception.error_code, "RESEARCH_CSV_INVALID")

    @staticmethod
    def _canonical_json(value):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
