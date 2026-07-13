"""
PDF 工具模块 - 将 PDF 字节转为图片 base64 列表

使用 pymupdf（fitz）库，Windows 无需额外安装 poppler。
pip install pymupdf
"""
import base64
import hashlib
import logging
import math
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

try:
    import fitz  # pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None
    PYMUPDF_AVAILABLE = False
    logger.warning("[PdfUtils] pymupdf 未安装，PDF转图片功能不可用。请执行: pip install pymupdf")


MAX_PDF_PAGES = 8
MAX_PDF_PAGE_PIXELS = 25_000_000
MAX_PDF_TOTAL_PIXELS = 100_000_000

RESEARCH_PDF_MAX_PAGES = 100
RESEARCH_PDF_MAX_OCR_PAGES = 20
RESEARCH_PDF_DPI = 150
RESEARCH_PDF_MAX_PAGE_PIXELS = 25_000_000
RESEARCH_PDF_MAX_OCR_TOTAL_PIXELS = 100_000_000
RESEARCH_PDF_MIN_VALID_CHARACTERS = 16
RESEARCH_PDF_MIN_NON_WHITESPACE_CHARACTERS = 24
RESEARCH_PDF_MAX_TEXT_BYTES_PER_PAGE = 2 * 1024 * 1024
RESEARCH_PDF_MAX_TEXT_BYTES_TOTAL = 16 * 1024 * 1024
RESEARCH_PDF_MAX_OUTPUT_BYTES = 64 * 1024 * 1024

_RESEARCH_VALID_CHARACTER_PATTERN = re.compile(r"[A-Za-z0-9\u3400-\u4dbf\u4e00-\u9fff]")


class StrictPdfError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class RenderedPdfPage:
    page_number: int
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class ResearchPdfPageArtifact:
    page_number: int
    text_relative_path: str
    text_sha256: str
    ocr_image_relative_path: str | None
    ocr_image_sha256: str | None


def is_research_pdf_text_low_quality(text: str) -> bool:
    """使用确定性的中英文数字与非空白阈值判定是否需要 OCR。"""
    if not isinstance(text, str):
        return True
    non_whitespace_count = sum(not character.isspace() for character in text)
    valid_count = len(_RESEARCH_VALID_CHARACTER_PATTERN.findall(text))
    return (
        non_whitespace_count < RESEARCH_PDF_MIN_NON_WHITESPACE_CHARACTERS
        or valid_count < RESEARCH_PDF_MIN_VALID_CHARACTERS
    )


