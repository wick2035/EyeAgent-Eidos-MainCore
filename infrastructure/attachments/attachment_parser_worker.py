import hashlib
import json
import os
import resource
import stat
import sys
import zipfile
from pathlib import Path

from PIL import Image

from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ResearchPdfManifest,
    ResearchPdfPageManifest,
    WorkerManifest,
    WorkerPageManifest,
    WorkerRequest,
)
from utils.pdf_utils import (
    StrictPdfError,
    extract_research_pdf_path_strict,
    render_pdf_path_strict,
)


MAX_IMAGE_PIXELS = 50_000_000
_MAX_REQUEST_BYTES = 16 * 1024
_MAX_OUTPUT_FILE_BYTES = 64 * 1024 * 1024
_MAX_OUTPUT_TOTAL_BYTES = 64 * 1024 * 1024


def parse_attachment_file(
    request: WorkerRequest,
    input_dir: Path | str,
    output_dir: Path | str,
) -> WorkerManifest | ResearchPdfManifest:
    input_root = _resolve_directory(input_dir)
    output_root = _resolve_directory(output_dir)
    input_path = input_root / request.input_filename
    try:
        input_lstat = input_path.lstat()
        input_real = input_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AttachmentParserError("ATTACHMENT_INPUT_PATH_INVALID") from exc
    if (
        not stat.S_ISREG(input_lstat.st_mode)
        or input_path.is_symlink()
        or input_real.parent != input_root
    ):
        raise AttachmentParserError("ATTACHMENT_INPUT_PATH_INVALID")

    if request.file_type == "image":
        return _parse_image(request, input_real, output_root)
    if request.profile == "research_pdf_v1":
        return _parse_research_pdf(request, input_real, output_root)
    return _parse_pdf(request, input_real, output_root)


