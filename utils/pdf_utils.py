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
import stat
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


class StrictPdfError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class RenderedPdfPage:
    page_number: int
    relative_path: str
    sha256: str


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
