import asyncio
import base64
import hashlib
import math
import os
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from application.services.plain_text_processor import PlainTextProcessor
from application.services.research_document_segmenter import (
    MAX_SEGMENT_TOKENS,
    estimate_tokens_v1,
)
from domain.models.research_document import (
    ExtractedResearchPage,
    ExtractedResearchText,
)
from infrastructure.attachments.parser_protocol import (
    ParsedAttachment,
    ParsedAttachmentPage,
    ParsedResearchPdf,
    ParsedResearchPdfPage,
)
from utils.pdf_utils import (
    RESEARCH_PDF_MAX_OCR_PAGES,
    RESEARCH_PDF_MAX_PAGES,
    RESEARCH_PDF_MAX_TEXT_BYTES_PER_PAGE,
    RESEARCH_PDF_MAX_TEXT_BYTES_TOTAL,
)


PDF_OCR_PROMPT_ID = "research-pdf-page-ocr-v1"
RESEARCH_IMAGE_PROMPT_ID = "research-image-analysis-v1"

_MAX_VISION_OUTPUT_BYTES = 64 * 1024
_STABLE_ERROR_CODES = frozenset(
    {
        "RESEARCH_DOCUMENT_VISION_TIMEOUT",
        "RESEARCH_DOCUMENT_VISION_FAILED",
        "RESEARCH_DOCUMENT_CONTENT_EMPTY",
        "RESEARCH_DOCUMENT_CONTENT_LIMIT",
    }
)
_ALLOWED_IMAGE_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_PROMPTS = {
    PDF_OCR_PROMPT_ID: (
        "你是科研文档逐页 OCR 助手。请忠实转写这张科研 PDF 页面中的全部可见文字，"
        "保留标题、段落、列表、表格行列关系、公式符号与单位；不要诊断、总结、补写或猜测。"
        "无法辨认的局部使用[无法辨认]，只输出本页转写正文。"
    ),
    RESEARCH_IMAGE_PROMPT_ID: (
        "你是科研资料图像分析助手。请客观描述图片中与科研分析有关的可见信息，忠实转写"
        "文字、标签、图例、坐标、单位和数值，并说明图表、实验材料或报告版式的结构。"
        "不要进行临床诊断，不要补造不可见事实，只输出可作为科研文档上下文的正文。"
    ),
}


class ResearchDocumentProcessingError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        if error_code not in _STABLE_ERROR_CODES:
            raise ValueError("不允许的科研文档处理错误码")
        super().__init__(error_code)
        self.error_code = error_code


class ResearchVisionGateway:
    """仅接受固定科研 prompt ID 的视觉模型边界。"""

    def __init__(
        self,
        *,
        model_factory: Callable[[], Any] | None = None,
        timeout_seconds: float = 90.0,
    ) -> None:
        if (
            type(timeout_seconds) not in {int, float}
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds 必须为正数")
        self._model_factory = model_factory or _create_research_vision_model
        self._timeout_seconds = float(timeout_seconds)

    async def invoke(
        self,
        prompt_id: str,
        mime_type: str,
        image_content: bytes,
    ) -> str:
        prompt = _PROMPTS.get(prompt_id)
        if (
            prompt is None
            or mime_type not in _ALLOWED_IMAGE_MIME_TYPES
            or not isinstance(image_content, bytes)
            or not image_content
        ):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )

        encoded = base64.b64encode(image_content).decode("ascii")
        message = HumanMessage(
            content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded}",
                    },
                },
                {"type": "text", "text": prompt},
            ]
        )
        failure_code: str | None = None
        try:
            model = self._model_factory()
            response = await asyncio.wait_for(
                model.ainvoke([message]),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            failure_code = "RESEARCH_DOCUMENT_VISION_TIMEOUT"
        except asyncio.CancelledError:
            raise
        except ResearchDocumentProcessingError:
            raise
        except Exception:
            failure_code = "RESEARCH_DOCUMENT_VISION_FAILED"
        if failure_code is not None:
            raise ResearchDocumentProcessingError(failure_code)

        response_read_failed = False
        try:
            content = getattr(response, "content", None)
            response_metadata = getattr(response, "response_metadata", None)
        except Exception:
            response_read_failed = True
        if response_read_failed:
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )
        if _response_was_truncated(response_metadata):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_CONTENT_LIMIT"
            )
        return _validate_vision_output(
            content,
            enforce_segment_limit=prompt_id == RESEARCH_IMAGE_PROMPT_ID,
        )


