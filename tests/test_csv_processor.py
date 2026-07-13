import unittest
from pathlib import Path

from application.services.csv_processor import (
    CsvProcessingError,
    CsvProcessor,
)
from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ParsedResearchCsv,
)
from infrastructure.attachments.research_csv_contract import (
    parse_research_csv_bytes,
)
from infrastructure.attachments.secure_downloader import DownloadedAttachment


class _Sandbox:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def parse(self, downloaded, profile):
        self.calls.append((downloaded, profile))
        if self.error is not None:
            raise self.error
        return self.result


def _downloaded(**overrides):
    values = {
        "attachment_id": "attachment-csv",
        "analysis_attempt_id": "attempt-csv",
        "file_type": "csv",
        "filename": "dataset.csv",
        "mime_type": "text/csv",
        "size_bytes": 16,
        "content_sha256": "a" * 64,
        "page_count": None,
        "path": Path("/tmp/dataset.csv"),
        "document_version": 2,
    }
    values.update(overrides)
    return DownloadedAttachment(**values)


def _parsed(**overrides):
    values = {
        "attachment_id": "attachment-csv",
        "document_version": 2,
        "mime_type": "text/csv",
        "normalized": parse_research_csv_bytes(
            b"name,value\nAlice,=literal\nBob,"
        ),
    }
    values.update(overrides)
    return ParsedResearchCsv(**values)


class CsvProcessorTest(unittest.IsolatedAsyncioTestCase):
    async def test_maps_validated_parser_output_to_domain_dataset(self):
        sandbox = _Sandbox(_parsed())

        extracted = await CsvProcessor(sandbox).process(_downloaded())

        self.assertEqual(sandbox.calls[0][1], "research_csv_v1")
        self.assertEqual(extracted.sheet_name, "CSV")
        self.assertEqual(extracted.headers, ("name", "value"))
        self.assertEqual(extracted.data_row_count, 2)
        self.assertEqual(extracted.missing_value_counts, (0, 1))
        self.assertEqual(extracted.formula_like_cell_count, 1)
        self.assertEqual(extracted.chunks[0].rows[0].values[1], "=literal")
        self.assertEqual(
            extracted.descriptor_sha256,
            sandbox.result.normalized.descriptor.sha256,
        )

    async def test_rejects_parser_identity_drift(self):
        for parsed in (
            _parsed(attachment_id="other"),
            _parsed(document_version=3),
            _parsed(mime_type="application/octet-stream"),
            object(),
        ):
            with self.subTest(parsed=parsed):
                with self.assertRaises(CsvProcessingError) as raised:
                    await CsvProcessor(_Sandbox(parsed)).process(_downloaded())
                self.assertEqual(
                    raised.exception.error_code,
                    "RESEARCH_CSV_PARSE_FAILED",
                )

    async def test_propagates_only_stable_csv_errors(self):
        for code in (
            "RESEARCH_CSV_INVALID",
            "RESEARCH_CSV_ENCODING_UNSUPPORTED",
            "RESEARCH_CSV_STRUCTURE_LIMIT",
            "RESEARCH_CSV_CONTENT_LIMIT",
        ):
            with self.subTest(code=code):
                with self.assertRaises(CsvProcessingError) as raised:
                    await CsvProcessor(
                        _Sandbox(error=AttachmentParserError(code))
                    ).process(_downloaded())
                self.assertEqual(raised.exception.error_code, code)

        with self.assertRaises(CsvProcessingError) as raised:
            await CsvProcessor(
                _Sandbox(error=AttachmentParserError("PRIVATE_WORKER_PATH"))
            ).process(_downloaded())
        self.assertEqual(
            raised.exception.error_code,
            "RESEARCH_CSV_PARSE_FAILED",
        )

    async def test_rejects_invalid_downloaded_contract_before_sandbox(self):
        sandbox = _Sandbox(_parsed())
        valid = vars(_downloaded()).copy()
        invalid_contracts = (
            {**valid, "file_type": "text"},
            {**valid, "mime_type": "application/octet-stream"},
            {**valid, "size_bytes": 0},
            {**valid, "page_count": 1},
        )
        for downloaded in invalid_contracts:
            with self.subTest(downloaded=downloaded):
                with self.assertRaises(CsvProcessingError) as raised:
                    await CsvProcessor(sandbox).process(downloaded)
                self.assertEqual(
                    raised.exception.error_code,
                    "RESEARCH_CSV_INVALID",
                )
        self.assertEqual(sandbox.calls, [])


if __name__ == "__main__":
    unittest.main()