def extract_research_pdf_path_strict(
    input_path: Path | str,
    output_dir: Path | str,
    *,
    declared_page_count: int,
) -> list[ResearchPdfPageArtifact]:
    """提取科研 PDF 的逐页文本，仅为低质量页生成受限 OCR 图。"""
    if not PYMUPDF_AVAILABLE or fitz is None:
        raise StrictPdfError("PDF_PARSER_UNAVAILABLE")

    source = Path(input_path)
    destination = Path(output_dir)
    try:
        source_lstat = source.lstat()
        source_real = source.resolve(strict=True)
        destination_real = destination.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StrictPdfError("PDF_PATH_INVALID") from exc
    if (
        not stat.S_ISREG(source_lstat.st_mode)
        or source.is_symlink()
        or not destination_real.is_dir()
    ):
        raise StrictPdfError("PDF_PATH_INVALID")

    try:
        document = fitz.open(filename=str(source_real), filetype="pdf")
    except Exception as exc:
        raise StrictPdfError("RESEARCH_PDF_INVALID") from exc

    created: list[Path] = []
    try:
        try:
            if _research_pdf_is_encrypted(document):
                raise StrictPdfError("RESEARCH_PDF_ENCRYPTED")
            if bool(getattr(document, "is_repaired", False)):
                raise StrictPdfError("RESEARCH_PDF_INVALID")
        except StrictPdfError:
            raise
        except Exception as exc:
            raise StrictPdfError("RESEARCH_PDF_INVALID") from exc
        try:
            page_count = len(document)
        except Exception as exc:
            raise StrictPdfError("RESEARCH_PDF_INVALID") from exc
        if page_count == 0:
            raise StrictPdfError("RESEARCH_PDF_INVALID")
        if page_count > RESEARCH_PDF_MAX_PAGES:
            raise StrictPdfError("RESEARCH_PDF_PAGE_LIMIT")
        if (
            isinstance(declared_page_count, bool)
            or not isinstance(declared_page_count, int)
            or page_count != declared_page_count
        ):
            raise StrictPdfError("ATTACHMENT_PAGE_COUNT_MISMATCH")

        scale = RESEARCH_PDF_DPI / 72.0
        scanned_pages: list[tuple[object, bytes, int, bool]] = []
        total_text_bytes = 0
        total_ocr_pixels = 0
        ocr_page_count = 0
        for index in range(page_count):
            try:
                page = document[index]
                width = float(page.rect.width)
                height = float(page.rect.height)
            except Exception as exc:
                raise StrictPdfError("RESEARCH_PDF_INVALID") from exc
            if (
                not math.isfinite(width)
                or not math.isfinite(height)
                or width <= 0
                or height <= 0
            ):
                raise StrictPdfError("RESEARCH_PDF_INVALID")
            pixel_width = math.ceil(width * scale)
            pixel_height = math.ceil(height * scale)
            page_pixels = pixel_width * pixel_height
            if page_pixels > RESEARCH_PDF_MAX_PAGE_PIXELS:
                raise StrictPdfError("PDF_PAGE_PIXEL_LIMIT")

            try:
                blocks = page.get_text("blocks", sort=True)
                text = _normalize_research_pdf_blocks(blocks)
                text_bytes = text.encode("utf-8", errors="strict")
            except StrictPdfError:
                raise
            except Exception as exc:
                raise StrictPdfError("RESEARCH_PDF_INVALID") from exc
            if len(text_bytes) > RESEARCH_PDF_MAX_TEXT_BYTES_PER_PAGE:
                raise StrictPdfError("RESEARCH_PDF_TEXT_LIMIT")
            total_text_bytes += len(text_bytes)
            if total_text_bytes > RESEARCH_PDF_MAX_TEXT_BYTES_TOTAL:
                raise StrictPdfError("RESEARCH_PDF_TEXT_LIMIT")

            needs_ocr = is_research_pdf_text_low_quality(text)
            if needs_ocr:
                ocr_page_count += 1
                total_ocr_pixels += page_pixels
            scanned_pages.append((page, text_bytes, page_pixels, needs_ocr))

        if ocr_page_count > RESEARCH_PDF_MAX_OCR_PAGES:
            raise StrictPdfError("RESEARCH_PDF_OCR_PAGE_LIMIT")
        if total_ocr_pixels > RESEARCH_PDF_MAX_OCR_TOTAL_PIXELS:
            raise StrictPdfError("RESEARCH_PDF_OCR_TOTAL_PIXEL_LIMIT")

        total_output_bytes = total_text_bytes
        if total_output_bytes > RESEARCH_PDF_MAX_OUTPUT_BYTES:
            raise StrictPdfError("ATTACHMENT_OUTPUT_LIMIT")
        matrix = fitz.Matrix(scale, scale)
        artifacts: list[ResearchPdfPageArtifact] = []
        for index, (page, text_bytes, _page_pixels, needs_ocr) in enumerate(
            scanned_pages,
            start=1,
        ):
            text_relative_path = f"page-{index:04d}.txt"
            text_output_path = destination_real / text_relative_path
            _write_private_research_artifact(text_output_path, text_bytes)
            created.append(text_output_path)

            ocr_relative_path: str | None = None
            ocr_sha256: str | None = None
            if needs_ocr:
                try:
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                    rendered_pixels = int(pixmap.width) * int(pixmap.height)
                    if rendered_pixels <= 0:
                        raise StrictPdfError("RESEARCH_PDF_INVALID")
                    if rendered_pixels > RESEARCH_PDF_MAX_PAGE_PIXELS:
                        raise StrictPdfError("PDF_PAGE_PIXEL_LIMIT")
                    image_bytes = pixmap.tobytes("jpeg")
                    if (
                        len(image_bytes) < 5
                        or not image_bytes.startswith(b"\xff\xd8\xff")
                        or not image_bytes.endswith(b"\xff\xd9")
                    ):
                        raise StrictPdfError("RESEARCH_PDF_INVALID")
                except StrictPdfError:
                    raise
                except Exception as exc:
                    raise StrictPdfError("RESEARCH_PDF_INVALID") from exc
                total_output_bytes += len(image_bytes)
                if (
                    len(image_bytes) > RESEARCH_PDF_MAX_OUTPUT_BYTES
                    or total_output_bytes > RESEARCH_PDF_MAX_OUTPUT_BYTES
                ):
                    raise StrictPdfError("ATTACHMENT_OUTPUT_LIMIT")
                ocr_relative_path = f"page-{index:04d}-ocr.jpg"
                ocr_output_path = destination_real / ocr_relative_path
                _write_private_research_artifact(ocr_output_path, image_bytes)
                created.append(ocr_output_path)
                ocr_sha256 = hashlib.sha256(image_bytes).hexdigest()

            artifacts.append(
                ResearchPdfPageArtifact(
                    page_number=index,
                    text_relative_path=text_relative_path,
                    text_sha256=hashlib.sha256(text_bytes).hexdigest(),
                    ocr_image_relative_path=ocr_relative_path,
                    ocr_image_sha256=ocr_sha256,
                )
            )
        return artifacts
    except Exception:
        for output_path in created:
            try:
                output_path.unlink()
            except OSError:
                pass
        raise
    finally:
        try:
            document.close()
        except Exception:
            pass