class ResearchDocumentProcessor:
    def __init__(
        self,
        sandbox: Any,
        vision_gateway: Any | None = None,
        *,
        plain_text_processor: Any | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._vision_gateway = vision_gateway or ResearchVisionGateway()
        self._plain_text_processor = plain_text_processor or PlainTextProcessor(
            sandbox
        )

    async def process(
        self,
        downloaded: Any,
    ) -> list[ExtractedResearchPage] | ExtractedResearchText:
        file_type = _value(downloaded, "file_type")
        if file_type == "pdf":
            return await self.process_pdf(downloaded)
        if file_type == "image":
            return await self.process_image(downloaded)
        if file_type == "text":
            return await self._plain_text_processor.process(downloaded)
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_VISION_FAILED")

    async def process_pdf(
        self,
        downloaded: Any,
    ) -> list[ExtractedResearchPage]:
        identity = _downloaded_identity(downloaded, expected_file_type="pdf")
        parsed = await self._sandbox.parse(
            downloaded,
            profile="research_pdf_v1",
        )
        if not isinstance(parsed, ParsedResearchPdf):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )
        if (
            parsed.attachment_id != identity[0]
            or parsed.document_version != identity[1]
            or parsed.mime_type != identity[2]
        ):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )
        validated_pages = _validate_pdf_pages(parsed)

        extracted: list[ExtractedResearchPage] = []
        for page in validated_pages:
            if page.ocr_image_content is None:
                text = page.text
                method = "digital_text"
            else:
                text = await self._invoke_vision(
                    PDF_OCR_PROMPT_ID,
                    "image/jpeg",
                    page.ocr_image_content,
                )
                method = "ocr"
            extracted.append(
                ExtractedResearchPage(
                    page_number=page.page_number,
                    text=text,
                    extraction_method=method,
                )
            )
        return extracted

    async def process_image(
        self,
        downloaded: Any,
    ) -> list[ExtractedResearchPage]:
        identity = _downloaded_identity(downloaded, expected_file_type="image")
        parsed = await self._sandbox.parse(
            downloaded,
            profile="assistant_visual_v1",
        )
        page = _validate_image_parse(
            parsed,
            expected_attachment_id=identity[0],
            expected_mime_type=identity[2],
            expected_content_sha256=identity[3],
        )
        text = await self._invoke_vision(
            RESEARCH_IMAGE_PROMPT_ID,
            page.mime_type,
            page.content,
        )
        return [
            ExtractedResearchPage(
                page_number=1,
                text=text,
                extraction_method="vision",
            )
        ]

    async def _invoke_vision(
        self,
        prompt_id: str,
        mime_type: str,
        image_content: bytes,
    ) -> str:
        gateway_failed = False
        try:
            content = await self._vision_gateway.invoke(
                prompt_id,
                mime_type,
                image_content,
            )
        except asyncio.CancelledError:
            raise
        except ResearchDocumentProcessingError:
            raise
        except Exception:
            gateway_failed = True
        if gateway_failed:
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )
        return _validate_vision_output(
            content,
            enforce_segment_limit=prompt_id == RESEARCH_IMAGE_PROMPT_ID,
        )


def _validate_pdf_pages(parsed: ParsedResearchPdf) -> tuple[Any, ...]:
    pages = parsed.pages
    if (
        parsed.mime_type != "application/pdf"
        or type(parsed.document_version) is not int
        or parsed.document_version < 1
        or not isinstance(pages, tuple)
    ):
        raise ResearchDocumentProcessingError(
            "RESEARCH_DOCUMENT_VISION_FAILED"
        )
    if not pages:
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_CONTENT_EMPTY")
    if len(pages) > RESEARCH_PDF_MAX_PAGES:
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_CONTENT_LIMIT")

    total_text_bytes = 0
    ocr_page_count = 0
    for expected_page_number, page in enumerate(pages, start=1):
        if (
            not isinstance(page, ParsedResearchPdfPage)
            or type(page.page_number) is not int
            or page.page_number != expected_page_number
        ):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )
        if not isinstance(page.text, str):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )
        text_bytes = page.text.encode("utf-8")
        if (
            len(text_bytes) > RESEARCH_PDF_MAX_TEXT_BYTES_PER_PAGE
            or total_text_bytes + len(text_bytes)
            > RESEARCH_PDF_MAX_TEXT_BYTES_TOTAL
        ):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_CONTENT_LIMIT"
            )
        total_text_bytes += len(text_bytes)
        if not _matches_sha256(text_bytes, page.text_sha256):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )

        image_content = page.ocr_image_content
        image_sha256 = page.ocr_image_sha256
        if (image_content is None) != (image_sha256 is None):
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_VISION_FAILED"
            )
        if image_content is not None:
            if (
                not isinstance(image_content, bytes)
                or not image_content
                or not _matches_sha256(image_content, image_sha256)
            ):
                raise ResearchDocumentProcessingError(
                    "RESEARCH_DOCUMENT_VISION_FAILED"
                )
            ocr_page_count += 1
            if ocr_page_count > RESEARCH_PDF_MAX_OCR_PAGES:
                raise ResearchDocumentProcessingError(
                    "RESEARCH_DOCUMENT_CONTENT_LIMIT"
                )
        elif not page.text.strip():
            raise ResearchDocumentProcessingError(
                "RESEARCH_DOCUMENT_CONTENT_EMPTY"
            )
    return pages


