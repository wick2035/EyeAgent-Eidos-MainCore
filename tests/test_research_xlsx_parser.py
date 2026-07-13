import hashlib
import json
import stat
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from infrastructure.attachments.attachment_parser_worker import (
    parse_attachment_file,
)
from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ResearchXlsxChunkManifest,
    ResearchXlsxManifest,
    WorkerRequest,
)
from infrastructure.attachments.research_xlsx_parser import (
    parse_research_xlsx_path,
)


_XLSX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _write_two_sheet_workbook(path: Path) -> None:
    workbook = Workbook()
    visible = workbook.active
    visible.title = "Visible"
    visible.append(("patient_id", "visit_date", "score", "calculated"))
    visible.append(("PRIVATE-XLSX-ROW-A", date(2026, 7, 13), 1.5, "=C2*2"))
    visible.append(("PRIVATE-XLSX-MERGED", "ignored", None, None))
    visible.merge_cells("A3:B3")

    hidden = workbook.create_sheet("Hidden")
    hidden.sheet_state = "hidden"
    hidden.append(("patient_id", "value"))
    hidden.append(("PRIVATE-XLSX-ROW-B", 7))
    workbook.save(path)
    workbook.close()


def _manifest_for(normalized) -> ResearchXlsxManifest:
    descriptor_bytes = normalized.descriptor_canonical_json_bytes
    chunks = tuple(
        ResearchXlsxChunkManifest(
            sheet_ordinal=chunk.sheet_ordinal,
            ordinal=chunk.ordinal,
            relative_path=(
                f"sheet-{chunk.sheet_ordinal:03d}-"
                f"chunk-{chunk.ordinal:05d}.json"
            ),
            sha256=hashlib.sha256(chunk_bytes).hexdigest(),
            byte_count=len(chunk_bytes),
            row_count=chunk.row_count,
            logical_row_start=chunk.logical_row_start,
            logical_row_end=chunk.logical_row_end,
            physical_row_start=chunk.physical_row_start,
            physical_row_end=chunk.physical_row_end,
            non_empty_cell_count=chunk.non_empty_cell_count,
            formula_like_cell_count=chunk.formula_like_cell_count,
            formula_cell_count=chunk.formula_cell_count,
        )
        for chunk, chunk_bytes in zip(
            normalized.chunks,
            normalized.chunk_canonical_json_bytes,
        )
    )
    descriptor = normalized.descriptor
    return ResearchXlsxManifest(
        profile="research_xlsx_v1",
        descriptor_relative_path="descriptor.json",
        descriptor_sha256=hashlib.sha256(descriptor_bytes).hexdigest(),
        descriptor_byte_count=len(descriptor_bytes),
        chunks=chunks,
        date_system=descriptor.date_system,
        workbook_sheet_count=descriptor.workbook_sheet_count,
        empty_sheet_count=descriptor.empty_sheet_count,
        total_record_count=descriptor.total_record_count,
        total_data_row_count=descriptor.total_data_row_count,
        total_non_empty_cell_count=descriptor.total_non_empty_cell_count,
        total_formula_like_cell_count=descriptor.total_formula_like_cell_count,
        total_formula_cell_count=descriptor.total_formula_cell_count,
        total_merged_range_count=descriptor.total_merged_range_count,
    )


class ResearchXlsxWorkerContractTest(unittest.TestCase):
    def test_worker_request_requires_exact_xlsx_profile_mime_and_no_page_count(self):
        request = WorkerRequest(
            input_filename="attachment.bin",
            file_type="xlsx",
            mime_type=_XLSX_MIME_TYPE,
            declared_page_count=None,
            profile="research_xlsx_v1",
        )
        self.assertEqual(WorkerRequest.from_json_bytes(request.to_json_bytes()), request)

        invalid = (
            {"mime_type": "application/zip"},
            {"profile": "assistant_visual_v1"},
            {"declared_page_count": 1},
            {"file_type": "csv"},
        )
        base = {
            "input_filename": "attachment.bin",
            "file_type": "xlsx",
            "mime_type": _XLSX_MIME_TYPE,
            "declared_page_count": None,
            "profile": "research_xlsx_v1",
        }
        for update in invalid:
            with self.subTest(update=update), self.assertRaises(
                AttachmentParserError
            ):
                WorkerRequest(**(base | update))

    def test_manifest_is_canonical_rejects_extra_fields_and_cross_sheet_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "dataset.xlsx"
            _write_two_sheet_workbook(source)
            normalized = parse_research_xlsx_path(source)
            manifest = _manifest_for(normalized)
            payload = manifest.to_json_bytes()

        self.assertEqual(ResearchXlsxManifest.from_json_bytes(payload), manifest)
        decoded = json.loads(payload)
        decoded["private_values"] = ["must-not-be-accepted"]
        with self.assertRaises(AttachmentParserError):
            ResearchXlsxManifest.from_json_bytes(
                json.dumps(decoded, separators=(",", ":"), sort_keys=True).encode()
            )

        self.assertGreaterEqual(len(manifest.chunks), 2)
        with self.assertRaises(AttachmentParserError):
            replace(manifest, chunks=tuple(reversed(manifest.chunks)))

    def test_worker_outputs_private_artifacts_but_stdout_manifest_has_no_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_root = root / "input"
            output_root = root / "output"
            input_root.mkdir(mode=0o700)
            output_root.mkdir(mode=0o700)
            source = input_root / "attachment.bin"
            _write_two_sheet_workbook(source)
            source.chmod(0o600)

            manifest = parse_attachment_file(
                WorkerRequest(
                    input_filename=source.name,
                    file_type="xlsx",
                    mime_type=_XLSX_MIME_TYPE,
                    declared_page_count=None,
                    profile="research_xlsx_v1",
                ),
                input_root,
                output_root,
            )

            stdout = manifest.to_json_bytes()
            self.assertNotIn(b"PRIVATE-XLSX-ROW-A", stdout)
            self.assertNotIn(b"PRIVATE-XLSX-ROW-B", stdout)
            expected_names = {"descriptor.json"}
            expected_names.update(chunk.relative_path for chunk in manifest.chunks)
            self.assertEqual(
                {path.name for path in output_root.iterdir()},
                expected_names,
            )
            for path in output_root.iterdir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_parser_preserves_formula_as_text_merge_anchor_dates_and_hidden_sheet(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "dataset.xlsx"
            _write_two_sheet_workbook(source)
            normalized = parse_research_xlsx_path(source)

        descriptor = normalized.descriptor
        self.assertEqual(descriptor.workbook_sheet_count, 2)
        self.assertEqual([sheet.visibility for sheet in descriptor.sheets], [
            "visible",
            "hidden",
        ])
        self.assertEqual(descriptor.total_formula_cell_count, 1)
        self.assertEqual(descriptor.total_merged_range_count, 1)
        visible_rows = tuple(
            row
            for chunk in normalized.chunks
            if chunk.sheet_ordinal == 0
            for row in chunk.rows
        )
        self.assertTrue(visible_rows[0].values[1].startswith("2026-07-13"))
        self.assertEqual(visible_rows[0].values[3], "=C2*2")
        self.assertEqual(visible_rows[0].formula_cell_indexes, (3,))
        self.assertEqual(visible_rows[1].values[:2], ("PRIVATE-XLSX-MERGED", ""))


if __name__ == "__main__":
    unittest.main()