def _normalize_research_pdf_blocks(blocks: object) -> str:
    if not isinstance(blocks, (list, tuple)):
        raise StrictPdfError("RESEARCH_PDF_INVALID")
    normalized_blocks: list[str] = []
    for block in blocks:
        if not isinstance(block, (list, tuple)) or len(block) < 5:
            raise StrictPdfError("RESEARCH_PDF_INVALID")
        if len(block) >= 7 and block[6] != 0:
            continue
        raw_text = block[4]
        if not isinstance(raw_text, str):
            raise StrictPdfError("RESEARCH_PDF_INVALID")
        normalized_lines = [
            " ".join(line.split())
            for line in unicodedata.normalize("NFC", raw_text)
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .split("\n")
        ]
        normalized = "\n".join(line for line in normalized_lines if line)
        if normalized:
            normalized_blocks.append(normalized)
    return "\n\n".join(normalized_blocks)


def _research_pdf_is_encrypted(document: object) -> bool:
    if bool(getattr(document, "needs_pass", False)) or bool(
        getattr(document, "is_encrypted", False)
    ):
        return True

    metadata = getattr(document, "metadata", None)
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise StrictPdfError("RESEARCH_PDF_INVALID")
        encryption = metadata.get("encryption")
        if encryption is not None and str(encryption).strip().lower() not in {
            "",
            "none",
            "null",
        }:
            return True

    xref_get_key = getattr(document, "xref_get_key", None)
    if callable(xref_get_key):
        key = xref_get_key(-1, "Encrypt")
        if not isinstance(key, tuple) or len(key) != 2:
            raise StrictPdfError("RESEARCH_PDF_INVALID")
        key_type, key_value = key
        if str(key_type).lower() not in {"null", "none"} or str(
            key_value
        ).lower() not in {"null", "none", ""}:
            return True

    pdf_trailer = getattr(document, "pdf_trailer", None)
    if callable(pdf_trailer):
        trailer = pdf_trailer()
        if not isinstance(trailer, str):
            raise StrictPdfError("RESEARCH_PDF_INVALID")
        if re.search(r"/Encrypt(?:\s|[/<])", trailer):
            return True
    return False


def _write_private_research_artifact(path: Path, content: bytes) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        stream = os.fdopen(descriptor, "wb")
        descriptor = None
        with stream as output:
            output.write(content)
    except OSError as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            path.unlink()
        except OSError:
            pass
        raise StrictPdfError("PDF_OUTPUT_FAILED") from exc