def _validate_image_parse(
    parsed: Any,
    *,
    expected_attachment_id: str,
    expected_mime_type: str,
    expected_content_sha256: str,
) -> Any:
    if (
        not isinstance(parsed, ParsedAttachment)
        or parsed.attachment_id != expected_attachment_id
        or parsed.file_type != "image"
        or parsed.mime_type != expected_mime_type
        or parsed.mime_type not in _ALLOWED_IMAGE_MIME_TYPES
        or not isinstance(parsed.pages, tuple)
        or len(parsed.pages) != 1
    ):
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_VISION_FAILED")
    page = parsed.pages[0]
    if (
        not isinstance(page, ParsedAttachmentPage)
        or type(page.page_number) is not int
        or page.page_number != 1
        or page.mime_type != parsed.mime_type
        or page.mime_type not in _ALLOWED_IMAGE_MIME_TYPES
        or not isinstance(page.content, bytes)
        or not page.content
        or not _matches_sha256(page.content, page.sha256)
        or page.sha256 != expected_content_sha256
    ):
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_VISION_FAILED")
    return page


def _validate_vision_output(
    content: Any,
    *,
    enforce_segment_limit: bool,
) -> str:
    if not isinstance(content, str):
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_VISION_FAILED")
    if not content.strip():
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_CONTENT_EMPTY")
    encoding_failed = False
    try:
        content_bytes = content.encode("utf-8")
    except UnicodeEncodeError:
        encoding_failed = True
    if encoding_failed:
        raise ResearchDocumentProcessingError(
            "RESEARCH_DOCUMENT_VISION_FAILED"
        )
    if len(content_bytes) > _MAX_VISION_OUTPUT_BYTES:
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_CONTENT_LIMIT")
    if enforce_segment_limit and estimate_tokens_v1(content) > MAX_SEGMENT_TOKENS:
        raise ResearchDocumentProcessingError("RESEARCH_DOCUMENT_CONTENT_LIMIT")
    return content


def _matches_sha256(content: bytes, expected: Any) -> bool:
    return (
        isinstance(expected, str)
        and len(expected) == 64
        and hashlib.sha256(content).hexdigest() == expected
    )


def _downloaded_identity(
    downloaded: Any,
    *,
    expected_file_type: str,
) -> tuple[str, int, str, str]:
    attachment_id = _value(downloaded, "attachment_id")
    document_version = _value(downloaded, "document_version")
    content_sha256 = _value(downloaded, "content_sha256")
    file_type = _value(downloaded, "file_type")
    mime_type = _value(downloaded, "mime_type")
    expected_mime_types = (
        {"application/pdf"}
        if expected_file_type == "pdf"
        else _ALLOWED_IMAGE_MIME_TYPES
    )
    if (
        not isinstance(attachment_id, str)
        or not attachment_id
        or type(document_version) is not int
        or document_version < 1
        or not isinstance(content_sha256, str)
        or len(content_sha256) != 64
        or any(character not in "0123456789abcdef" for character in content_sha256)
        or file_type != expected_file_type
        or mime_type not in expected_mime_types
    ):
        raise ResearchDocumentProcessingError(
            "RESEARCH_DOCUMENT_VISION_FAILED"
        )
    return attachment_id, document_version, mime_type, content_sha256


def _response_was_truncated(response_metadata: Any) -> bool:
    if not isinstance(response_metadata, dict):
        return False
    finish_reason = response_metadata.get("finish_reason")
    return finish_reason in {"length", "max_tokens", "max_output_tokens"}


def _value(item: Any, name: str) -> Any:
    missing = object()
    lookup_failed = False
    try:
        value = item.get(name, missing) if isinstance(item, dict) else getattr(
            item,
            name,
            missing,
        )
    except (KeyError, AttributeError, TypeError):
        lookup_failed = True
        value = missing
    if lookup_failed or value is missing:
        raise ResearchDocumentProcessingError(
            "RESEARCH_DOCUMENT_VISION_FAILED"
        )
    return value


def _create_research_vision_model() -> ChatOpenAI:
    api_key = os.getenv("SILICON_FLOW_API_KEY")
    if not api_key:
        raise RuntimeError("research vision model unavailable")
    return ChatOpenAI(
        model=os.getenv(
            "RESEARCH_VISION_MODEL",
            "Qwen/Qwen3.5-397B-A17B",
        ),
        openai_api_key=api_key,
        openai_api_base=os.getenv(
            "RESEARCH_VISION_BASE_URL",
            "https://api.siliconflow.cn/v1",
        ),
        temperature=0.0,
        max_tokens=32768,
    )


__all__ = [
    "PDF_OCR_PROMPT_ID",
    "RESEARCH_IMAGE_PROMPT_ID",
    "ResearchDocumentProcessingError",
    "ResearchDocumentProcessor",
    "ResearchVisionGateway",
]
