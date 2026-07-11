import asyncio
import hashlib
import logging
import os
import shutil
import socket
import tempfile
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import aiohttp
from aiohttp.abc import AbstractResolver

from infrastructure.attachments.config import (
    AllowedAttachmentEndpoint,
    AttachmentConfigurationError,
    AttachmentDownloadSettings,
)


logger = logging.getLogger(__name__)

_TOTAL_LIMIT_BYTES = 40 * 1024 * 1024
_DEFAULT_CHUNK_SIZE = 64 * 1024


class AttachmentDownloadError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        *,
        attachment_id: str = "",
        bytes_received: int = 0,
    ) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.attachment_id = attachment_id
        self.bytes_received = bytes_received


@dataclass(frozen=True)
class DownloadedAttachment:
    attachment_id: str
    analysis_attempt_id: str
    file_type: str
    filename: str
    mime_type: str
    size_bytes: int
    content_sha256: str
    page_count: int | None
    path: Path
    document_version: int = 1

    def __post_init__(self) -> None:
        if type(self.size_bytes) is not int or self.size_bytes < 1:
            raise ValueError("size_bytes must be a positive integer")
        if self.page_count is not None and (
            type(self.page_count) is not int
            or not 1 <= self.page_count <= 100
        ):
            raise ValueError("page_count must be an integer from 1 to 100")
        if (
            type(self.document_version) is not int
            or self.document_version < 1
        ):
            raise ValueError("document_version must be a positive integer")


