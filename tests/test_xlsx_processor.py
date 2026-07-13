import unittest
from dataclasses import replace

from application.services.xlsx_processor import (
    XlsxProcessingError,
    XlsxProcessor,
)
from infrastructure.attachments.parser_protocol import ParsedResearchXlsx
from infrastructure.attachments.research_xlsx_contract import (
    NormalizedResearchXlsx,
    XlsxDescriptor,
    XlsxRow,
    XlsxSheetDescriptor,
    build_normalized_research_xlsx,
)


_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _normalized_xlsx():
    visible = XlsxSheetDescriptor(
        ordinal=0,
        name="公开表",
        visibility="visible",
        headers=("患者", "结果"),
        header_row_start=1,
        header_row_end=1,
        physical_line_count=2,
        record_count=2,
        data_row_count=1,
        column_count=2,
        non_empty_cell_count=4,
        formula_like_cell_count=1,
        formula_cell_count=1,
        merged_range_count=1,
        missing_value_counts=(0, 0),
    )
    hidden = XlsxSheetDescriptor(
        ordinal=2,
        name="隐藏表",
        visibility="veryHidden",
        headers=("患者", "备注"),
        header_row_start=2,
        header_row_end=2,
        physical_line_count=3,
        record_count=2,
        data_row_count=1,
        column_count=2,
        non_empty_cell_count=3,
        formula_like_cell_count=0,
        formula_cell_count=0,
        merged_range_count=0,
        missing_value_counts=(0, 1),
    )
    descriptor = XlsxDescriptor(
        schema_version="research_xlsx_v1",
        date_system="1900",
        workbook_sheet_count=3,
        empty_sheet_count=1,
        sheets=(visible, hidden),
        total_record_count=4,
        total_data_row_count=2,
        total_non_empty_cell_count=7,
        total_formula_like_cell_count=1,
        total_formula_cell_count=1,
        total_merged_range_count=1,
    )
    return build_normalized_research_xlsx(
        descriptor,
        (
            (
                XlsxRow(
                    logical_row_number=1,
                    physical_row_start=2,
                    physical_row_end=2,
                    values=("Alice", "=1+1"),
                    formula_cell_indexes=(1,),
                ),
            ),
            (
                XlsxRow(
                    logical_row_number=1,
                    physical_row_start=3,
                    physical_row_end=3,
                    values=("PRIVATE_HIDDEN_ROW_SENTINEL", ""),
                    formula_cell_indexes=(),
                ),
            ),
        ),
    )


def _downloaded(**updates):
    value = {
        "attachment_id": "attachment-1",
        "document_version": 2,
        "file_type": "xlsx",
        "mime_type": _MIME_TYPE,
        "size_bytes": 1024,
        "page_count": None,
    }
    value.update(updates)
    return value


class FakeSandbox:
    def __init__(self, parsed=None, error=None):
        self.parsed = parsed
        self.error = error
        self.calls = []

    async def parse(self, downloaded, profile):
        self.calls.append((downloaded, profile))
        if self.error is not None:
            raise self.error
        return self.parsed


class XlsxProcessorTest(unittest.IsolatedAsyncioTestCase):
    async def test_maps_multi_sheet_visibility_formula_and_original_ordinals(self):
        parsed = ParsedResearchXlsx(
            attachment_id="attachment-1",
            document_version=2,
            mime_type=_MIME_TYPE,
            normalized=_normalized_xlsx(),
        )
        sandbox = FakeSandbox(parsed)

        result = await XlsxProcessor(sandbox).process(_downloaded())

        self.assertEqual(sandbox.calls[0][1], "research_xlsx_v1")
        self.assertEqual([sheet.ordinal for sheet in result.sheets], [0, 2])
        self.assertEqual(
            [sheet.visibility for sheet in result.sheets],
            ["visible", "veryHidden"],
        )
        formula_row = result.sheets[0].chunks[0].rows[0]
        self.assertEqual(formula_row.values[1], "=1+1")
        self.assertEqual(formula_row.formula_cell_indexes, (1,))
        self.assertEqual(result.total_formula_cell_count, 1)
        self.assertEqual(result.empty_sheet_count, 1)

    async def test_identity_drift_fails_closed(self):
        parsed = ParsedResearchXlsx(
            attachment_id="foreign-attachment",
            document_version=2,
            mime_type=_MIME_TYPE,
            normalized=_normalized_xlsx(),
        )

        with self.assertRaises(XlsxProcessingError) as raised:
            await XlsxProcessor(FakeSandbox(parsed)).process(_downloaded())

        self.assertEqual(raised.exception.error_code, "RESEARCH_XLSX_PARSE_FAILED")

    async def test_revalidates_normalized_artifact_and_rejects_orphan_chunk(self):
        normalized = _normalized_xlsx()
        orphan = replace(normalized.chunks[0], sheet_ordinal=1)
        tampered = NormalizedResearchXlsx(
            descriptor=normalized.descriptor,
            chunks=(*normalized.chunks, orphan),
        )
        parsed = ParsedResearchXlsx(
            attachment_id="attachment-1",
            document_version=2,
            mime_type=_MIME_TYPE,
            normalized=tampered,
        )

        with self.assertRaises(XlsxProcessingError) as raised:
            await XlsxProcessor(FakeSandbox(parsed)).process(_downloaded())

        self.assertEqual(raised.exception.error_code, "RESEARCH_XLSX_PARSE_FAILED")

    async def test_only_stable_worker_errors_cross_boundary(self):
        for source_code, expected_code in (
            ("RESEARCH_XLSX_ENCRYPTED", "RESEARCH_XLSX_ENCRYPTED"),
            ("RESEARCH_XLSX_INTERNAL_PATH", "RESEARCH_XLSX_PARSE_FAILED"),
        ):
            error = RuntimeError("private parser detail")
            error.error_code = source_code
            with self.subTest(source_code=source_code):
                with self.assertRaises(XlsxProcessingError) as raised:
                    await XlsxProcessor(FakeSandbox(error=error)).process(
                        _downloaded()
                    )
                self.assertEqual(raised.exception.error_code, expected_code)

    async def test_rejects_non_xlsx_metadata_before_sandbox(self):
        sandbox = FakeSandbox()

        with self.assertRaises(XlsxProcessingError) as raised:
            await XlsxProcessor(sandbox).process(
                _downloaded(mime_type="application/octet-stream")
            )

        self.assertEqual(raised.exception.error_code, "RESEARCH_XLSX_INVALID")
        self.assertEqual(sandbox.calls, [])


if __name__ == "__main__":
    unittest.main()
