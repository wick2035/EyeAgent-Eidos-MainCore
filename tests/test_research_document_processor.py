import asyncio
import hashlib
import inspect
import unittest
from dataclasses import replace

from application.services.research_document_processor import (
    PDF_OCR_PROMPT_ID,
    RESEARCH_IMAGE_PROMPT_ID,
    ResearchDocumentProcessingError,
    ResearchDocumentProcessor,
    ResearchVisionGateway,
)
from infrastructure.attachments.parser_protocol import (
    ParsedAttachment,
    ParsedAttachmentPage,
    ParsedResearchPdf,
    ParsedResearchPdfPage,
)
from domain.models.research_document import ExtractedResearchText


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pdf_page(page_number, text, image=None):
    text_bytes = text.encode("utf-8")
    return ParsedResearchPdfPage(
        page_number=page_number,
        text=text,
        text_sha256=_digest(text_bytes),
        ocr_image_content=image,
        ocr_image_sha256=_digest(image) if image is not None else None,
    )


def _parsed_pdf(*pages):
    return ParsedResearchPdf(
        attachment_id="attachment-1",
        document_version=1,
        mime_type="application/pdf",
        pages=tuple(pages),
    )


def _parsed_image(content=b"validated-image"):
    return ParsedAttachment(
        attachment_id="attachment-1",
        file_type="image",
        mime_type="image/png",
        pages=(
            ParsedAttachmentPage(
                page_number=1,
                mime_type="image/png",
                sha256=_digest(content),
                content=content,
            ),
        ),
    )


def _downloaded(file_type, mime_type, *, content=b"validated-image"):
    return {
        "attachment_id": "attachment-1",
        "document_version": 1,
        "content_sha256": _digest(content),
        "file_type": file_type,
        "mime_type": mime_type,
    }


class FakeSandbox:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    async def parse(self, downloaded, profile="assistant_visual_v1"):
        self.calls.append((downloaded, profile))
        return self.parsed


class FakeGateway:
    def __init__(self, outputs=()):
        self.outputs = list(outputs)
        self.calls = []

    async def invoke(self, prompt_id, mime_type, image_content):
        self.calls.append((prompt_id, mime_type, image_content))
        output = self.outputs.pop(0)
        if isinstance(output, BaseException):
            raise output
        return output


class FakePlainTextProcessor:
    def __init__(self, output):
        self.output = output
        self.calls = []

    async def process(self, downloaded):
        self.calls.append(downloaded)
        return self.output


class FakeModel:
    def __init__(self, output=None, error=None, delay=0, response_metadata=None):
        self.output = output
        self.error = error
        self.delay = delay
        self.response_metadata = response_metadata or {}
        self.messages = []

    async def ainvoke(self, messages):
        self.messages.append(messages)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return type(
            "Response",
            (),
            {
                "content": self.output,
                "response_metadata": self.response_metadata,
            },
        )()


