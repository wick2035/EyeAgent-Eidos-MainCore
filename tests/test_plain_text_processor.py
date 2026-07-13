import hashlib
import unittest
from dataclasses import replace

from application.services.plain_text_processor import (
    PlainTextProcessingError,
    PlainTextProcessor,
)
from domain.models.research_document import ExtractedResearchText
from infrastructure.attachments.parser_protocol import ParsedResearchText


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _downloaded(*, content_sha256: str) -> dict:
    return {
        "attachment_id": "attachment-1",
        "document_version": 7,
        "content_sha256": content_sha256,
        "file_type": "text",
        "mime_type": "text/plain",
    }


def _parsed(text: str = "Caf\u00e9\nline") -> ParsedResearchText:
    encoded = text.encode("utf-8")
    return ParsedResearchText(
        attachment_id="attachment-1",
        document_version=7,
        mime_type="text/plain",
        text=text,
        text_sha256=_digest(encoded),
        character_count=len(text),
    )


class FakeSandbox:
    def __init__(self, output):
        self.output = output
        self.calls = []

    async def parse(self, downloaded, profile="assistant_visual_v1"):
        self.calls.append((downloaded, profile))
        if isinstance(self.output, BaseException):
            raise self.output
        return self.output


class PlainTextProcessorTest(unittest.IsolatedAsyncioTestCase):
    async def test_uses_fixed_profile_and_validates_normalized_text_not_raw_hash(self):
        raw_content = b"\xef\xbb\xbfCafe\xcc\x81\r\nline"
        parsed = _parsed()
        downloaded = _downloaded(content_sha256=_digest(raw_content))
        self.assertNotEqual(downloaded["content_sha256"], parsed.text_sha256)
        sandbox = FakeSandbox(parsed)

        result = await PlainTextProcessor(sandbox).process(downloaded)

        self.assertEqual(sandbox.calls, [(downloaded, "research_text_v1")])
        self.assertIsInstance(result, ExtractedResearchText)
        self.assertEqual(result.text, "Caf\u00e9\nline")
        self.assertEqual(result.text_sha256, _digest(result.text.encode("utf-8")))
        self.assertEqual(result.character_count, len(result.text))

    async def test_rejects_non_text_parse_identity_mime_hash_and_count(self):
        parsed = _parsed()
        malformed = (
            object(),
            replace(parsed, attachment_id="other"),
            replace(parsed, document_version=8),
            replace(parsed, mime_type="application/pdf"),
            replace(parsed, text_sha256="0" * 64),
            replace(parsed, character_count=parsed.character_count + 1),
            replace(parsed, text=""),
        )
        downloaded = _downloaded(content_sha256=_digest(b"raw-bytes"))

        for output in malformed:
            with self.subTest(output=output):
                with self.assertRaises(PlainTextProcessingError) as raised:
                    await PlainTextProcessor(FakeSandbox(output)).process(downloaded)
                self.assertEqual(
                    raised.exception.error_code,
                    "RESEARCH_TXT_PARSE_FAILED",
                )

    async def test_unknown_sandbox_failure_is_stable_and_does_not_leak_detail(self):
        downloaded = _downloaded(content_sha256=_digest(b"raw-bytes"))

        with self.assertRaises(PlainTextProcessingError) as raised:
            await PlainTextProcessor(
                FakeSandbox(RuntimeError("private bundle path and worker detail"))
            ).process(downloaded)

        self.assertEqual(raised.exception.error_code, "RESEARCH_TXT_PARSE_FAILED")
        self.assertEqual(str(raised.exception), "RESEARCH_TXT_PARSE_FAILED")
        self.assertNotIn("private", repr(raised.exception))
        self.assertIsNone(raised.exception.__context__)
        self.assertIsNone(raised.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