def render_pdf_path_strict(
    input_path: Path | str,
    output_dir: Path | str,
    *,
    dpi: int = 150,
    max_pages: int = MAX_PDF_PAGES,
    max_page_pixels: int = MAX_PDF_PAGE_PIXELS,
    max_total_pixels: int = MAX_PDF_TOTAL_PIXELS,
) -> list[RenderedPdfPage]:
    """从受控 path 严格渲染 PDF；超过限制时拒绝而不是静默截断。"""
    if not PYMUPDF_AVAILABLE or fitz is None:
        raise StrictPdfError("PDF_PARSER_UNAVAILABLE")
    if dpi != 150 or max_pages != MAX_PDF_PAGES:
        raise StrictPdfError("PDF_RENDER_POLICY_INVALID")

    source = Path(input_path)
    destination = Path(output_dir)
    try:
        source_lstat = source.lstat()
        source_real = source.resolve(strict=True)
        destination_real = destination.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StrictPdfError("PDF_PATH_INVALID") from exc
    if (
        not stat.S_ISREG(source_lstat.st_mode)
        or source.is_symlink()
        or not destination_real.is_dir()
    ):
        raise StrictPdfError("PDF_PATH_INVALID")

    try:
        document = fitz.open(filename=str(source_real), filetype="pdf")
    except Exception as exc:
        raise StrictPdfError("PDF_INVALID") from exc

    created: list[Path] = []
    try:
        if bool(getattr(document, "needs_pass", False)):
            raise StrictPdfError("PDF_ENCRYPTED")
        try:
            page_count = len(document)
        except Exception as exc:
            raise StrictPdfError("PDF_INVALID") from exc
        if page_count == 0:
            raise StrictPdfError("PDF_EMPTY")
        if page_count > max_pages:
            raise StrictPdfError("PDF_PAGE_LIMIT")

        scale = dpi / 72.0
        matrix = fitz.Matrix(scale, scale)
        predicted_total = 0
        rendered: list[RenderedPdfPage] = []
        for index in range(page_count):
            try:
                page = document[index]
                width = float(page.rect.width)
                height = float(page.rect.height)
            except Exception as exc:
                raise StrictPdfError("PDF_INVALID") from exc
            if (
                not math.isfinite(width)
                or not math.isfinite(height)
                or width <= 0
                or height <= 0
            ):
                raise StrictPdfError("PDF_PAGE_GEOMETRY_INVALID")
            pixel_width = math.ceil(width * scale)
            pixel_height = math.ceil(height * scale)
            page_pixels = pixel_width * pixel_height
            if page_pixels > max_page_pixels:
                raise StrictPdfError("PDF_PAGE_PIXEL_LIMIT")
            predicted_total += page_pixels
            if predicted_total > max_total_pixels:
                raise StrictPdfError("PDF_TOTAL_PIXEL_LIMIT")

            try:
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                if pixmap.width * pixmap.height > max_page_pixels:
                    raise StrictPdfError("PDF_PAGE_PIXEL_LIMIT")
                image_bytes = pixmap.tobytes("jpeg")
            except StrictPdfError:
                raise
            except Exception as exc:
                raise StrictPdfError("PDF_RENDER_FAILED") from exc

            relative_path = f"page-{index + 1:04d}.jpg"
            output_path = destination_real / relative_path
            try:
                file_descriptor = os.open(
                    output_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                with os.fdopen(file_descriptor, "wb") as output:
                    output.write(image_bytes)
            except OSError as exc:
                raise StrictPdfError("PDF_OUTPUT_FAILED") from exc
            created.append(output_path)
            rendered.append(
                RenderedPdfPage(
                    page_number=index + 1,
                    relative_path=relative_path,
                    sha256=hashlib.sha256(image_bytes).hexdigest(),
                )
            )
        return rendered
    except Exception:
        for output_path in created:
            try:
                output_path.unlink()
            except OSError:
                pass
        raise
    finally:
        try:
            document.close()
        except Exception:
            pass


def pdf_bytes_to_images(
    pdf_bytes: bytes,
    max_pages: int = 8,
    dpi: int = 150,
) -> List[Dict]:
    """
    将 PDF 字节转为各页 JPEG 图片 base64 列表。

    Args:
        pdf_bytes: PDF 文件字节数据
        max_pages: 最多处理页数（医疗报告通常 1-5 页，默认上限 8）
        dpi: 渲染分辨率（150dpi 约 100-200KB/页，识别精度与大小的平衡点）

    Returns:
        列表，每项为：
        {
            "base64": str,          # JPEG 图片的 base64 字符串
            "mime_type": "image/jpeg",
            "page": int,            # 页码（从 1 开始）
        }

    Raises:
        RuntimeError: pymupdf 未安装时
    """
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError(
            "pymupdf 未安装，无法转换 PDF。请执行: pip install pymupdf"
        )

    if not pdf_bytes:
        return []

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        pages_to_process = min(total_pages, max_pages)

        logger.info(
            f"[PdfUtils] PDF共 {total_pages} 页，处理前 {pages_to_process} 页，DPI={dpi}"
        )

        result = []
        scale = dpi / 72.0  # fitz 默认 72dpi，缩放到目标 DPI
        mat = fitz.Matrix(scale, scale)

        for i in range(pages_to_process):
            page = doc[i]
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("jpeg")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            result.append({
                "base64": b64,
                "mime_type": "image/jpeg",
                "page": i + 1,
            })
            logger.debug(
                f"[PdfUtils] 第 {i + 1} 页转换完成，图片大小: {len(img_bytes) // 1024}KB"
            )

        doc.close()
        logger.info(f"[PdfUtils] PDF 转换完成，共 {len(result)} 页")
        return result

    except Exception as e:
        logger.error(f"[PdfUtils] PDF 转换失败: {e}", exc_info=True)
        raise RuntimeError(f"PDF 转图片失败: {e}") from e
