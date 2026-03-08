"""
PDF 工具模块 - 将 PDF 字节转为图片 base64 列表

使用 pymupdf（fitz）库，Windows 无需额外安装 poppler。
pip install pymupdf
"""
import base64
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

try:
    import fitz  # pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("[PdfUtils] pymupdf 未安装，PDF转图片功能不可用。请执行: pip install pymupdf")


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