class ResearchDocumentProcessorTest(unittest.IsolatedAsyncioTestCase):
    async def test_text_dispatches_to_plain_text_processor_without_vision(self):
        downloaded = _downloaded("text", "text/plain", content=b"raw text")
        extracted = ExtractedResearchText(
            text="规范化正文",
            text_sha256=_digest("规范化正文".encode("utf-8")),
            character_count=len("规范化正文"),
        )
        text_processor = FakePlainTextProcessor(extracted)
        gateway = FakeGateway()

        result = await ResearchDocumentProcessor(
            FakeSandbox(object()),
            gateway,
            plain_text_processor=text_processor,
        ).process(downloaded)

        self.assertEqual(result, extracted)
        self.assertEqual(text_processor.calls, [downloaded])
        self.assertEqual(gateway.calls, [])

    async def test_digital_pdf_uses_research_profile_without_llm(self):
        sandbox = FakeSandbox(_parsed_pdf(_pdf_page(1, "第一页"), _pdf_page(2, "第二页")))
        gateway = FakeGateway()
        processor = ResearchDocumentProcessor(sandbox, gateway)

        pages = await processor.process(
            _downloaded("pdf", "application/pdf")
        )

        self.assertEqual(sandbox.calls[0][1], "research_pdf_v1")
        self.assertEqual(gateway.calls, [])
        self.assertEqual(
            [(page.page_number, page.text, page.extraction_method) for page in pages],
            [(1, "第一页", "digital_text"), (2, "第二页", "digital_text")],
        )

    async def test_mixed_pdf_only_ocrs_artifact_pages_and_keeps_order(self):
        sandbox = FakeSandbox(
            _parsed_pdf(
                _pdf_page(1, "数字第一页"),
                _pdf_page(2, "low quality", b"page-2-image"),
                _pdf_page(3, "数字第三页"),
                _pdf_page(4, "low quality", b"page-4-image"),
            )
        )
        gateway = FakeGateway(["OCR 第二页", "OCR 第四页"])

        pages = await ResearchDocumentProcessor(sandbox, gateway).process(
            _downloaded("pdf", "application/pdf")
        )

        self.assertEqual(
            gateway.calls,
            [
                (PDF_OCR_PROMPT_ID, "image/jpeg", b"page-2-image"),
                (PDF_OCR_PROMPT_ID, "image/jpeg", b"page-4-image"),
            ],
        )
        self.assertEqual([page.page_number for page in pages], [1, 2, 3, 4])
        self.assertEqual(
            [page.extraction_method for page in pages],
            ["digital_text", "ocr", "digital_text", "ocr"],
        )
        self.assertEqual([page.text for page in pages], ["数字第一页", "OCR 第二页", "数字第三页", "OCR 第四页"])

    async def test_image_is_validated_by_assistant_sandbox_then_uses_research_prompt(self):
        parsed = _parsed_image()
        sandbox = FakeSandbox(parsed)
        gateway = FakeGateway(["独立科研图片描述"])

        pages = await ResearchDocumentProcessor(sandbox, gateway).process(
            _downloaded("image", "image/png")
        )

        self.assertEqual(sandbox.calls[0][1], "assistant_visual_v1")
        self.assertEqual(
            gateway.calls,
            [(RESEARCH_IMAGE_PROMPT_ID, "image/png", b"validated-image")],
        )
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].extraction_method, "vision")

    async def test_pdf_defensively_revalidates_pages_text_and_ocr_pairs(self):
        valid = _pdf_page(1, "数字页")
        malformed = [
            _parsed_pdf(replace(valid, page_number=2)),
            _parsed_pdf(replace(valid, text=object())),
            _parsed_pdf(replace(valid, text_sha256="0" * 64)),
            _parsed_pdf(replace(valid, ocr_image_content=b"image", ocr_image_sha256=None)),
            _parsed_pdf(replace(valid, ocr_image_content="image", ocr_image_sha256="0" * 64)),
        ]
        for parsed in malformed:
            with self.subTest(parsed=parsed):
                with self.assertRaises(ResearchDocumentProcessingError) as raised:
                    await ResearchDocumentProcessor(FakeSandbox(parsed), FakeGateway()).process(
                        _downloaded("pdf", "application/pdf")
                    )
                self.assertIn(
                    raised.exception.error_code,
                    {"RESEARCH_DOCUMENT_VISION_FAILED", "RESEARCH_DOCUMENT_CONTENT_LIMIT"},
                )

    async def test_pdf_defensively_revalidates_per_page_and_total_text_limits(self):
        oversized_page_text = "a" * (2 * 1024 * 1024 + 1)
        with self.assertRaises(ResearchDocumentProcessingError) as page_error:
            await ResearchDocumentProcessor(
                FakeSandbox(_parsed_pdf(_pdf_page(1, oversized_page_text))),
                FakeGateway(),
            ).process(_downloaded("pdf", "application/pdf"))
        self.assertEqual(page_error.exception.error_code, "RESEARCH_DOCUMENT_CONTENT_LIMIT")

        pages = tuple(_pdf_page(index + 1, "a" * (2 * 1024 * 1024)) for index in range(9))
        with self.assertRaises(ResearchDocumentProcessingError) as total_error:
            await ResearchDocumentProcessor(
                FakeSandbox(_parsed_pdf(*pages)),
                FakeGateway(),
            ).process(_downloaded("pdf", "application/pdf"))
        self.assertEqual(total_error.exception.error_code, "RESEARCH_DOCUMENT_CONTENT_LIMIT")

    async def test_processor_maps_unknown_gateway_failure_without_leaking_detail(self):
        gateway = FakeGateway([RuntimeError("provider secret response body")])

        with self.assertRaises(ResearchDocumentProcessingError) as raised:
            await ResearchDocumentProcessor(FakeSandbox(_parsed_image()), gateway).process(
                _downloaded("image", "image/png")
            )

        self.assertEqual(raised.exception.error_code, "RESEARCH_DOCUMENT_VISION_FAILED")
        self.assertNotIn("provider", str(raised.exception))
        self.assertNotIn("secret", repr(raised.exception))
        self.assertIsNone(raised.exception.__context__)
        self.assertIsNone(raised.exception.__cause__)

    async def test_processor_revalidates_fake_gateway_output_and_image_token_limit(self):
        cases = [
            ("", "RESEARCH_DOCUMENT_CONTENT_EMPTY"),
            (123, "RESEARCH_DOCUMENT_VISION_FAILED"),
            ("a" * (64 * 1024 + 1), "RESEARCH_DOCUMENT_CONTENT_LIMIT"),
            ("a" * 7501, "RESEARCH_DOCUMENT_CONTENT_LIMIT"),
        ]
        for output, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(ResearchDocumentProcessingError) as raised:
                    await ResearchDocumentProcessor(
                        FakeSandbox(_parsed_image()), FakeGateway([output])
                    ).process(_downloaded("image", "image/png"))
                self.assertEqual(raised.exception.error_code, code)

        accepted = await ResearchDocumentProcessor(
            FakeSandbox(_parsed_image()), FakeGateway(["a" * 7500])
        ).process(_downloaded("image", "image/png"))
        self.assertEqual(len(accepted[0].text), 7500)

    async def test_processor_rejects_sandbox_identity_or_version_mismatch(self):
        pdf_cases = [
            replace(_parsed_pdf(_pdf_page(1, "正文")), attachment_id="other"),
            replace(_parsed_pdf(_pdf_page(1, "正文")), document_version=2),
            replace(_parsed_pdf(_pdf_page(1, "正文")), mime_type="image/png"),
        ]
        for parsed in pdf_cases:
            with self.subTest(parsed=parsed):
                gateway = FakeGateway(["不应调用"])
                with self.assertRaises(ResearchDocumentProcessingError) as raised:
                    await ResearchDocumentProcessor(
                        FakeSandbox(parsed), gateway
                    ).process(_downloaded("pdf", "application/pdf"))
                self.assertEqual(
                    raised.exception.error_code,
                    "RESEARCH_DOCUMENT_VISION_FAILED",
                )
                self.assertEqual(gateway.calls, [])

        image_cases = [
            (
                replace(_parsed_image(), attachment_id="other"),
                _downloaded("image", "image/png"),
            ),
            (
                _parsed_image(b"other-content"),
                _downloaded("image", "image/png"),
            ),
            (
                _parsed_image(),
                {
                    **_downloaded("image", "image/png"),
                    "document_version": 0,
                },
            ),
        ]
        for parsed, downloaded in image_cases:
            with self.subTest(parsed=parsed, downloaded=downloaded):
                gateway = FakeGateway(["不应调用"])
                with self.assertRaises(ResearchDocumentProcessingError) as raised:
                    await ResearchDocumentProcessor(
                        FakeSandbox(parsed), gateway
                    ).process(downloaded)
                self.assertEqual(
                    raised.exception.error_code,
                    "RESEARCH_DOCUMENT_VISION_FAILED",
                )
                self.assertEqual(gateway.calls, [])


