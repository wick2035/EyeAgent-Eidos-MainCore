import hashlib
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from infrastructure.attachments import parser_protocol as protocol
from infrastructure.attachments.attachment_parser_worker import (
    parse_attachment_file,
)
from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    WorkerRequest,
)
from utils import pdf_utils
from utils.pdf_utils import (
    MAX_PDF_PAGE_PIXELS,
    MAX_PDF_TOTAL_PIXELS,
    StrictPdfError,
    render_pdf_path_strict,
)


class _FakePixmap:
    width = 100
    height = 100

    def tobytes(self, output):
        if output != "jpeg":
            raise AssertionError("strict renderer must emit JPEG")
        return b"jpeg-page"


class _FakePage:
    def __init__(self, width=612, height=792, *, blocks=None):
        self.rect = type("Rect", (), {"width": width, "height": height})()
        self.matrix = None
        self.blocks = (
            blocks
            if blocks is not None
            else [(0, 0, 1, 1, "研究文档有效文本内容 1234567890 ABCDEFGHIJKLMNOP", 0, 0)]
        )
        self.render_calls = 0

    def get_text(self, output, *, sort):
        if output != "blocks" or sort is not True:
            raise AssertionError("research extractor must request sorted blocks")
        return self.blocks

    def get_pixmap(self, *, matrix, alpha):
        self.matrix = matrix
        self.render_calls += 1
        if alpha:
            raise AssertionError("strict renderer must not render alpha")
        return _FakePixmap()


class _FakeDocument:
    def __init__(self, pages, *, encrypted=False):
        self._pages = list(pages)
        self.needs_pass = encrypted
        self.closed = False

    def __len__(self):
        return len(self._pages)

    def __getitem__(self, index):
        return self._pages[index]

    def close(self):
        self.closed = True


