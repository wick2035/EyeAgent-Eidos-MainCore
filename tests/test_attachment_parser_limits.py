import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from infrastructure.attachments.attachment_parser_worker import (
    parse_attachment_file,
)
from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    WorkerRequest,
)
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
    def __init__(self, width=612, height=792):
        self.rect = type("Rect", (), {"width": width, "height": height})()
        self.matrix = None

    def get_pixmap(self, *, matrix, alpha):
        self.matrix = matrix
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


if __name__ == "__main__":
    unittest.main()
