import hashlib
import unittest

from application.services.docx_processor import (
    DocxProcessingError,
    DocxProcessor,
)
from infrastructure.attachments.parser_protocol import ParsedResearchDocx
from infrastructure.attachments.parser_protocol import AttachmentParserError


DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


class Sandbox:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def parse(self, downloaded, profile):
        self.calls.append((downloaded, profile))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class DocxProcessorTest(unittest.IsolatedAsyncioTestCase):
    async def test_processes_only_validated_docx_text(self):
        text = "标题\n\nA\tB"
        parsed = ParsedResearchDocx(
            attachment_id="attachment-1",
            document_version=1,
            mime_type=DOCX_MIME,
            text=text,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            character_count=len(text),
        )
        sandbox = Sandbox(parsed)
        downloaded = {
            "attachment_id": "attachment-1",
            "document_version": 1,
            "file_type": "docx",
            "mime_type": DOCX_MIME,
        }

        result = await DocxProcessor(sandbox).process(downloaded)

        self.assertEqual(result.text, text)
        self.assertEqual(sandbox.calls, [(downloaded, "research_docx_v1")])

    async def test_rejects_identity_hash_and_unknown_failures(self):
        text = "正文"
        valid = ParsedResearchDocx(
            attachment_id="other",
            document_version=1,
            mime_type=DOCX_MIME,
            text=text,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            character_count=len(text),
        )
        downloaded = {
            "attachment_id": "attachment-1",
            "document_version": 1,
            "file_type": "docx",
            "mime_type": DOCX_MIME,
        }
        for result in (valid, RuntimeError("secret")):
            with self.subTest(result=result):
                with self.assertRaises(DocxProcessingError) as raised:
                    await DocxProcessor(Sandbox(result)).process(downloaded)
                self.assertEqual(
                    raised.exception.error_code,
                    "RESEARCH_DOCX_PARSE_FAILED",
                )

    async def test_preserves_only_stable_docx_parser_error_codes(self):
        downloaded = {
            "attachment_id": "attachment-1",
            "document_version": 1,
            "file_type": "docx",
            "mime_type": DOCX_MIME,
        }
        for error_code in (
            "RESEARCH_DOCX_INVALID",
            "RESEARCH_DOCX_ENCRYPTED",
            "RESEARCH_DOCX_STRUCTURE_LIMIT",
            "RESEARCH_DOCX_CONTENT_LIMIT",
            "RESEARCH_DOCX_SIZE_LIMIT",
        ):
            with self.subTest(error_code=error_code):
                with self.assertRaises(DocxProcessingError) as raised:
                    await DocxProcessor(
                        Sandbox(AttachmentParserError(error_code))
                    ).process(downloaded)
                self.assertEqual(raised.exception.error_code, error_code)

        with self.assertRaises(DocxProcessingError) as unknown:
            await DocxProcessor(
                Sandbox(AttachmentParserError("ATTACHMENT_WORKER_FAILED"))
            ).process(downloaded)
        self.assertEqual(unknown.exception.error_code, "RESEARCH_DOCX_PARSE_FAILED")


if __name__ == "__main__":
    unittest.main()