class _FakeImage:
    def __init__(self, size, image_format="PNG"):
        self.size = size
        self.format = image_format

    def verify(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class AttachmentParserLimitsTest(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir(mode=0o700)
        self.output_dir.mkdir(mode=0o700)

    def tearDown(self):
        self._temporary.cleanup()

    def _request(self, **overrides):
        values = {
            "input_filename": "attachment.bin",
            "file_type": "image",
            "mime_type": "image/png",
            "declared_page_count": None,
        }
        values.update(overrides)
        return WorkerRequest(**values)

    def test_worker_request_profiles_are_explicit_strict_and_versioned(self):
        assistant = self._request()
        self.assertEqual(assistant.profile, "assistant_visual_v1")
        self.assertEqual(
            json.loads(assistant.to_json_bytes()),
            {
                "declared_page_count": None,
                "file_type": "image",
                "input_filename": "attachment.bin",
                "mime_type": "image/png",
                "profile": "assistant_visual_v1",
            },
        )
        self.assertEqual(
            WorkerRequest.from_json_bytes(assistant.to_json_bytes()),
            assistant,
        )

        research = self._request(
            profile="research_pdf_v1",
            file_type="pdf",
            mime_type="application/pdf",
            declared_page_count=100,
        )
        self.assertEqual(research.profile, "research_pdf_v1")

        invalid_contracts = (
            {
                "profile": "research_pdf_v1",
                "file_type": "image",
                "mime_type": "image/png",
                "declared_page_count": None,
            },
            {
                "profile": "research_pdf_v1",
                "file_type": "pdf",
                "mime_type": "application/pdf",
                "declared_page_count": 101,
            },
            {
                "profile": "assistant_visual_v1",
                "file_type": "pdf",
                "mime_type": "application/pdf",
                "declared_page_count": 9,
            },
            {"profile": "unknown_profile_v1"},
        )
        for overrides in invalid_contracts:
            with self.subTest(overrides=overrides):
                with self.assertRaises(AttachmentParserError):
                    self._request(**overrides)

        decoded = json.loads(assistant.to_json_bytes())
        for mutation in (
            {key: value for key, value in decoded.items() if key != "profile"},
            {**decoded, "unknown": True},
            {**decoded, "profile": "unknown_profile_v1"},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(
                    AttachmentParserError,
                    "ATTACHMENT_WORKER_REQUEST_INVALID|ATTACHMENT_PROFILE_INVALID",
                ):
                    WorkerRequest.from_json_bytes(
                        json.dumps(mutation).encode("utf-8")
                    )

    def test_research_manifest_is_independent_and_validates_all_artifacts(self):
        page_type = protocol.ResearchPdfPageManifest
        manifest_type = protocol.ResearchPdfManifest
        page = page_type(
            page_number=1,
            text_relative_path="page-0001.txt",
            text_sha256="a" * 64,
            ocr_image_relative_path="page-0001-ocr.jpg",
            ocr_image_sha256="b" * 64,
        )
        manifest = manifest_type(pages=(page,))
        self.assertEqual(
            manifest_type.from_json_bytes(manifest.to_json_bytes()),
            manifest,
        )
        self.assertEqual(
            json.loads(manifest.to_json_bytes())["profile"],
            "research_pdf_v1",
        )

        invalid_pages = (
            dict(
                page_number=1,
                text_relative_path="../page-0001.txt",
                text_sha256="a" * 64,
            ),
            dict(
                page_number=1,
                text_relative_path="page-0002.txt",
                text_sha256="a" * 64,
            ),
            dict(
                page_number=1,
                text_relative_path="page-0001.txt",
                text_sha256="a" * 64,
                ocr_image_relative_path="page-0001-ocr.jpg",
                ocr_image_sha256=None,
            ),
            dict(
                page_number=1,
                text_relative_path="page-0001.txt",
                text_sha256="a" * 64,
                ocr_image_relative_path="page-0002-ocr.jpg",
                ocr_image_sha256="b" * 64,
            ),
        )
        for values in invalid_pages:
            with self.subTest(values=values):
                with self.assertRaises(AttachmentParserError):
                    page_type(**values)

        duplicate_artifact = page_type(
            page_number=2,
            text_relative_path="page-0002.txt",
            text_sha256="c" * 64,
            ocr_image_relative_path="page-0002-ocr.jpg",
            ocr_image_sha256="d" * 64,
        )
        object.__setattr__(
            duplicate_artifact,
            "ocr_image_relative_path",
            "page-0001.txt",
        )
        with self.assertRaises(AttachmentParserError):
            manifest_type(pages=(page, duplicate_artifact))

        raw = json.loads(manifest.to_json_bytes())
        raw["unknown"] = True
        with self.assertRaisesRegex(
            AttachmentParserError,
            "ATTACHMENT_WORKER_MANIFEST_INVALID",
        ):
            manifest_type.from_json_bytes(json.dumps(raw).encode("utf-8"))

    def test_research_text_quality_thresholds_are_named_and_boundary_stable(self):
        valid_limit = pdf_utils.RESEARCH_PDF_MIN_VALID_CHARACTERS
        non_whitespace_limit = (
            pdf_utils.RESEARCH_PDF_MIN_NON_WHITESPACE_CHARACTERS
        )
        self.assertGreater(valid_limit, 0)
        self.assertGreaterEqual(non_whitespace_limit, valid_limit)

        enough = "中" * valid_limit + "." * (
            non_whitespace_limit - valid_limit
        )
        one_valid_short = "中" * (valid_limit - 1) + "." * (
            non_whitespace_limit - valid_limit + 1
        )
        one_non_whitespace_short = "中" * valid_limit + "." * max(
            non_whitespace_limit - valid_limit - 1,
            0,
        )
        self.assertFalse(pdf_utils.is_research_pdf_text_low_quality(enough))
        self.assertTrue(
            pdf_utils.is_research_pdf_text_low_quality(one_valid_short)
        )
        self.assertTrue(
            pdf_utils.is_research_pdf_text_low_quality(
                one_non_whitespace_short
            )
        )

    def test_research_pdf_accepts_100_pages_and_rejects_101_or_mismatch(self):
        input_path = self.input_dir / "attachment.bin"
        input_path.write_bytes(b"pdf")
        accepted_output = self.output_dir / "accepted"
        too_many_output = self.output_dir / "too-many"
        mismatch_output = self.output_dir / "mismatch"
        accepted_output.mkdir()
        too_many_output.mkdir()
        mismatch_output.mkdir()

        pages = [_FakePage() for _ in range(100)]
        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument(pages),
        ):
            artifacts = pdf_utils.extract_research_pdf_path_strict(
                input_path,
                accepted_output,
                declared_page_count=100,
            )
        self.assertEqual(len(artifacts), 100)
        self.assertTrue(all(page.render_calls == 0 for page in pages))
        self.assertEqual(
            stat.S_IMODE((accepted_output / "page-0001.txt").stat().st_mode),
            0o600,
        )

        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument([_FakePage()] * 101),
        ):
            with self.assertRaisesRegex(
                StrictPdfError,
                "RESEARCH_PDF_PAGE_LIMIT",
            ):
                pdf_utils.extract_research_pdf_path_strict(
                    input_path,
                    too_many_output,
                    declared_page_count=100,
                )

        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument([_FakePage()]),
        ):
            with self.assertRaisesRegex(
                StrictPdfError,
                "ATTACHMENT_PAGE_COUNT_MISMATCH",
            ):
                pdf_utils.extract_research_pdf_path_strict(
                    input_path,
                    mismatch_output,
                    declared_page_count=2,
                )

    def test_research_pdf_limits_ocr_candidates_before_any_render(self):
        input_path = self.input_dir / "attachment.bin"
        input_path.write_bytes(b"pdf")
        rejected_output = self.output_dir / "rejected"
        mixed_output = self.output_dir / "mixed"
        rejected_output.mkdir()
        mixed_output.mkdir()

        rejected_pages = [_FakePage(blocks=[]) for _ in range(21)]
        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument(rejected_pages),
        ):
            with self.assertRaisesRegex(
                StrictPdfError,
                "RESEARCH_PDF_OCR_PAGE_LIMIT",
            ):
                pdf_utils.extract_research_pdf_path_strict(
                    input_path,
                    rejected_output,
                    declared_page_count=21,
                )
        self.assertEqual(sum(page.render_calls for page in rejected_pages), 0)
        self.assertEqual(list(rejected_output.iterdir()), [])

        low_quality_pages = [_FakePage(blocks=[]) for _ in range(20)]
        digital_page = _FakePage(
            blocks=[
                (0, 0, 1, 1, " 研究报告 1234567890 ABCDEFGHIJ \r\n 第二行有效文本 ", 0, 0)
            ]
        )
        mixed_pages = low_quality_pages + [digital_page]
        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument(mixed_pages),
        ):
            artifacts = pdf_utils.extract_research_pdf_path_strict(
                input_path,
                mixed_output,
                declared_page_count=21,
            )
        self.assertEqual(sum(page.render_calls for page in mixed_pages), 20)
        self.assertTrue(all(item.ocr_image_relative_path for item in artifacts[:20]))
        self.assertIsNone(artifacts[-1].ocr_image_relative_path)
        self.assertEqual(
            (mixed_output / artifacts[-1].text_relative_path).read_text(
                encoding="utf-8"
            ),
            "研究报告 1234567890 ABCDEFGHIJ\n第二行有效文本",
        )

    def test_research_pdf_fails_closed_for_document_geometry_and_text_limits(self):
        input_path = self.input_dir / "attachment.bin"
        input_path.write_bytes(b"pdf")
        cases = (
            (_FakeDocument([_FakePage()], encrypted=True), None, "PDF_ENCRYPTED"),
            (None, ValueError("corrupt details"), "PDF_INVALID"),
            (_FakeDocument([]), None, "PDF_EMPTY"),
            (
                _FakeDocument([_FakePage(width=float("nan"))]),
                None,
                "PDF_PAGE_GEOMETRY_INVALID",
            ),
        )
        for index, (document, raised, code) in enumerate(cases):
            output = self.output_dir / f"research-invalid-{index}"
            output.mkdir()
            context = (
                patch("utils.pdf_utils.fitz.open", side_effect=raised)
                if raised
                else patch("utils.pdf_utils.fitz.open", return_value=document)
            )
            with self.subTest(code=code), context:
                with self.assertRaisesRegex(StrictPdfError, code):
                    pdf_utils.extract_research_pdf_path_strict(
                        input_path,
                        output,
                        declared_page_count=1,
                    )
            self.assertEqual(list(output.iterdir()), [])

        text_output = self.output_dir / "research-text-limit"
        text_output.mkdir()
        text_page = _FakePage(
            blocks=[(0, 0, 1, 1, "A" * 32, 0, 0)]
        )
        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument([text_page]),
        ), patch.object(pdf_utils, "RESEARCH_PDF_MAX_TEXT_BYTES_TOTAL", 10):
            with self.assertRaisesRegex(
                StrictPdfError,
                "RESEARCH_PDF_TEXT_LIMIT",
            ):
                pdf_utils.extract_research_pdf_path_strict(
                    input_path,
                    text_output,
                    declared_page_count=1,
                )
        self.assertEqual(list(text_output.iterdir()), [])

        pixel_output = self.output_dir / "research-page-pixel-limit"
        pixel_output.mkdir()
        scale = pdf_utils.RESEARCH_PDF_DPI / 72.0
        pixel_page = _FakePage(
            width=(pdf_utils.RESEARCH_PDF_MAX_PAGE_PIXELS + 1) / scale,
            height=1 / scale,
            blocks=[],
        )
        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument([pixel_page]),
        ):
            with self.assertRaisesRegex(
                StrictPdfError,
                "PDF_PAGE_PIXEL_LIMIT",
            ):
                pdf_utils.extract_research_pdf_path_strict(
                    input_path,
                    pixel_output,
                    declared_page_count=1,
                )
        self.assertEqual(pixel_page.render_calls, 0)
        self.assertEqual(list(pixel_output.iterdir()), [])

        ocr_pixel_output = self.output_dir / "research-ocr-pixel-limit"
        ocr_pixel_output.mkdir()
        ocr_pixel_page = _FakePage(blocks=[])
        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument([ocr_pixel_page]),
        ), patch.object(pdf_utils, "RESEARCH_PDF_MAX_OCR_TOTAL_PIXELS", 1):
            with self.assertRaisesRegex(
                StrictPdfError,
                "RESEARCH_PDF_OCR_TOTAL_PIXEL_LIMIT",
            ):
                pdf_utils.extract_research_pdf_path_strict(
                    input_path,
                    ocr_pixel_output,
                    declared_page_count=1,
                )
        self.assertEqual(ocr_pixel_page.render_calls, 0)
        self.assertEqual(list(ocr_pixel_output.iterdir()), [])

        output_limit = self.output_dir / "research-output-limit"
        output_limit.mkdir()
        output_page = _FakePage(blocks=[])
        with patch(
            "utils.pdf_utils.fitz.open",
            return_value=_FakeDocument([output_page]),
        ), patch.object(pdf_utils, "RESEARCH_PDF_MAX_OUTPUT_BYTES", 5):
            with self.assertRaisesRegex(
                StrictPdfError,
                "ATTACHMENT_OUTPUT_LIMIT",
            ):
                pdf_utils.extract_research_pdf_path_strict(
                    input_path,
                    output_limit,
                    declared_page_count=1,
                )
        self.assertEqual(output_page.render_calls, 1)
        self.assertEqual(list(output_limit.iterdir()), [])

    def test_worker_research_profile_emits_independent_metadata_manifest(self):
        (self.input_dir / "attachment.bin").write_bytes(b"pdf")
        artifact = pdf_utils.ResearchPdfPageArtifact(
            page_number=1,
            text_relative_path="page-0001.txt",
            text_sha256="a" * 64,
            ocr_image_relative_path="page-0001-ocr.jpg",
            ocr_image_sha256="b" * 64,
        )
        with patch(
            "infrastructure.attachments.attachment_parser_worker."
            "extract_research_pdf_path_strict",
            return_value=[artifact],
            create=True,
        ) as extract:
            manifest = parse_attachment_file(
                self._request(
                    profile="research_pdf_v1",
                    file_type="pdf",
                    mime_type="application/pdf",
                    declared_page_count=1,
                ),
                self.input_dir,
                self.output_dir,
            )

        self.assertIsInstance(manifest, protocol.ResearchPdfManifest)
        self.assertEqual(manifest.pages[0].text_relative_path, "page-0001.txt")
        self.assertNotIn("正文", manifest.to_json_bytes().decode("utf-8"))
        extract.assert_called_once_with(
            (self.input_dir / "attachment.bin").resolve(),
            self.output_dir.resolve(),
            declared_page_count=1,
        )

    def test_worker_bundles_exact_research_artifact_set_without_compression(self):
        from infrastructure.attachments.attachment_parser_worker import (
            _write_output_bundle,
        )

        text = "科研正文".encode("utf-8")
        image = b"ocr-image"
        text_path = self.output_dir / "page-0001.txt"
        image_path = self.output_dir / "page-0001-ocr.jpg"
        text_path.write_bytes(text)
        image_path.write_bytes(image)
        text_path.chmod(0o600)
        image_path.chmod(0o600)
        bundle = self.root / "output.bundle"
        bundle.touch(mode=0o600)
        manifest = protocol.ResearchPdfManifest(
            pages=(
                protocol.ResearchPdfPageManifest(
                    page_number=1,
                    text_relative_path=text_path.name,
                    text_sha256=hashlib.sha256(text).hexdigest(),
                    ocr_image_relative_path=image_path.name,
                    ocr_image_sha256=hashlib.sha256(image).hexdigest(),
                ),
            )
        )

        _write_output_bundle(manifest, self.output_dir, bundle)

        with zipfile.ZipFile(bundle) as archive:
            self.assertEqual(
                [entry.filename for entry in archive.infolist()],
                ["page-0001.txt", "page-0001-ocr.jpg"],
            )
            self.assertTrue(
                all(
                    entry.compress_type == zipfile.ZIP_STORED
                    for entry in archive.infolist()
                )
            )
            self.assertEqual(archive.read("page-0001.txt"), text)
            self.assertEqual(archive.read("page-0001-ocr.jpg"), image)

    def test_image_success_writes_only_a_hashed_output_manifest(self):
        payload = b"valid-png"
        (self.input_dir / "attachment.bin").write_bytes(payload)

        with patch(
            "infrastructure.attachments.attachment_parser_worker.Image.open",
            return_value=_FakeImage((1200, 800)),
        ):
            manifest = parse_attachment_file(
                self._request(), self.input_dir, self.output_dir
            )

        self.assertEqual(len(manifest.pages), 1)
        page = manifest.pages[0]
        self.assertEqual(page.page_number, 1)
        self.assertFalse(Path(page.relative_path).is_absolute())
        self.assertNotIn("..", Path(page.relative_path).parts)
        output = self.output_dir / page.relative_path
        self.assertEqual(output.read_bytes(), payload)
        self.assertEqual(page.sha256, hashlib.sha256(payload).hexdigest())

    def test_image_over_fifty_megapixels_is_rejected(self):
        (self.input_dir / "attachment.bin").write_bytes(b"image")

        with patch(
            "infrastructure.attachments.attachment_parser_worker.Image.open",
            return_value=_FakeImage((10_000, 5_001)),
        ):
            with self.assertRaisesRegex(
                AttachmentParserError, "ATTACHMENT_IMAGE_PIXEL_LIMIT"
            ):
                parse_attachment_file(
                    self._request(), self.input_dir, self.output_dir
                )

    def test_pdf_encrypted_corrupt_empty_and_page_limit_fail_closed(self):
        input_path = self.input_dir / "attachment.bin"
        input_path.write_bytes(b"pdf")
        cases = (
            (_FakeDocument([_FakePage()], encrypted=True), None, "PDF_ENCRYPTED"),
            (None, ValueError("corrupt details"), "PDF_INVALID"),
            (_FakeDocument([]), None, "PDF_EMPTY"),
            (_FakeDocument([_FakePage()] * 9), None, "PDF_PAGE_LIMIT"),
        )

        for document, raised, code in cases:
            with self.subTest(code=code):
                open_result = raised if raised is not None else document
                with patch("utils.pdf_utils.fitz.open", side_effect=raised) if raised else patch(
                    "utils.pdf_utils.fitz.open", return_value=open_result
                ):
                    with self.assertRaisesRegex(StrictPdfError, code):
                        render_pdf_path_strict(input_path, self.output_dir)

    def test_pdf_uses_150_dpi_and_enforces_page_and_total_pixel_limits(self):
        input_path = self.input_dir / "attachment.bin"
        input_path.write_bytes(b"pdf")
        normal_output = self.output_dir / "normal"
        page_limit_output = self.output_dir / "page-limit"
        total_limit_output = self.output_dir / "total-limit"
        normal_output.mkdir()
        page_limit_output.mkdir()
        total_limit_output.mkdir()
        matrix_calls = []

        def matrix(scale_x, scale_y):
            matrix_calls.append((scale_x, scale_y))
            return (scale_x, scale_y)

        normal_page = _FakePage()
        with patch("utils.pdf_utils.fitz.open", return_value=_FakeDocument([normal_page])), patch(
            "utils.pdf_utils.fitz.Matrix", side_effect=matrix
        ):
            pages = render_pdf_path_strict(input_path, normal_output, dpi=150)

        self.assertEqual(len(pages), 1)
        self.assertAlmostEqual(matrix_calls[0][0], 150 / 72.0)
        self.assertAlmostEqual(matrix_calls[0][1], 150 / 72.0)

        page_scale = 150 / 72.0
        page_over = _FakePage(
            width=(MAX_PDF_PAGE_PIXELS + 1) / page_scale,
            height=1 / page_scale,
        )
        with patch("utils.pdf_utils.fitz.open", return_value=_FakeDocument([page_over])):
            with self.assertRaisesRegex(StrictPdfError, "PDF_PAGE_PIXEL_LIMIT"):
                render_pdf_path_strict(input_path, page_limit_output, dpi=150)

        each_pixels = MAX_PDF_TOTAL_PIXELS // 8 + 1
        total_pages = [
            _FakePage(width=each_pixels / page_scale, height=1 / page_scale)
            for _ in range(8)
        ]
        with patch(
            "utils.pdf_utils.fitz.open", return_value=_FakeDocument(total_pages)
        ):
            with self.assertRaisesRegex(StrictPdfError, "PDF_TOTAL_PIXEL_LIMIT"):
                render_pdf_path_strict(input_path, total_limit_output, dpi=150)

    def test_worker_rejects_declared_pdf_page_count_mismatch(self):
        (self.input_dir / "attachment.bin").write_bytes(b"pdf")
        rendered = [
            type(
                "RenderedPage",
                (),
                {
                    "page_number": 1,
                    "relative_path": "page-0001.jpg",
                    "sha256": "a" * 64,
                },
            )()
        ]

        with patch(
            "infrastructure.attachments.attachment_parser_worker.render_pdf_path_strict",
            return_value=rendered,
        ):
            with self.assertRaisesRegex(
                AttachmentParserError, "ATTACHMENT_PAGE_COUNT_MISMATCH"
            ):
                parse_attachment_file(
                    self._request(
                        file_type="pdf",
                        mime_type="application/pdf",
                        declared_page_count=2,
                    ),
                    self.input_dir,
                    self.output_dir,
                )

    def test_bundle_rejects_cumulative_multi_file_output_before_host_write(self):
        from infrastructure.attachments.attachment_parser_worker import (
            _write_output_bundle,
        )
        from infrastructure.attachments.parser_protocol import (
            WorkerManifest,
            WorkerPageManifest,
        )

        tmpfs_output = self.output_dir / "tmpfs"
        host_bundle = self.output_dir / "output.bundle"
        tmpfs_output.mkdir()
        host_bundle.touch(mode=0o600)
        first = tmpfs_output / "page-0001.jpg"
        second = tmpfs_output / "page-0002.jpg"
        first.write_bytes(b"a" * 6)
        second.write_bytes(b"b" * 6)
        first.chmod(0o600)
        second.chmod(0o600)
        manifest = WorkerManifest((
            WorkerPageManifest(1, first.name, hashlib.sha256(first.read_bytes()).hexdigest()),
            WorkerPageManifest(2, second.name, hashlib.sha256(second.read_bytes()).hexdigest()),
        ))

        with patch(
            "infrastructure.attachments.attachment_parser_worker._MAX_OUTPUT_TOTAL_BYTES",
            10,
        ):
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_LIMIT",
            ):
                _write_output_bundle(manifest, tmpfs_output, host_bundle)

        self.assertEqual(host_bundle.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