class _PinnedResolver(AbstractResolver):
    def __init__(self, endpoints: Iterable[AllowedAttachmentEndpoint]) -> None:
        addresses: dict[tuple[str, int], list[str]] = {}
        for endpoint in endpoints:
            addresses.setdefault((endpoint.host, endpoint.port), []).append(endpoint.ip)
        self._addresses = {
            key: tuple(dict.fromkeys(values)) for key, values in addresses.items()
        }

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: int = socket.AF_INET,
    ) -> list[dict[str, Any]]:
        addresses = self._addresses.get((host.lower(), port), ())
        if not addresses:
            raise OSError("attachment endpoint was not prevalidated")
        return [
            {
                "hostname": host,
                "host": address,
                "port": port,
                "family": socket.AF_INET6 if ":" in address else socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
            for address in addresses
        ]

    async def close(self) -> None:
        return None


class SecureAttachmentDownloader:
    def __init__(
        self,
        settings: AttachmentDownloadSettings,
        *,
        temp_root: Path | str | None = None,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        timeout_seconds: float = 120.0,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._settings = settings
        self._temp_root = Path(temp_root) if temp_root is not None else None
        self._chunk_size = chunk_size
        self._timeout_seconds = timeout_seconds

    @asynccontextmanager
    async def download_all(
        self,
        descriptors: Iterable[Any],
        request_id: str,
    ) -> AsyncIterator[list[DownloadedAttachment]]:
        items = list(descriptors)
        declared_total = 0
        for item in items:
            declared_total += _strict_descriptor_integer(item, "size_bytes")
            _strict_descriptor_integer(item, "document_version")
            _strict_descriptor_integer(item, "page_count", allow_none=True)
        if declared_total > _TOTAL_LIMIT_BYTES:
            raise AttachmentDownloadError("ATTACHMENT_TOTAL_LIMIT_EXCEEDED")

        endpoint_sets: list[tuple[AllowedAttachmentEndpoint, ...]] = []
        try:
            for descriptor in items:
                endpoint_sets.append(
                    self._settings.endpoints_for_url(
                        str(_value(descriptor, "download_url"))
                    )
                )
        except AttachmentConfigurationError as exc:
            raise AttachmentDownloadError("ATTACHMENT_URL_REJECTED") from exc

        request_directory: Path | None = None
        try:
            request_directory = Path(
                tempfile.mkdtemp(
                    prefix="eyeagent-attachment-download-",
                    dir=str(self._temp_root) if self._temp_root is not None else None,
                )
            )
            os.chmod(request_directory, 0o700)
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            downloaded: list[DownloadedAttachment] = []
            for index, (descriptor, endpoints) in enumerate(
                zip(items, endpoint_sets)
            ):
                resolver = _PinnedResolver(endpoints)
                connector = aiohttp.TCPConnector(
                    resolver=resolver,
                    use_dns_cache=False,
                    force_close=True,
                )
                async with aiohttp.ClientSession(
                    connector=connector,
                    connector_owner=True,
                    timeout=timeout,
                    trust_env=False,
                    auto_decompress=False,
                    headers={"Accept-Encoding": "identity"},
                ) as session:
                    try:
                        downloaded.append(
                            await self._download_one(
                                session,
                                descriptor,
                                request_directory,
                                index,
                            )
                        )
                    except AttachmentDownloadError as exc:
                        attachment_id = str(_value(descriptor, "attachment_id"))
                        file_type = str(_value(descriptor, "file_type"))
                        logger.warning(
                            "attachment download failed request_id=%s "
                            "attachment_id=%s type=%s bytes=%d error_code=%s",
                            request_id,
                            attachment_id,
                            file_type,
                            exc.bytes_received,
                            exc.error_code,
                        )
                        raise
            yield downloaded
        finally:
            if request_directory is not None:
                shutil.rmtree(request_directory, ignore_errors=True)

    async def _download_one(
        self,
        session: aiohttp.ClientSession,
        descriptor: Any,
        request_directory: Path,
        index: int,
    ) -> DownloadedAttachment:
        attachment_id = str(_value(descriptor, "attachment_id"))
        expected_size = _strict_descriptor_integer(descriptor, "size_bytes")
        mime_type = str(_value(descriptor, "mime_type"))
        suffix = _safe_suffix(mime_type)
        destination = request_directory / f"{index:02d}-{uuid.uuid4().hex}{suffix}"
        received = 0
        digest = hashlib.sha256()

        try:
            async with session.get(
                str(_value(descriptor, "download_url")),
                allow_redirects=False,
            ) as response:
                if 300 <= response.status < 400:
                    raise AttachmentDownloadError(
                        "ATTACHMENT_REDIRECT_REJECTED",
                        attachment_id=attachment_id,
                    )
                if response.status != 200:
                    raise AttachmentDownloadError(
                        "ATTACHMENT_DOWNLOAD_FAILED",
                        attachment_id=attachment_id,
                    )

                file_descriptor = os.open(
                    destination,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                with os.fdopen(file_descriptor, "wb") as output:
                    async for chunk in response.content.iter_chunked(self._chunk_size):
                        received += len(chunk)
                        if received > expected_size or received > _TOTAL_LIMIT_BYTES:
                            raise AttachmentDownloadError(
                                "ATTACHMENT_STREAM_LIMIT_EXCEEDED",
                                attachment_id=attachment_id,
                                bytes_received=received,
                            )
                        output.write(chunk)
                        digest.update(chunk)
        except AttachmentDownloadError:
            raise
        except aiohttp.ClientPayloadError as exc:
            raise AttachmentDownloadError(
                "ATTACHMENT_DOWNLOAD_INCOMPLETE",
                attachment_id=attachment_id,
                bytes_received=received,
            ) from exc
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise AttachmentDownloadError(
                "ATTACHMENT_DOWNLOAD_FAILED",
                attachment_id=attachment_id,
                bytes_received=received,
            ) from exc

        if received != expected_size:
            raise AttachmentDownloadError(
                "ATTACHMENT_SIZE_MISMATCH",
                attachment_id=attachment_id,
                bytes_received=received,
            )
        if digest.hexdigest() != str(_value(descriptor, "content_sha256")):
            raise AttachmentDownloadError(
                "ATTACHMENT_HASH_MISMATCH",
                attachment_id=attachment_id,
                bytes_received=received,
            )
        if not _matches_magic(destination, mime_type):
            raise AttachmentDownloadError(
                "ATTACHMENT_MAGIC_MISMATCH",
                attachment_id=attachment_id,
                bytes_received=received,
            )

        return DownloadedAttachment(
            attachment_id=attachment_id,
            analysis_attempt_id=str(_value(descriptor, "analysis_attempt_id")),
            file_type=str(_value(descriptor, "file_type")),
            filename=str(_value(descriptor, "filename")),
            mime_type=mime_type,
            size_bytes=received,
            content_sha256=digest.hexdigest(),
            page_count=_value(descriptor, "page_count"),
            path=destination,
            document_version=_strict_descriptor_integer(
                descriptor,
                "document_version",
            ),
        )


def _value(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item[name]
    return getattr(item, name)


def _strict_descriptor_integer(
    item: Any,
    name: str,
    *,
    allow_none: bool = False,
) -> int | None:
    value = _value(item, name)
    if value is None and allow_none:
        return None
    if type(value) is not int or value < 1:
        attachment_id = ""
        try:
            attachment_id = str(_value(item, "attachment_id"))
        except (AttributeError, KeyError):
            pass
        raise AttachmentDownloadError(
            "ATTACHMENT_DESCRIPTOR_INVALID",
            attachment_id=attachment_id,
        )
    return value


def _safe_suffix(mime_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }.get(mime_type, ".bin")


def _matches_magic(path: Path, mime_type: str) -> bool:
    with path.open("rb") as source:
        header = source.read(16)
    if mime_type == "image/jpeg":
        return header.startswith(b"\xff\xd8\xff")
    if mime_type == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/webp":
        return (
            len(header) >= 12
            and header.startswith(b"RIFF")
            and header[8:12] == b"WEBP"
        )
    if mime_type == "application/pdf":
        return header.startswith(b"%PDF-")
    return False
