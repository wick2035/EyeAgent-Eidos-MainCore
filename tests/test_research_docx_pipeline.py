import hashlib
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from application.services.research_document_context_selector import (
    _validate_segment_sources,
)
from application.services.research_document_ingestion_service import (
    DOCX_EXTRACTOR_VERSION,
    _build_identity,
    _validate_metadata,
)
from application.services.research_document_segmenter import (
    SEGMENT_SCHEMA_VERSION,
    ResearchDocumentSegmenter,
)
from domain.models.research_document import (
    ExtractedResearchText,
    ResearchDocumentIngestionEntity,
    build_research_document_ingestion_id,
)
from infrastructure.attachments.secure_downloader import (
    DownloadedAttachment,
    _matches_magic,
    _docx_magic_error,
    _safe_suffix,
)


DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


class ResearchDocxPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "paper.docx"
        self.path.write_bytes(b"PK\x03\x04docx")

    def tearDown(self):
        self.temporary.cleanup()

    def _downloaded(self, **overrides):
        values = {
            "attachment_id": "attachment-docx",
            "analysis_attempt_id": "attempt-docx",
            "file_type": "docx",
            "filename": "paper.docx",
            "mime_type": DOCX_MIME,
            "size_bytes": self.path.stat().st_size,
            "content_sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
            "page_count": None,
            "path": self.path,
            "document_version": 1,
        }
        values.update(overrides)
        return DownloadedAttachment(**values)

    def test_downloader_suffix_magic_and_ingestion_identity_are_docx_specific(self):
        item = self._downloaded()

        self.assertEqual(_safe_suffix(DOCX_MIME), ".docx")
        self.assertTrue(_matches_magic(self.path, DOCX_MIME))
        self.assertEqual(_validate_metadata("doctor-1", [item]), (item,))
        identity = _build_identity("doctor-1", item)
        self.assertEqual(identity.processor_type, "docx_text_v1")
        self.assertEqual(identity.extractor_version, DOCX_EXTRACTOR_VERSION)

        self.path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1encrypted")
        self.assertEqual(_docx_magic_error(self.path), "RESEARCH_DOCX_ENCRYPTED")

    def test_metadata_rejects_docx_wrong_mime_page_and_size(self):
        for item in (
            self._downloaded(mime_type="application/zip"),
            self._downloaded(page_count=1),
            self._downloaded(size_bytes=10 * 1024 * 1024 + 1),
        ):
            with self.subTest(item=item):
                with self.assertRaises(Exception):
                    _validate_metadata("doctor-1", [item])

    def test_docx_segments_use_file_locator_compatible_metadata(self):
        item = self._downloaded()
        identity = _build_identity("doctor-1", item)
        ingestion_id = build_research_document_ingestion_id(identity)
        text = "标题\n\n表头A\t表头B\n值A\t值B"
        extracted = ExtractedResearchText(
            text=text,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            character_count=len(text),
        )

        segments = ResearchDocumentSegmenter().segment(
            ingestion_id,
            extracted,
            processor_type="docx_text_v1",
        )
        entity = ResearchDocumentIngestionEntity(
            id=ingestion_id,
            doctor_id="doctor-1",
            attachment_id=item.attachment_id,
            document_version=1,
            content_sha256=item.content_sha256,
            processor_type="docx_text_v1",
            extractor_version=DOCX_EXTRACTOR_VERSION,
            segment_schema_version=SEGMENT_SCHEMA_VERSION,
            status="ready",
            attempt_count=1,
            page_count=0,
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )

        _validate_segment_sources(entity, segments)
        self.assertTrue(segments)
        self.assertTrue(all(segment.page_start is None for segment in segments))
        self.assertEqual(
            segments[0].metadata,
            {
                "block_index": 0,
                "extraction_method": "docx_xml",
                "extraction_mode": "text",
            },
        )


if __name__ == "__main__":
    unittest.main()