def _parse_image(
    request: WorkerRequest,
    input_path: Path,
    output_root: Path,
) -> WorkerManifest:
    expected_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }[request.mime_type]
    try:
        with Image.open(input_path) as image:
            width, height = image.size
            image_format = image.format
            if width <= 0 or height <= 0:
                raise AttachmentParserError("ATTACHMENT_IMAGE_INVALID")
            if width * height > MAX_IMAGE_PIXELS:
                raise AttachmentParserError("ATTACHMENT_IMAGE_PIXEL_LIMIT")
            if image_format != expected_format:
                raise AttachmentParserError("ATTACHMENT_IMAGE_FORMAT_MISMATCH")
            image.verify()
    except AttachmentParserError:
        raise
    except Exception as exc:
        raise AttachmentParserError("ATTACHMENT_IMAGE_INVALID") from exc

    suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[expected_format]
    relative_path = f"page-0001{suffix}"
    output_path = output_root / relative_path
    digest = hashlib.sha256()
    total = 0
    try:
        file_descriptor = os.open(
            output_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with input_path.open("rb") as source, os.fdopen(file_descriptor, "wb") as output:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_OUTPUT_FILE_BYTES:
                    raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
                output.write(chunk)
                digest.update(chunk)
    except AttachmentParserError:
        try:
            output_path.unlink()
        except OSError:
            pass
        raise
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_FAILED") from exc

    return WorkerManifest(
        pages=(
            WorkerPageManifest(
                page_number=1,
                relative_path=relative_path,
                sha256=digest.hexdigest(),
            ),
        )
    )


def _parse_pdf(
    request: WorkerRequest,
    input_path: Path,
    output_root: Path,
) -> WorkerManifest:
    try:
        rendered_pages = render_pdf_path_strict(
            input_path,
            output_root,
            dpi=150,
        )
    except StrictPdfError as exc:
        raise AttachmentParserError(exc.error_code) from exc
    if len(rendered_pages) != request.declared_page_count:
        raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_MISMATCH")
    return WorkerManifest(
        pages=tuple(
            WorkerPageManifest(
                page_number=page.page_number,
                relative_path=page.relative_path,
                sha256=page.sha256,
            )
            for page in rendered_pages
        )
    )


def _parse_research_pdf(
    request: WorkerRequest,
    input_path: Path,
    output_root: Path,
) -> ResearchPdfManifest:
    declared_page_count = request.declared_page_count
    if type(declared_page_count) is not int:
        raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_INVALID")
    try:
        extracted_pages = extract_research_pdf_path_strict(
            input_path,
            output_root,
            declared_page_count=declared_page_count,
        )
    except StrictPdfError as exc:
        raise AttachmentParserError(exc.error_code) from exc
    return ResearchPdfManifest(
        pages=tuple(
            ResearchPdfPageManifest(
                page_number=page.page_number,
                text_relative_path=page.text_relative_path,
                text_sha256=page.text_sha256,
                ocr_image_relative_path=page.ocr_image_relative_path,
                ocr_image_sha256=page.ocr_image_sha256,
            )
            for page in extracted_pages
        )
    )


def _resolve_directory(path: Path | str) -> Path:
    candidate = Path(path)
    try:
        resolved = candidate.resolve(strict=True)
        mode = candidate.lstat().st_mode
    except (OSError, RuntimeError) as exc:
        raise AttachmentParserError("ATTACHMENT_SANDBOX_PATH_INVALID") from exc
    if not stat.S_ISDIR(mode) or candidate.is_symlink():
        raise AttachmentParserError("ATTACHMENT_SANDBOX_PATH_INVALID")
    return resolved


def _write_output_bundle(
    manifest: WorkerManifest | ResearchPdfManifest,
    output_dir: Path | str,
    bundle_path: Path | str,
) -> None:
    output_root = _resolve_directory(output_dir)
    bundle = Path(bundle_path)
    try:
        bundle_metadata = bundle.lstat()
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
    if (
        bundle.is_symlink()
        or not stat.S_ISREG(bundle_metadata.st_mode)
        or stat.S_IMODE(bundle_metadata.st_mode) != 0o600
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")

    validated: list[tuple[Path, str]] = []
    total_bytes = 0
    for relative_path, expected_sha256 in _manifest_artifacts(manifest):
        source = output_root / relative_path
        try:
            metadata = source.lstat()
            resolved = source.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
        if (
            source.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or resolved.parent != output_root
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        total_bytes += metadata.st_size
        if total_bytes > _MAX_OUTPUT_TOTAL_BYTES:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
        if _sha256_file(resolved) != expected_sha256:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_HASH_MISMATCH")
        validated.append((resolved, relative_path))

    try:
        with zipfile.ZipFile(
            bundle,
            mode="w",
            compression=zipfile.ZIP_STORED,
            allowZip64=False,
        ) as archive:
            for source, relative_path in validated:
                archive.write(source, arcname=relative_path)
    except (OSError, RuntimeError, zipfile.LargeZipFile) as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_FAILED") from exc


def _manifest_artifacts(
    manifest: WorkerManifest | ResearchPdfManifest,
) -> tuple[tuple[str, str], ...]:
    if isinstance(manifest, WorkerManifest):
        return tuple(
            (page.relative_path, page.sha256) for page in manifest.pages
        )
    if not isinstance(manifest, ResearchPdfManifest):
        raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
    manifest = ResearchPdfManifest(tuple(manifest.pages))
    artifacts: list[tuple[str, str]] = []
    for page in manifest.pages:
        artifacts.append((page.text_relative_path, page.text_sha256))
        if page.ocr_image_relative_path is not None:
            if page.ocr_image_sha256 is None:
                raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
            artifacts.append(
                (page.ocr_image_relative_path, page.ocr_image_sha256)
            )
    return tuple(artifacts)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc
    return digest.hexdigest()


def _apply_resource_limits() -> None:
    limits = (
        (resource.RLIMIT_CPU, 120, 121),
        (resource.RLIMIT_AS, 768 * 1024 * 1024, 768 * 1024 * 1024),
        (resource.RLIMIT_FSIZE, _MAX_OUTPUT_FILE_BYTES, _MAX_OUTPUT_FILE_BYTES),
        (resource.RLIMIT_NOFILE, 128, 128),
    )
    try:
        for resource_name, soft, hard in limits:
            resource.setrlimit(resource_name, (soft, hard))
    except (OSError, ValueError) as exc:
        raise AttachmentParserError("ATTACHMENT_RESOURCE_LIMIT_FAILED") from exc


def _assert_network_namespace_isolated() -> None:
    try:
        ipv4_lines = Path("/proc/net/route").read_text(encoding="ascii").splitlines()
        ipv6_lines = Path("/proc/net/ipv6_route").read_text(
            encoding="ascii"
        ).splitlines()
    except (OSError, UnicodeError) as exc:
        raise AttachmentParserError("ATTACHMENT_NETWORK_CHECK_FAILED") from exc
    ipv4_interfaces = {
        fields[0]
        for line in ipv4_lines[1:]
        if len(fields := line.split()) >= 1
    }
    ipv6_interfaces = {
        fields[-1]
        for line in ipv6_lines
        if len(fields := line.split()) >= 10
    }
    if (ipv4_interfaces | ipv6_interfaces) - {"lo"}:
        raise AttachmentParserError("ATTACHMENT_NETWORK_ISOLATION_FAILED")


def _assert_input_is_read_only(input_path: Path) -> None:
    try:
        file_descriptor = os.open(input_path, os.O_WRONLY)
    except OSError:
        return
    else:
        os.close(file_descriptor)
    raise AttachmentParserError("ATTACHMENT_INPUT_MOUNT_WRITABLE")


def main() -> int:
    try:
        payload = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
        if len(payload) > _MAX_REQUEST_BYTES:
            raise AttachmentParserError("ATTACHMENT_WORKER_REQUEST_INVALID")
        request = WorkerRequest.from_json_bytes(payload)
        _apply_resource_limits()
        _assert_network_namespace_isolated()
        _assert_input_is_read_only(Path("/input") / request.input_filename)
        manifest = parse_attachment_file(request, Path("/input"), Path("/output"))
        _write_output_bundle(manifest, Path("/output"), Path("/output.bundle"))
        sys.stdout.buffer.write(manifest.to_json_bytes())
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        return 0
    except AttachmentParserError as exc:
        sys.stderr.write(
            json.dumps({"error_code": exc.error_code}, separators=(",", ":"))
            + "\n"
        )
        return 2
    except BaseException:
        sys.stderr.write('{"error_code":"ATTACHMENT_WORKER_FAILED"}\n')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
