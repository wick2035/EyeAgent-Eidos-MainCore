import hashlib
import json
import stat
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from infrastructure.attachments.attachment_parser_worker import (
    _write_output_bundle,
    parse_attachment_file,
)
from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ResearchCsvManifest,
    WorkerRequest,
)
from infrastructure.attachments.research_csv_contract import (
    RESEARCH_CSV_ERROR_CODES,
    ResearchCsvContractError,
    parse_research_csv_bytes,
)


class ResearchCsvParserTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir(mode=0o700)
        self.output_dir.mkdir(mode=0o700)

    def tearDown(self):
        self.temporary.cleanup()

    def _request(self) -> WorkerRequest:
        return WorkerRequest(
            input_filename="dataset.csv",
            file_type="csv",
            mime_type="text/csv",
            declared_page_count=None,
            profile="research_csv_v1",
        )

    def _parse(self, content: bytes) -> ResearchCsvManifest:
        (self.input_dir / "dataset.csv").write_bytes(content)
        manifest = parse_attachment_file(
            self._request(),
            self.input_dir,
            self.output_dir,
        )
        self.assertIsInstance(manifest, ResearchCsvManifest)
        return manifest

    def test_worker_request_requires_the_exact_research_csv_profile_tuple(self):
        request = self._request()
        self.assertEqual(WorkerRequest.from_json_bytes(request.to_json_bytes()), request)

        invalid = (
            dict(file_type="text", mime_type="text/plain", profile="research_csv_v1"),
            dict(file_type="csv", mime_type="text/csv", profile="research_text_v1"),
            dict(file_type="csv", mime_type="text/csv", profile="assistant_visual_v1"),
            dict(file_type="csv", mime_type="application/csv", profile="research_csv_v1"),
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_TYPE_INVALID",
            ):
                WorkerRequest(
                    input_filename="dataset.csv",
                    declared_page_count=None,
                    **values,
                )

        with self.assertRaisesRegex(
            AttachmentParserError,
            "ATTACHMENT_PAGE_COUNT_INVALID",
        ):
            WorkerRequest(
                input_filename="dataset.csv",
                file_type="csv",
                mime_type="text/csv",
                declared_page_count=1,
                profile="research_csv_v1",
            )

        decoded = json.loads(request.to_json_bytes())
        decoded["extra"] = "rejected"
        with self.assertRaisesRegex(
            AttachmentParserError,
            "ATTACHMENT_WORKER_REQUEST_INVALID",
        ):
            WorkerRequest.from_json_bytes(json.dumps(decoded).encode("utf-8"))

    def test_utf8_sig_multiline_and_formula_values_write_canonical_artifacts(self):
        raw = (
            b'\xef\xbb\xbf" Name ",Score,Formula\r\n'
            b'Alice,1,=1+1\r\n'
            b'"Bob\r\nB.",,@SUM(A1)'
        )
        manifest = self._parse(raw)
        expected = parse_research_csv_bytes(raw)

        self.assertEqual(manifest.profile, "research_csv_v1")
        self.assertEqual(manifest.physical_line_count, 4)
        self.assertEqual(manifest.record_count, 3)
        self.assertEqual(manifest.data_row_count, 2)
        self.assertEqual(manifest.column_count, 3)
        self.assertEqual(manifest.formula_like_cell_count, 2)
        self.assertEqual(manifest.descriptor_relative_path, "descriptor.json")
        self.assertEqual(len(manifest.chunks), 1)

        descriptor = self.output_dir / manifest.descriptor_relative_path
        chunk_manifest = manifest.chunks[0]
        chunk = self.output_dir / chunk_manifest.relative_path
        self.assertEqual(descriptor.read_bytes(), expected.descriptor_canonical_json_bytes)
        self.assertEqual(chunk.read_bytes(), expected.chunk_canonical_json_bytes[0])
        self.assertEqual(
            manifest.descriptor_sha256,
            hashlib.sha256(descriptor.read_bytes()).hexdigest(),
        )
        self.assertEqual(manifest.descriptor_byte_count, descriptor.stat().st_size)
        self.assertEqual(
            chunk_manifest.sha256,
            hashlib.sha256(chunk.read_bytes()).hexdigest(),
        )
        self.assertEqual(chunk_manifest.byte_count, chunk.stat().st_size)
        self.assertEqual(
            (
                chunk_manifest.row_count,
                chunk_manifest.logical_row_start,
                chunk_manifest.logical_row_end,
                chunk_manifest.physical_row_start,
                chunk_manifest.physical_row_end,
            ),
            (2, 1, 2, 2, 4),
        )
        self.assertEqual(stat.S_IMODE(descriptor.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(chunk.stat().st_mode), 0o600)

        chunk_value = json.loads(chunk.read_bytes())
        self.assertEqual(chunk_value["rows"][0]["values"], ["Alice", "1", "=1+1"])
        self.assertEqual(chunk_value["rows"][1]["values"], ["Bob\nB.", "", "@SUM(A1)"])
        stdout = manifest.to_json_bytes()
        self.assertNotIn(b"Alice", stdout)
        self.assertNotIn(b"@SUM", stdout)
        self.assertEqual(ResearchCsvManifest.from_json_bytes(stdout), manifest)

    def test_utf8_and_utf8_sig_produce_identical_artifacts(self):
        plain = b"Name,Value\nA,1"
        first = self._parse(plain)
        first_descriptor = (self.output_dir / "descriptor.json").read_bytes()
        first_chunk = (self.output_dir / "chunk-00001.json").read_bytes()

        self.output_dir = self.root / "output-bom"
        self.output_dir.mkdir(mode=0o700)
        second = self._parse(b"\xef\xbb\xbf" + plain)

        self.assertEqual(second.descriptor_sha256, first.descriptor_sha256)
        self.assertEqual(second.chunks[0].sha256, first.chunks[0].sha256)
        self.assertEqual((self.output_dir / "descriptor.json").read_bytes(), first_descriptor)
        self.assertEqual((self.output_dir / "chunk-00001.json").read_bytes(), first_chunk)

    def test_manifest_rejects_extra_fields_wrong_profile_and_crossed_paths(self):
        manifest = self._parse(b"Name,Value\nA,1")
        with self.assertRaises(AttachmentParserError):
            ResearchCsvManifest.from_json_bytes(manifest.to_json_bytes() + b"\n")
        decoded = json.loads(manifest.to_json_bytes())
        invalid = []

        extra = dict(decoded)
        extra["values"] = [["private"]]
        invalid.append(extra)

        wrong_profile = dict(decoded)
        wrong_profile["profile"] = "research_docx_v1"
        invalid.append(wrong_profile)

        crossed_path = json.loads(manifest.to_json_bytes())
        crossed_path["chunks"][0]["relative_path"] = "chunk-00002.json"
        invalid.append(crossed_path)

        extra_chunk = json.loads(manifest.to_json_bytes())
        extra_chunk["chunks"][0]["values"] = ["private"]
        invalid.append(extra_chunk)

        for value in invalid:
            with self.subTest(value=value), self.assertRaises(AttachmentParserError):
                ResearchCsvManifest.from_json_bytes(
                    json.dumps(value, separators=(",", ":")).encode("utf-8")
                )

    def test_bundle_uses_exact_artifact_set_and_revalidates_bytes_and_hashes(self):
        manifest = self._parse(b"Name,Value\nA,1\nB,2")
        bundle = self.root / "output.bundle"
        bundle.touch(mode=0o600)

        _write_output_bundle(manifest, self.output_dir, bundle)

        with zipfile.ZipFile(bundle) as archive:
            self.assertEqual(
                [entry.filename for entry in archive.infolist()],
                ["descriptor.json", "chunk-00001.json"],
            )
            self.assertTrue(
                all(
                    entry.compress_type == zipfile.ZIP_STORED
                    for entry in archive.infolist()
                )
            )

        bad_bytes = replace(
            manifest,
            descriptor_byte_count=manifest.descriptor_byte_count + 1,
        )
        with self.assertRaisesRegex(
            AttachmentParserError,
            "ATTACHMENT_OUTPUT_SIZE_MISMATCH",
        ):
            _write_output_bundle(bad_bytes, self.output_dir, bundle)

        bad_hash = replace(manifest, descriptor_sha256="0" * 64)
        with self.assertRaisesRegex(
            AttachmentParserError,
            "ATTACHMENT_OUTPUT_HASH_MISMATCH",
        ):
            _write_output_bundle(bad_hash, self.output_dir, bundle)

    def test_unknown_parser_failure_collapses_without_private_content(self):
        (self.input_dir / "dataset.csv").write_bytes(b"Name\nprivate-value")
        with patch(
            "infrastructure.attachments.attachment_parser_worker.parse_research_csv_bytes",
            side_effect=RuntimeError("private-value"),
        ):
            with self.assertRaises(AttachmentParserError) as captured:
                parse_attachment_file(
                    self._request(),
                    self.input_dir,
                    self.output_dir,
                )

        self.assertEqual(captured.exception.error_code, "RESEARCH_CSV_PARSE_FAILED")
        self.assertNotIn("private-value", str(captured.exception))

    def test_worker_only_passes_through_stable_research_csv_error_codes(self):
        (self.input_dir / "dataset.csv").write_bytes(b"Name\nvalue")
        for error_code in RESEARCH_CSV_ERROR_CODES:
            with self.subTest(error_code=error_code), patch(
                "infrastructure.attachments.attachment_parser_worker.parse_research_csv_bytes",
                side_effect=ResearchCsvContractError(error_code),
            ):
                with self.assertRaises(AttachmentParserError) as captured:
                    parse_attachment_file(
                        self._request(),
                        self.input_dir,
                        self.output_dir,
                    )
            self.assertEqual(captured.exception.error_code, error_code)


if __name__ == "__main__":
    unittest.main()
