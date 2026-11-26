"""Regression checks for backend configuration and PDF attachment rendering."""
import base64
import io
import os
import unittest
from unittest.mock import patch

from PIL import Image

from infrastructure.api.backend_client import BackendAPIClient
from utils.pdf_utils import pdf_bytes_to_images


class BackendConfigurationTests(unittest.TestCase):
    def test_requires_explicit_backend_configuration(self):
        with patch.dict(os.environ, {"BACKEND_API_URL": "", "BACKEND_API_TOKEN": ""}):
            with self.assertRaisesRegex(ValueError, "BACKEND_API_URL"):
                BackendAPIClient()

    def test_uses_configured_endpoint_and_token(self):
        with patch.dict(os.environ, {
            "BACKEND_API_URL": "http://localhost:8081/",
            "BACKEND_API_TOKEN": "example-token",
        }):
            client = BackendAPIClient()
            try:
                self.assertEqual(client.BASE_URL, "http://localhost:8081")
                self.assertEqual(client.session.headers["Agent-Token"], "example-token")
            finally:
                client.session.close()


class PdfRenderingTests(unittest.TestCase):
    def test_renders_pages_and_respects_limit(self):
        with Image.new("RGB", (72, 72), "white") as first, \
             Image.new("RGB", (72, 72), "red") as second, io.BytesIO() as source:
            first.save(source, format="PDF", save_all=True, append_images=[second], resolution=72)
            pdf = source.getvalue()
        self.assertEqual(pdf_bytes_to_images(b""), [])
        pages = pdf_bytes_to_images(pdf, max_pages=1, dpi=72)
        self.assertEqual([(p["page"], p["mime_type"]) for p in pages], [(1, "image/jpeg")])
        with Image.open(io.BytesIO(base64.b64decode(pages[0]["base64"]))) as image:
            self.assertEqual((image.format, image.size), ("JPEG", (72, 72)))
        self.assertEqual([p["page"] for p in pdf_bytes_to_images(pdf, dpi=72)], [1, 2])

    def test_rejects_invalid_pdf(self):
        with self.assertLogs("utils.pdf_utils", level="ERROR"):
            with self.assertRaises(RuntimeError):
                pdf_bytes_to_images(b"not a PDF")


if __name__ == "__main__":
    unittest.main()
