import io
import stat
import struct
import tempfile
import unittest
import zipfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils.datetime import CALENDAR_MAC_1904

from infrastructure.attachments.research_xlsx_contract import (
    ResearchXlsxContractError,
)
from infrastructure.attachments.research_xlsx_parser import (
    _normalize_string,
    _validate_archive_entries,
    parse_research_xlsx_path,
)


def _workbook_bytes(configure=None) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Visible"
    sheet.append(("id", "value"))
    sheet.append(("P-1", 1))
    if configure is not None:
        configure(workbook)
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as stream:
        workbook.save(stream.name)
        workbook.close()
        return Path(stream.name).read_bytes()


def _rewrite_archive(
    raw: bytes,
    replacements: dict[str, bytes] | None = None,
    additions: tuple[tuple[zipfile.ZipInfo | str, bytes], ...] = (),
    renames: dict[str, str] | None = None,
) -> bytes:
    replacements = replacements or {}
    renames = renames or {}
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as source, zipfile.ZipFile(
        output,
        "w",
    ) as target:
        for info in source.infolist():
            target_name: zipfile.ZipInfo | str = info
            if info.filename in renames:
                target_name = renames[info.filename]
            target.writestr(
                target_name,
                replacements.get(info.filename, source.read(info)),
            )
        for name_or_info, content in additions:
            target.writestr(name_or_info, content)
    return output.getvalue()


def _archive_member(raw: bytes, name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
        return archive.read(name)


def _parse_bytes(raw: bytes):
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as stream:
        Path(stream.name).write_bytes(raw)
        return parse_research_xlsx_path(stream.name)


class ResearchXlsxArchiveSecurityTest(unittest.TestCase):
    def assert_contract_error(self, expected: str, operation) -> None:
        with self.assertRaises(ResearchXlsxContractError) as raised:
            operation()
        self.assertEqual(raised.exception.error_code, expected)

    def test_cfb_encrypted_office_container_is_encrypted(self):
        self.assert_contract_error(
            "RESEARCH_XLSX_ENCRYPTED",
            lambda: _parse_bytes(
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"encrypted"
            ),
        )

    def test_zip_magic_must_start_at_byte_zero(self):
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(b"SFX-JUNK" + _workbook_bytes()),
        )

    def test_entry_encryption_and_zip64_are_rejected(self):
        encrypted = zipfile.ZipInfo("xl/workbook.xml")
        encrypted.flag_bits = 0x1
        self.assert_contract_error(
            "RESEARCH_XLSX_ENCRYPTED",
            lambda: _validate_archive_entries([encrypted]),
        )

        zip64 = zipfile.ZipInfo("xl/workbook.xml")
        zip64.extra = struct.pack("<HHQ", 0x0001, 8, 1)
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _validate_archive_entries([zip64]),
        )

        version_only = zipfile.ZipInfo("xl/workbook.xml")
        version_only.create_version = 45
        version_only.extract_version = 45
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _validate_archive_entries([version_only]),
        )

    def test_unsafe_names_duplicates_symlink_and_compression_are_rejected(self):
        unsafe_names = (
            "../escape.xml",
            "xl\\workbook.xml",
            "/absolute.xml",
        )
        for name in unsafe_names:
            with self.subTest(name=name):
                self.assert_contract_error(
                    "RESEARCH_XLSX_INVALID",
                    lambda name=name: _validate_archive_entries(
                        [zipfile.ZipInfo(name)]
                    ),
                )

        duplicate = zipfile.ZipInfo("xl/workbook.xml")
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _validate_archive_entries([duplicate, duplicate]),
        )

        symlink = zipfile.ZipInfo("xl/workbook.xml")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _validate_archive_entries([symlink]),
        )

        unsupported = zipfile.ZipInfo("xl/workbook.xml")
        unsupported.compress_type = zipfile.ZIP_BZIP2
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _validate_archive_entries([unsupported]),
        )

    def test_zip_bomb_ratio_is_rejected_before_decompression(self):
        bomb = zipfile.ZipInfo("xl/workbook.xml")
        bomb.file_size = 10_001
        bomb.compress_size = 100
        self.assert_contract_error(
            "RESEARCH_XLSX_STRUCTURE_LIMIT",
            lambda: _validate_archive_entries([bomb]),
        )

    def test_active_content_part_families_are_rejected(self):
        names = (
            "xl/vbaProject.bin",
            "xl/activeX/activeX1.bin",
            "xl/oleObjects/oleObject1.bin",
            "xl/embeddings/embedded1.bin",
            "xl/externalLinks/externalLink1.xml",
            "xl/macroSheets/sheet1.xml",
            "xl/connections.xml",
        )
        for name in names:
            with self.subTest(name=name):
                self.assert_contract_error(
                    "RESEARCH_XLSX_INVALID",
                    lambda name=name: _validate_archive_entries(
                        [zipfile.ZipInfo(name)]
                    ),
                )

    def test_dtd_entity_and_external_relationship_are_rejected(self):
        raw = _workbook_bytes()
        workbook_xml = _archive_member(raw, "xl/workbook.xml")
        dtd = workbook_xml.replace(
            b"<workbook ",
            b'<!DOCTYPE workbook [<!ENTITY x "boom">]><workbook ',
            1,
        )
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {"xl/workbook.xml": dtd})
            ),
        )

        relationships_path = "xl/_rels/workbook.xml.rels"
        relationships = _archive_member(raw, relationships_path)
        external = relationships.replace(
            b"</Relationships>",
            b'<Relationship Id="external" Type="http://example.test/type" '
            b'Target="https://example.test/private" TargetMode="External"/>'
            b"</Relationships>",
        )
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {relationships_path: external})
            ),
        )

    def test_xml_content_type_cannot_hide_dtd_behind_binary_suffix(self):
        raw = _workbook_bytes()
        styles_path = "xl/styles.xml"
        styles = _archive_member(raw, styles_path).replace(
            b"<styleSheet ",
            b"<!DOCTYPE styleSheet><styleSheet ",
            1,
        )
        content_types_path = "[Content_Types].xml"
        content_types = _archive_member(raw, content_types_path).replace(
            b"/xl/styles.xml",
            b"/xl/styles.bin",
            1,
        )

        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(
                    raw,
                    {
                        styles_path: styles,
                        content_types_path: content_types,
                    },
                    renames={styles_path: "xl/styles.bin"},
                )
            ),
        )

    def test_relationship_escape_is_rejected(self):
        raw = _workbook_bytes()
        relationships_path = "xl/_rels/workbook.xml.rels"
        relationships = _archive_member(raw, relationships_path)
        escaped = relationships.replace(
            b"</Relationships>",
            b'<Relationship Id="escape" Type="http://example.test/type" '
            b'Target="../../outside.xml"/>'
            b"</Relationships>",
        )
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {relationships_path: escaped})
            ),
        )

    def test_active_relationship_type_is_rejected_even_with_innocent_target(self):
        raw = _workbook_bytes()
        relationships_path = "xl/_rels/workbook.xml.rels"
        relationships = _archive_member(raw, relationships_path)
        disguised = relationships.replace(
            b"</Relationships>",
            b'<Relationship Id="disguised" '
            b'Type="http://schemas.example.test/relationships/vbaProject" '
            b'Target="styles.xml"/></Relationships>',
        )
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {relationships_path: disguised})
            ),
        )

    def test_workbook_content_type_and_root_relationship_are_exact(self):
        raw = _workbook_bytes()
        content_types_path = "[Content_Types].xml"
        content_types = _archive_member(raw, content_types_path)
        spoofed = content_types.replace(
            b"spreadsheetml.sheet.main+xml",
            b"spreadsheetml.worksheet+xml",
        )
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {content_types_path: spoofed})
            ),
        )

        root_relationships_path = "_rels/.rels"
        root_relationships = _archive_member(raw, root_relationships_path)
        decoy = root_relationships.replace(
            b'Target="xl/workbook.xml"',
            b'Target="xl/worksheets/sheet1.xml"',
            1,
        )
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {root_relationships_path: decoy})
            ),
        )


