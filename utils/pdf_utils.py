"""Render PDF bytes as base64-encoded JPEG pages using PDFium."""
import base64
import io
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None
    logger.warning("[PdfUtils] pypdfium2 未安装，PDF 转图片功能不可用")


def pdf_bytes_to_images(pdf_bytes: bytes, max_pages: int = 8, dpi: int = 150) -> List[Dict]:
    """Return up to max_pages rendered JPEG images, with one-based page numbers."""
    if pdfium is None:
        raise RuntimeError("pypdfium2 未安装，无法转换 PDF。请安装项目依赖")
    if not pdf_bytes:
        return []

    try:
        result = []
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            for i in range(min(len(doc), max_pages)):
                page = doc[i]
                try:
                    bitmap = page.render(scale=dpi / 72.0)
                    try:
                        image = bitmap.to_pil()
                        try:
                            with image.convert("RGB") as rgb, io.BytesIO() as buffer:
                                rgb.save(buffer, format="JPEG")
                                encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                result.append({"base64": encoded, "mime_type": "image/jpeg", "page": i + 1})
        finally:
            doc.close()
        logger.info("[PdfUtils] PDF 转换完成，共 %s 页", len(result))
        return result
    except Exception as exc:
        logger.error("[PdfUtils] PDF 转换失败: %s", exc, exc_info=True)
        raise RuntimeError(f"PDF 转图片失败: {exc}") from exc
