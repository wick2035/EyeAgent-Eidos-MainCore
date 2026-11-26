"""
文件上传路由 - 处理图片和 PDF 附件上传

POST /api/upload
  - 图片 (image/jpeg, image/png, image/webp)：存 MinIO 备份 + 返回 base64
  - PDF  (application/pdf)：存 MinIO 备份 + pypdfium2 转页面图片 base64

返回数据直接附在 ChatRequest.attachments[] 中随消息发送。
"""
import base64
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, status
from pydantic import BaseModel

from infrastructure.storage.minio_client import get_minio_client
from utils.pdf_utils import pdf_bytes_to_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["files"])

# 允许的 MIME 类型及对应扩展名
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_PDF_TYPES = {"application/pdf"}
_ALL_ALLOWED_TYPES = _ALLOWED_IMAGE_TYPES | _ALLOWED_PDF_TYPES

# 文件大小上限
_MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
_MAX_PDF_SIZE = 30 * 1024 * 1024     # 30MB

# MinIO 文件夹
_MINIO_FOLDER = "attachments"


class PageImageResponse(BaseModel):
    base64: str
    mime_type: str = "image/jpeg"
    page: int


class FileUploadResponse(BaseModel):
    file_type: str                              # "image" | "pdf"
    filename: str
    minio_url: Optional[str] = None            # MinIO 备份 URL（内网，仅记录用）
    # 图片专用
    base64: Optional[str] = None
    mime_type: Optional[str] = None
    # PDF 专用
    page_images: Optional[list[PageImageResponse]] = None
    page_count: Optional[int] = None


@router.post("/upload", response_model=FileUploadResponse)
async def upload_attachment(file: UploadFile = File(...)) -> FileUploadResponse:
    """
    上传图片或 PDF 附件。

    图片：存 MinIO → 读回字节 → base64，返回 {file_type, base64, mime_type, minio_url}
    PDF ：存 MinIO → pypdfium2 转各页 JPEG → base64，返回 {file_type, page_images, minio_url}

    前端拿到响应后，将整个 JSON 对象放入 ChatRequest.attachments[]，
    随消息一起发送给 /api/chat，由 chat_router 触发附件预分析。
    """
    content_type = file.content_type or ""
    filename = file.filename or f"upload_{uuid.uuid4().hex[:8]}"

    # ── 类型校验 ──────────────────────────────────────────────────────────────
    if content_type not in _ALL_ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"不支持的文件类型: {content_type}。"
                   f"支持: image/jpeg, image/png, image/webp, application/pdf",
        )

    # ── 读取文件字节 ──────────────────────────────────────────────────────────
    file_bytes = await file.read()

    # ── 大小校验 ──────────────────────────────────────────────────────────────
    if content_type in _ALLOWED_IMAGE_TYPES and len(file_bytes) > _MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"图片文件过大（{len(file_bytes) // 1024 // 1024}MB），上限 10MB",
        )
    if content_type in _ALLOWED_PDF_TYPES and len(file_bytes) > _MAX_PDF_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF文件过大（{len(file_bytes) // 1024 // 1024}MB），上限 30MB",
        )

    logger.info(
        f"[FileRouter] 上传附件: filename={filename}, "
        f"type={content_type}, size={len(file_bytes) // 1024}KB"
    )

    # ── 存 MinIO 备份（可选，失败不阻断流程）────────────────────────────────
    minio_url: Optional[str] = None
    try:
        minio = get_minio_client()
        if minio.is_available():
            minio_url = minio.upload_bytes(
                data=file_bytes,
                content_type=content_type,
                folder=_MINIO_FOLDER,
            )
            logger.info(f"[FileRouter] MinIO 备份成功: {minio_url}")
        else:
            logger.warning("[FileRouter] MinIO 不可用，跳过备份存储")
    except Exception as e:
        logger.warning(f"[FileRouter] MinIO 备份失败（不影响后续分析）: {e}")

    # ── 图片处理 ──────────────────────────────────────────────────────────────
    if content_type in _ALLOWED_IMAGE_TYPES:
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        return FileUploadResponse(
            file_type="image",
            filename=filename,
            minio_url=minio_url,
            base64=b64,
            mime_type=content_type,
        )

    # ── PDF 处理 ──────────────────────────────────────────────────────────────
    try:
        pages = pdf_bytes_to_images(file_bytes, max_pages=8, dpi=150)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"PDF 转图片失败: {e}",
        )

    if not pages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF 无法提取任何页面图片，请确认文件完整",
        )

    page_responses = [
        PageImageResponse(
            base64=pg["base64"],
            mime_type=pg["mime_type"],
            page=pg["page"],
        )
        for pg in pages
    ]

    return FileUploadResponse(
        file_type="pdf",
        filename=filename,
        minio_url=minio_url,
        page_images=page_responses,
        page_count=len(page_responses),
    )