class ResearchXlsxSemanticParserTest(unittest.TestCase):
    def assert_contract_error(self, expected: str, operation) -> None:
        with self.assertRaises(ResearchXlsxContractError) as raised:
            operation()
        self.assertEqual(raised.exception.error_code, expected)

    def test_visibility_empty_sheet_gap_dense_rows_merge_and_formula(self):
        def configure(workbook):
            visible = workbook.active
            visible["B2"] = "=1+1"
            visible.merge_cells("A4:B4")
            visible["A4"] = "anchor"
            empty = workbook.create_sheet("Empty")
            empty.sheet_state = "hidden"
            very_hidden = workbook.create_sheet("VeryHidden")
            very_hidden.sheet_state = "veryHidden"
            very_hidden.append(("private",))
            very_hidden.append(("row",))

        normalized = _parse_bytes(_workbook_bytes(configure))

        self.assertEqual(normalized.descriptor.empty_sheet_count, 1)
        self.assertEqual(
            tuple(sheet.ordinal for sheet in normalized.descriptor.sheets),
            (0, 2),
        )
        self.assertEqual(
            tuple(sheet.visibility for sheet in normalized.descriptor.sheets),
            ("visible", "veryHidden"),
        )
        visible_rows = tuple(
            row
            for chunk in normalized.chunks
            if chunk.sheet_ordinal == 0
            for row in chunk.rows
        )
        self.assertEqual(len(visible_rows), 3)
        self.assertEqual(visible_rows[0].formula_cell_indexes, (1,))
        self.assertEqual(visible_rows[1].values, ("", ""))
        self.assertEqual(visible_rows[2].values, ("anchor", ""))

    def test_1904_dates_times_and_timedelta_are_locale_free(self):
        def configure(workbook):
            workbook.epoch = CALENDAR_MAC_1904
            sheet = workbook.active
            sheet.delete_rows(1, sheet.max_row)
            sheet.append(("date", "datetime", "time", "duration"))
            sheet.append(
                (
                    date(2026, 7, 13),
                    datetime(2026, 7, 13, 4, 5, 6, 123000),
                    time(4, 5, 6, 123000),
                    timedelta(days=1, hours=2, minutes=3, seconds=4.5),
                )
            )

        normalized = _parse_bytes(_workbook_bytes(configure))
        row = normalized.chunks[0].rows[0]

        self.assertEqual(normalized.descriptor.date_system, "1904")
        self.assertTrue(row.values[0].startswith("2026-07-13"))
        self.assertEqual(row.values[1], "2026-07-13T04:05:06.123000")
        self.assertEqual(row.values[2], "04:05:06.123000")
        self.assertEqual(row.values[3], "P1DT2H3M4.5S")

    def test_header_formula_and_sparse_header_are_rejected(self):
        def formula_header(workbook):
            workbook.active["A1"] = "=1+1"

        self.assert_contract_error(
            "RESEARCH_XLSX_FORMULA_UNSUPPORTED",
            lambda: _parse_bytes(_workbook_bytes(formula_header)),
        )

        def sparse_header(workbook):
            sheet = workbook.active
            sheet.delete_rows(1, sheet.max_row)
            sheet["A1"] = "a"
            sheet["C1"] = "c"

        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(_workbook_bytes(sparse_header)),
        )

    def test_array_and_data_table_formulas_are_rejected(self):
        def formula(workbook):
            workbook.active["B2"] = "=1+1"

        raw = _workbook_bytes(formula)
        sheet_path = "xl/worksheets/sheet1.xml"
        sheet = _archive_member(raw, sheet_path)
        for formula_type in (b"array", b"dataTable"):
            with self.subTest(formula_type=formula_type):
                mutated = sheet.replace(
                    b"<f>",
                    b'<f t="' + formula_type + b'" ref="B2">',
                    1,
                )
                self.assert_contract_error(
                    "RESEARCH_XLSX_FORMULA_UNSUPPORTED",
                    lambda mutated=mutated: _parse_bytes(
                        _rewrite_archive(raw, {sheet_path: mutated})
                    ),
                )

    def test_declared_row_and_column_bounds_are_rejected(self):
        raw = _workbook_bytes()
        sheet_path = "xl/worksheets/sheet1.xml"
        sheet = _archive_member(raw, sheet_path)
        for coordinate in (b"A50001", b"CW2"):
            with self.subTest(coordinate=coordinate):
                mutated = sheet.replace(b'r="A2"', b'r="' + coordinate + b'"', 1)
                self.assert_contract_error(
                    "RESEARCH_XLSX_STRUCTURE_LIMIT",
                    lambda mutated=mutated: _parse_bytes(
                        _rewrite_archive(raw, {sheet_path: mutated})
                    ),
                )

    def test_overlapping_merged_ranges_are_rejected(self):
        def merged(workbook):
            workbook.active.merge_cells("A2:B2")

        raw = _workbook_bytes(merged)
        sheet_path = "xl/worksheets/sheet1.xml"
        sheet = _archive_member(raw, sheet_path)
        mutated = sheet.replace(
            b"</mergeCells>",
            b'<mergeCell ref="A2:A3"/></mergeCells>',
            1,
        )
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {sheet_path: mutated})
            ),
        )

    def test_duplicate_cell_coordinate_is_rejected(self):
        raw = _workbook_bytes()
        sheet_path = "xl/worksheets/sheet1.xml"
        sheet = _archive_member(raw, sheet_path)
        duplicate = sheet.replace(
            b"</sheetData>",
            b'<row r="3"><c r="A2" t="inlineStr"><is><t>dupe</t></is>'
            b"</c></row></sheetData>",
        )
        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {sheet_path: duplicate})
            ),
        )

    def test_row_declaration_must_match_cell_coordinates(self):
        raw = _workbook_bytes()
        sheet_path = "xl/worksheets/sheet1.xml"
        sheet = _archive_member(raw, sheet_path)
        mismatched = sheet.replace(b'<row r="2">', b'<row r="1">', 1)

        self.assert_contract_error(
            "RESEARCH_XLSX_INVALID",
            lambda: _parse_bytes(
                _rewrite_archive(raw, {sheet_path: mismatched})
            ),
        )

    def test_cell_string_codepoint_limit_is_enforced(self):
        self.assert_contract_error(
            "RESEARCH_XLSX_CONTENT_LIMIT",
            lambda: _normalize_string("x" * 32_768),
        )


if __name__ == "__main__":
    unittest.main()