class ResearchVisionGatewayTest(unittest.IsolatedAsyncioTestCase):
    async def test_only_fixed_research_prompt_ids_are_allowed(self):
        model = FakeModel("结果")
        gateway = ResearchVisionGateway(model_factory=lambda: model)

        for prompt_id in (PDF_OCR_PROMPT_ID, RESEARCH_IMAGE_PROMPT_ID):
            self.assertEqual(
                await gateway.invoke(prompt_id, "image/png", b"image"),
                "结果",
            )
        with self.assertRaises(ResearchDocumentProcessingError) as raised:
            await gateway.invoke("caller-supplied-prompt", "image/png", b"image")
        self.assertEqual(raised.exception.error_code, "RESEARCH_DOCUMENT_VISION_FAILED")
        prompts = [call[0].content[-1]["text"] for call in model.messages]
        self.assertNotEqual(prompts[0], prompts[1])
        self.assertTrue(all("科研" in prompt for prompt in prompts))

    async def test_gateway_timeout_exception_empty_nonstring_and_64k_limit(self):
        cases = [
            (FakeModel("ok", delay=0.03), 0.001, "RESEARCH_DOCUMENT_VISION_TIMEOUT"),
            (FakeModel(error=RuntimeError("provider detail")), 1, "RESEARCH_DOCUMENT_VISION_FAILED"),
            (FakeModel("   \n"), 1, "RESEARCH_DOCUMENT_CONTENT_EMPTY"),
            (FakeModel(["not", "string"]), 1, "RESEARCH_DOCUMENT_VISION_FAILED"),
            (FakeModel("\ud800"), 1, "RESEARCH_DOCUMENT_VISION_FAILED"),
            (FakeModel("a" * (64 * 1024 + 1)), 1, "RESEARCH_DOCUMENT_CONTENT_LIMIT"),
            (
                FakeModel("partial", response_metadata={"finish_reason": "length"}),
                1,
                "RESEARCH_DOCUMENT_CONTENT_LIMIT",
            ),
        ]
        for model, timeout, code in cases:
            with self.subTest(code=code):
                gateway = ResearchVisionGateway(
                    model_factory=lambda model=model: model,
                    timeout_seconds=timeout,
                )
                with self.assertRaises(ResearchDocumentProcessingError) as raised:
                    await gateway.invoke(PDF_OCR_PROMPT_ID, "image/jpeg", b"image")
                self.assertEqual(raised.exception.error_code, code)
                self.assertEqual(str(raised.exception), code)

        accepted = await ResearchVisionGateway(
            model_factory=lambda: FakeModel("a" * (64 * 1024))
        ).invoke(PDF_OCR_PROMPT_ID, "image/jpeg", b"image")
        self.assertEqual(len(accepted), 64 * 1024)

    async def test_gateway_does_not_chain_provider_exception_details(self):
        gateway = ResearchVisionGateway(
            model_factory=lambda: FakeModel(
                error=RuntimeError("provider secret response body")
            )
        )

        with self.assertRaises(ResearchDocumentProcessingError) as raised:
            await gateway.invoke(PDF_OCR_PROMPT_ID, "image/jpeg", b"image")

        self.assertEqual(
            raised.exception.error_code,
            "RESEARCH_DOCUMENT_VISION_FAILED",
        )
        self.assertIsNone(raised.exception.__context__)
        self.assertIsNone(raised.exception.__cause__)

    def test_processor_does_not_import_legacy_medical_prompts(self):
        source = inspect.getsource(
            __import__(
                "application.services.research_document_processor",
                fromlist=["*"],
            )
        )
        self.assertNotIn("utils.attachment_analyzer", source)
        self.assertNotIn("_IMAGE_ANALYSIS_PROMPT", source)
        self.assertNotIn("_PDF_ANALYSIS_PROMPT", source)


if __name__ == "__main__":
    unittest.main()
