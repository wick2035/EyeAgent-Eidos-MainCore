import asyncio
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import stat
import struct
import subprocess
import tempfile
import warnings
import zipfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from PIL import Image

from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ParsedAttachment,
    ParsedAttachmentPage,
    ParsedResearchPdf,
    ParsedResearchPdfPage,
    ParsedResearchDocx,
    ParsedResearchText,
    ResearchDocxManifest,
    ResearchPdfManifest,
    ResearchTextManifest,
    WorkerManifest,
    WorkerRequest,
)
from infrastructure.attachments.research_text_contract import (
    NormalizedResearchText,
    ResearchTextContractError,
    validate_canonical_research_text_bytes,
)
from infrastructure.attachments.research_docx_contract import (
    NormalizedResearchDocxText,
    ResearchDocxContractError,
    validate_canonical_research_docx_bytes,
)
from utils.pdf_utils import (
    RESEARCH_PDF_MAX_OCR_PAGES,
    RESEARCH_PDF_MAX_PAGE_PIXELS,
    RESEARCH_PDF_MAX_OCR_TOTAL_PIXELS,
    RESEARCH_PDF_MAX_TEXT_BYTES_PER_PAGE,
    RESEARCH_PDF_MAX_TEXT_BYTES_TOTAL,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_RUNNER = _REPOSITORY_ROOT / "scripts" / "run_attachment_parser_sandbox.sh"
_DEFAULT_IMAGE = "eyeagent/attachment-parser:research-c2b"
_PARSER_IMAGE_ENV = "PLATFORM_ATTACHMENT_PARSER_IMAGE"
_PARSER_REQUIRE_DIGEST_ENV = "PLATFORM_ATTACHMENT_PARSER_REQUIRE_DIGEST"
_CID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ERROR_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SAFE_IMAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:+-]{0,255}$")
_SHA256_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_STDOUT_BYTES = 64 * 1024
_MAX_OUTPUT_BYTES = 64 * 1024 * 1024
_LABEL_KEY = "eyeagent.attachment-parser.run"
_STARTUP_CLEANUP_WAIT_SECONDS = 2.0
_ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
_ZIP64_EOCD_LOCATOR_SIGNATURE = b"PK\x06\x07"
_ZIP_CENTRAL_HEADER_SIGNATURE = b"PK\x01\x02"
_ZIP_EOCD = struct.Struct("<4sHHHHIIH")
_ZIP_CENTRAL_HEADER = struct.Struct("<4s6H3I5H2I")
_ZIP_EOCD_MAX_SEARCH_BYTES = _ZIP_EOCD.size + 65_535
_MAX_CENTRAL_DIRECTORY_BYTES = 128 * 1024


CommandRunner = Callable[..., Awaitable[int]]
LabelFinder = Callable[[str, str], Awaitable[tuple[str, ...]]]


class _WorkerOutputLimitError(RuntimeError):
    pass


def _parse_strict_environment_boolean(
    raw_value: str | None,
    *,
    default: bool,
) -> bool:
    if raw_value is None:
        return default
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    raise AttachmentParserError("ATTACHMENT_SANDBOX_CONFIG_INVALID")


def _has_immutable_sha256_digest(image: str) -> bool:
    repository, separator, digest = image.rpartition("@sha256:")
    return bool(
        separator
        and repository
        and "@" not in repository
        and _SHA256_DIGEST_PATTERN.fullmatch(digest)
    )


class AttachmentParserSandbox:
    def __init__(
        self,
        *,
        runner_path: Path | str = _DEFAULT_RUNNER,
        docker_binary: str = "docker",
        image: str | None = None,
        environ: Mapping[str, str] | None = None,
        temp_root: Path | str | None = None,
        timeout_seconds: float = 120.0,
        uid_getter: Callable[[], int] = os.getuid,
        gid_getter: Callable[[], int] = os.getgid,
        label_factory: Callable[[], str] | None = None,
    ) -> None:
        source = os.environ if environ is None else environ
        configured_image = (
            source.get(_PARSER_IMAGE_ENV, _DEFAULT_IMAGE)
            if image is None
            else image
        )
        require_digest = _parse_strict_environment_boolean(
            source.get(_PARSER_REQUIRE_DIGEST_ENV),
            default=False,
        )
        if (
            not isinstance(configured_image, str)
            or not _SAFE_IMAGE_PATTERN.fullmatch(configured_image)
        ):
            raise AttachmentParserError("ATTACHMENT_SANDBOX_IMAGE_INVALID")
        if require_digest and not _has_immutable_sha256_digest(configured_image):
            raise AttachmentParserError(
                "ATTACHMENT_SANDBOX_IMAGE_DIGEST_REQUIRED"
            )
        self._runner_path = Path(runner_path)
        self._docker_binary = docker_binary
        self._image = configured_image
        self._require_digest = require_digest
        self._temp_root = (
            Path(temp_root)
            if temp_root is not None
            else Path(tempfile.gettempdir()) / "eyeagent-attachment-parser"
        )
        self._timeout_seconds = timeout_seconds
        self._uid_getter = uid_getter
        self._gid_getter = gid_getter
        self._label_factory = label_factory or (lambda: secrets.token_hex(16))

    async def preflight(self) -> None:
        if self._uid_getter() == 0:
            raise AttachmentParserError("ATTACHMENT_SANDBOX_ROOT_FORBIDDEN")
        if (
            not self._runner_path.is_file()
            or self._runner_path.is_symlink()
            or not os.access(self._runner_path, os.X_OK)
        ):
            raise AttachmentParserError("ATTACHMENT_SANDBOX_UNAVAILABLE")
        if shutil.which(self._docker_binary) is None:
            raise AttachmentParserError("ATTACHMENT_SANDBOX_UNAVAILABLE")

        info = await _run_capture_command(
            self._docker_binary,
            "info",
            "--format",
            "{{.ServerVersion}}",
        )
        if info[0] != 0 or not info[1].strip():
            raise AttachmentParserError("ATTACHMENT_SANDBOX_UNAVAILABLE")
        inspect = await _run_capture_command(
            self._docker_binary,
            "image",
            "inspect",
            self._image,
            "--format",
            "{{.Config.User}}",
        )
        configured_user = inspect[1].decode("utf-8", "replace").strip()
        if inspect[0] != 0 or configured_user.lower() in {"", "root", "0", "0:0"}:
            raise AttachmentParserError("ATTACHMENT_SANDBOX_UNAVAILABLE")

    async def parse(
        self,
        downloaded: Any,
        profile: str = "assistant_visual_v1",
    ) -> ParsedAttachment | ParsedResearchPdf | ParsedResearchText | ParsedResearchDocx:
        await self.preflight()
        self._ensure_temp_root()
        request_directory: Path | None = None
        cid_directory: Path | None = None
        cidfile: Path | None = None
        process: asyncio.subprocess.Process | None = None
        launch_task: asyncio.Task | None = None
        launch_interrupted = False
        label: str | None = None

        try:
            try:
                request_directory = Path(
                    tempfile.mkdtemp(prefix="request-", dir=str(self._temp_root))
                )
                cid_directory = Path(
                    tempfile.mkdtemp(prefix="cid-", dir=str(self._temp_root))
                )
                cidfile = cid_directory / "container.cid"
                os.chmod(request_directory, 0o700)
                os.chmod(cid_directory, 0o700)
                input_directory = request_directory / "input"
                output_bundle = request_directory / "output.bundle"
                input_directory.mkdir(mode=0o700)
                bundle_descriptor = os.open(
                    output_bundle,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                os.close(bundle_descriptor)
            except OSError as exc:
                raise AttachmentParserError(
                    "ATTACHMENT_SANDBOX_UNAVAILABLE"
                ) from exc

            input_filename = "attachment.bin"
            copied_input = input_directory / input_filename
            _copy_and_revalidate_input(downloaded, copied_input)
            request = WorkerRequest(
                input_filename=input_filename,
                file_type=str(_value(downloaded, "file_type")),
                mime_type=str(_value(downloaded, "mime_type")),
                declared_page_count=_value(downloaded, "page_count"),
                profile=profile,
            )
            label = self._label_factory()
            if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", label):
                raise AttachmentParserError("ATTACHMENT_SANDBOX_LABEL_INVALID")

            try:
                launch_task = asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        str(self._runner_path),
                        str(input_directory),
                        str(output_bundle),
                        str(cidfile),
                        label,
                        self._image,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        limit=_MAX_STDOUT_BYTES + 1,
                    )
                )
                process = await asyncio.shield(launch_task)
            except asyncio.CancelledError:
                launch_interrupted = True
                raise
            except (OSError, subprocess.SubprocessError) as exc:
                raise AttachmentParserError("ATTACHMENT_SANDBOX_UNAVAILABLE") from exc

            try:
                stdout, stderr = await asyncio.wait_for(
                    _communicate_bounded(process, request.to_json_bytes()),
                    timeout=self._timeout_seconds,
                )
            except _WorkerOutputLimitError as exc:
                await _stop_process(process)
                raise AttachmentParserError(
                    "ATTACHMENT_WORKER_OUTPUT_LIMIT"
                ) from exc
            except asyncio.TimeoutError as exc:
                launch_interrupted = True
                await _stop_process(process)
                raise AttachmentParserError("ATTACHMENT_PARSER_TIMEOUT") from exc
            except asyncio.CancelledError:
                launch_interrupted = True
                await asyncio.shield(_stop_process(process))
                raise

            if process.returncode != 0:
                raise AttachmentParserError(_worker_error_code(stderr))
            if profile == "research_pdf_v1":
                research_pages = _read_validated_research_bundle(
                    output_bundle,
                    stdout,
                    expected_page_count=_value(downloaded, "page_count"),
                )
                return ParsedResearchPdf(
                    attachment_id=str(_value(downloaded, "attachment_id")),
                    document_version=_value(downloaded, "document_version"),
                    mime_type=str(_value(downloaded, "mime_type")),
                    pages=research_pages,
                )
            if profile == "research_text_v1":
                research_text = _read_validated_research_text_bundle(
                    output_bundle,
                    stdout,
                )
                return ParsedResearchText(
                    attachment_id=str(_value(downloaded, "attachment_id")),
                    document_version=_value(downloaded, "document_version"),
                    mime_type=str(_value(downloaded, "mime_type")),
                    text=research_text.text,
                    text_sha256=research_text.sha256,
                    character_count=research_text.character_count,
                )
            if profile == "research_docx_v1":
                research_docx = _read_validated_research_docx_bundle(
                    output_bundle,
                    stdout,
                )
                return ParsedResearchDocx(
                    attachment_id=str(_value(downloaded, "attachment_id")),
                    document_version=_value(downloaded, "document_version"),
                    mime_type=str(_value(downloaded, "mime_type")),
                    text=research_docx.text,
                    text_sha256=research_docx.sha256,
                    character_count=research_docx.character_count,
                )
            pages = _read_validated_bundle(
                output_bundle,
                stdout,
                (
                    str(_value(downloaded, "mime_type"))
                    if str(_value(downloaded, "file_type")) == "image"
                    else "image/jpeg"
                ),
            )
            return ParsedAttachment(
                attachment_id=str(_value(downloaded, "attachment_id")),
                file_type=str(_value(downloaded, "file_type")),
                mime_type=str(_value(downloaded, "mime_type")),
                pages=pages,
            )
        finally:
            if launch_task is not None and process is None:
                process = await asyncio.shield(_reclaim_launch_task(launch_task))
            if process is not None and process.returncode is None:
                await asyncio.shield(_stop_process(process))
            if cidfile is not None:
                await asyncio.shield(
                    _cleanup_container(
                        cidfile,
                        docker_binary=self._docker_binary,
                        label=label,
                        wait_for_cidfile_seconds=(
                            _STARTUP_CLEANUP_WAIT_SECONDS
                            if launch_interrupted
                            else 0.0
                        ),
                    )
                )
            if request_directory is not None:
                shutil.rmtree(request_directory, ignore_errors=True)
            if cid_directory is not None:
                shutil.rmtree(cid_directory, ignore_errors=True)

    def _ensure_temp_root(self) -> None:
        try:
            self._temp_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self._temp_root.is_symlink():
                raise OSError("symlink temp root")
            os.chmod(self._temp_root, 0o700)
        except OSError as exc:
            raise AttachmentParserError("ATTACHMENT_SANDBOX_UNAVAILABLE") from exc


async def _cleanup_container(
    cidfile: Path,
    *,
    docker_binary: str,
    command_runner: CommandRunner | None = None,
    label: str | None = None,
    label_finder: LabelFinder | None = None,
    wait_for_cidfile_seconds: float = 0.0,
) -> None:
    runner = command_runner or _run_cleanup_command
    find_by_label = label_finder or _find_labeled_containers
    try:
        deadline = asyncio.get_running_loop().time() + max(
            wait_for_cidfile_seconds,
            0.0,
        )
        cleaned_container_ids: set[str] = set()
        while True:
            discovered: list[str] = []
            try:
                container_id = cidfile.read_text(encoding="ascii").strip()
                if _CID_PATTERN.fullmatch(container_id):
                    discovered.append(container_id)
            except FileNotFoundError:
                pass
            except (OSError, UnicodeError):
                pass
            if label is not None:
                try:
                    discovered.extend(await find_by_label(docker_binary, label))
                except BaseException:
                    pass
            container_ids = tuple(dict.fromkeys(
                item for item in discovered if _CID_PATTERN.fullmatch(item)
            ))
            for container_id in container_ids:
                if container_id in cleaned_container_ids:
                    continue
                try:
                    await runner(docker_binary, "kill", container_id)
                except BaseException:
                    pass
                try:
                    await runner(docker_binary, "rm", "-f", container_id)
                except BaseException:
                    pass
                cleaned_container_ids.add(container_id)
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            await asyncio.sleep(min(0.05, remaining))
    finally:
        try:
            cidfile.unlink()
        except OSError:
            pass


async def _run_cleanup_command(*command: str) -> int:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await process.wait()
    except (OSError, subprocess.SubprocessError):
        return 127


async def _run_capture_command(*command: str) -> tuple[int, bytes, bytes]:
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_MAX_STDOUT_BYTES + 1,
        )
        stdout, stderr = await asyncio.wait_for(
            _communicate_bounded(process),
            timeout=15,
        )
        return process.returncode or 0, stdout, stderr
    except (
        OSError,
        subprocess.SubprocessError,
        asyncio.TimeoutError,
        _WorkerOutputLimitError,
    ):
        return 127, b"", b""
    finally:
        if process is not None and process.returncode is None:
            await _stop_process(process)


async def _find_labeled_containers(
    docker_binary: str,
    label: str,
) -> tuple[str, ...]:
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", label):
        return ()
    return_code, stdout, _ = await _run_capture_command(
        docker_binary,
        "ps",
        "-aq",
        "--filter",
        f"label={_LABEL_KEY}={label}",
    )
    if return_code != 0:
        return ()
    container_ids = []
    for raw_line in stdout.splitlines():
        try:
            container_id = raw_line.decode("ascii")
        except UnicodeDecodeError:
            continue
        if _CID_PATTERN.fullmatch(container_id):
            container_ids.append(container_id)
    return tuple(container_ids)


async def _communicate_bounded(
    process: asyncio.subprocess.Process,
    payload: bytes | None = None,
) -> tuple[bytes, bytes]:
    stdout_task = asyncio.create_task(_read_stream_bounded(process.stdout))
    stderr_task = asyncio.create_task(_read_stream_bounded(process.stderr))
    wait_task = asyncio.create_task(process.wait())
    tasks = [stdout_task, stderr_task, wait_task]
    if payload is not None:
        tasks.append(asyncio.create_task(_write_process_stdin(process, payload)))
    try:
        await asyncio.gather(*tasks)
        return stdout_task.result(), stderr_task.result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _read_stream_bounded(
    stream: asyncio.StreamReader | None,
) -> bytes:
    if stream is None:
        return b""
    output = bytearray()
    while True:
        remaining = _MAX_STDOUT_BYTES + 1 - len(output)
        chunk = await stream.read(min(16 * 1024, max(remaining, 1)))
        if not chunk:
            return bytes(output)
        output.extend(chunk)
        if len(output) > _MAX_STDOUT_BYTES:
            raise _WorkerOutputLimitError()


async def _write_process_stdin(
    process: asyncio.subprocess.Process,
    payload: bytes,
) -> None:
    if process.stdin is None:
        return
    try:
        process.stdin.write(payload)
        await process.stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        process.stdin.close()
        try:
            await process.stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass


async def _reclaim_launch_task(
    launch_task: asyncio.Task,
) -> asyncio.subprocess.Process | None:
    try:
        return await asyncio.wait_for(
            asyncio.shield(launch_task),
            timeout=5,
        )
    except BaseException:
        if not launch_task.done():
            launch_task.cancel()
        return None


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process.kill()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except (asyncio.TimeoutError, ProcessLookupError):
        pass


def _read_validated_bundle(
    output_bundle: Path,
    stdout: bytes,
    mime_type: str,
) -> tuple[ParsedAttachmentPage, ...]:
    if len(stdout) > _MAX_STDOUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
    manifest = WorkerManifest.from_json_bytes(stdout)
    try:
        metadata = output_bundle.lstat()
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
    if (
        output_bundle.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    if metadata.st_size > _MAX_OUTPUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")

    expected_names = {page.relative_path for page in manifest.pages}
    _preflight_zip_bundle(
        output_bundle,
        file_size=metadata.st_size,
        expected_names=expected_names,
    )
    parsed_pages: list[ParsedAttachmentPage] = []
    total_bytes = 0
    try:
        with zipfile.ZipFile(output_bundle, mode="r") as archive:
            entries = archive.infolist()
            actual_names = {entry.filename for entry in entries}
            if len(entries) != len(actual_names) or actual_names != expected_names:
                raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
            entries_by_name = {entry.filename: entry for entry in entries}
            for page in manifest.pages:
                entry = entries_by_name[page.relative_path]
                if (
                    entry.is_dir()
                    or entry.flag_bits & 0x1
                    or entry.compress_type != zipfile.ZIP_STORED
                    or entry.compress_size != entry.file_size
                ):
                    raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
                total_bytes += entry.file_size
                if total_bytes > _MAX_OUTPUT_BYTES:
                    raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
                with archive.open(entry, mode="r") as input_file:
                    content = input_file.read(entry.file_size + 1)
                if len(content) != entry.file_size:
                    raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED")
                digest = hashlib.sha256(content).hexdigest()
                if digest != page.sha256:
                    raise AttachmentParserError(
                        "ATTACHMENT_OUTPUT_HASH_MISMATCH"
                    )
                parsed_pages.append(ParsedAttachmentPage(
                    page_number=page.page_number,
                    mime_type=mime_type,
                    sha256=digest,
                    content=content,
                ))
    except AttachmentParserError:
        raise
    except Exception as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc
    return tuple(parsed_pages)


def _read_validated_research_bundle(
    output_bundle: Path,
    stdout: bytes,
    *,
    expected_page_count: int,
) -> tuple[ParsedResearchPdfPage, ...]:
    if len(stdout) > _MAX_STDOUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
    manifest = ResearchPdfManifest.from_json_bytes(stdout)
    if (
        type(expected_page_count) is not int
        or not 1 <= expected_page_count <= 100
        or len(manifest.pages) != expected_page_count
    ):
        raise AttachmentParserError("ATTACHMENT_PAGE_COUNT_MISMATCH")
    ocr_page_count = sum(
        page.ocr_image_relative_path is not None for page in manifest.pages
    )
    if ocr_page_count > RESEARCH_PDF_MAX_OCR_PAGES:
        raise AttachmentParserError("RESEARCH_PDF_OCR_PAGE_LIMIT")
    try:
        metadata = output_bundle.lstat()
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
    if (
        output_bundle.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    if metadata.st_size > _MAX_OUTPUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")

    expected_names: set[str] = set()
    for page in manifest.pages:
        expected_names.add(page.text_relative_path)
        if page.ocr_image_relative_path is not None:
            expected_names.add(page.ocr_image_relative_path)
    _preflight_zip_bundle(
        output_bundle,
        file_size=metadata.st_size,
        expected_names=expected_names,
    )

    parsed_pages: list[ParsedResearchPdfPage] = []
    total_bytes = 0
    total_text_bytes = 0
    total_ocr_pixels = 0
    try:
        with zipfile.ZipFile(output_bundle, mode="r") as archive:
            entries = archive.infolist()
            actual_names = {entry.filename for entry in entries}
            if len(entries) != len(actual_names) or actual_names != expected_names:
                raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
            entries_by_name = {entry.filename: entry for entry in entries}
            for page in manifest.pages:
                text_content = _read_research_bundle_entry(
                    archive,
                    entries_by_name[page.text_relative_path],
                )
                total_bytes += len(text_content)
                total_text_bytes += len(text_content)
                if (
                    len(text_content) > RESEARCH_PDF_MAX_TEXT_BYTES_PER_PAGE
                    or total_text_bytes > RESEARCH_PDF_MAX_TEXT_BYTES_TOTAL
                    or total_bytes > _MAX_OUTPUT_BYTES
                ):
                    raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
                if hashlib.sha256(text_content).hexdigest() != page.text_sha256:
                    raise AttachmentParserError(
                        "ATTACHMENT_OUTPUT_HASH_MISMATCH"
                    )
                try:
                    text = text_content.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise AttachmentParserError(
                        "ATTACHMENT_OUTPUT_TEXT_INVALID"
                    ) from exc

                ocr_image_content: bytes | None = None
                if page.ocr_image_relative_path is not None:
                    image_entry = entries_by_name[page.ocr_image_relative_path]
                    ocr_image_content = _read_research_bundle_entry(
                        archive,
                        image_entry,
                    )
                    total_bytes += len(ocr_image_content)
                    if total_bytes > _MAX_OUTPUT_BYTES:
                        raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
                    if (
                        page.ocr_image_sha256 is None
                        or hashlib.sha256(ocr_image_content).hexdigest()
                        != page.ocr_image_sha256
                    ):
                        raise AttachmentParserError(
                            "ATTACHMENT_OUTPUT_HASH_MISMATCH"
                        )
                    total_ocr_pixels += _validate_research_ocr_jpeg(
                        ocr_image_content
                    )
                    if (
                        total_ocr_pixels
                        > RESEARCH_PDF_MAX_OCR_TOTAL_PIXELS
                    ):
                        raise AttachmentParserError(
                            "RESEARCH_PDF_OCR_TOTAL_PIXEL_LIMIT"
                        )
                parsed_pages.append(
                    ParsedResearchPdfPage(
                        page_number=page.page_number,
                        text=text,
                        text_sha256=page.text_sha256,
                        ocr_image_content=ocr_image_content,
                        ocr_image_sha256=page.ocr_image_sha256,
                    )
                )
    except AttachmentParserError:
        raise
    except Exception as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc
    return tuple(parsed_pages)


def _read_validated_research_text_bundle(
    output_bundle: Path,
    stdout: bytes,
) -> NormalizedResearchText:
    if len(stdout) > _MAX_STDOUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
    manifest = ResearchTextManifest.from_json_bytes(stdout)
    try:
        metadata = output_bundle.lstat()
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
    if (
        output_bundle.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    if metadata.st_size > _MAX_OUTPUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")

    expected_names = {manifest.text_relative_path}
    _preflight_zip_bundle(
        output_bundle,
        file_size=metadata.st_size,
        expected_names=expected_names,
    )
    try:
        with zipfile.ZipFile(output_bundle, mode="r") as archive:
            entries = archive.infolist()
            actual_names = {entry.filename for entry in entries}
            if len(entries) != 1 or actual_names != expected_names:
                raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
            content = _read_research_bundle_entry(archive, entries[0])
    except AttachmentParserError:
        raise
    except Exception as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc

    digest = hashlib.sha256(content).hexdigest()
    if digest != manifest.text_sha256:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_HASH_MISMATCH")
    try:
        normalized = validate_canonical_research_text_bytes(content)
    except ResearchTextContractError as exc:
        raise AttachmentParserError(exc.error_code) from exc
    if (
        normalized.utf8_bytes != content
        or normalized.sha256 != manifest.text_sha256
        or normalized.character_count != manifest.character_count
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_TEXT_INVALID")
    return normalized


def _read_validated_research_docx_bundle(
    output_bundle: Path,
    stdout: bytes,
) -> NormalizedResearchDocxText:
    if len(stdout) > _MAX_STDOUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
    manifest = ResearchDocxManifest.from_json_bytes(stdout)
    try:
        metadata = output_bundle.lstat()
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
    if (
        output_bundle.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    if metadata.st_size > _MAX_OUTPUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")

    expected_names = {manifest.text_relative_path}
    _preflight_zip_bundle(
        output_bundle,
        file_size=metadata.st_size,
        expected_names=expected_names,
    )
    try:
        with zipfile.ZipFile(output_bundle, mode="r") as archive:
            entries = archive.infolist()
            actual_names = {entry.filename for entry in entries}
            if len(entries) != 1 or actual_names != expected_names:
                raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
            content = _read_research_bundle_entry(archive, entries[0])
    except AttachmentParserError:
        raise
    except Exception as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc

    digest = hashlib.sha256(content).hexdigest()
    if digest != manifest.text_sha256:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_HASH_MISMATCH")
    try:
        normalized = validate_canonical_research_docx_bytes(content)
    except ResearchDocxContractError as exc:
        raise AttachmentParserError(exc.error_code) from exc
    if (
        normalized.utf8_bytes != content
        or normalized.sha256 != manifest.text_sha256
        or normalized.character_count != manifest.character_count
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_TEXT_INVALID")
    return normalized


def _read_research_bundle_entry(
    archive: zipfile.ZipFile,
    entry: zipfile.ZipInfo,
) -> bytes:
    if (
        entry.is_dir()
        or entry.flag_bits & 0x1
        or entry.compress_type != zipfile.ZIP_STORED
        or entry.compress_size != entry.file_size
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    if entry.file_size > _MAX_OUTPUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
    with archive.open(entry, mode="r") as input_file:
        content = input_file.read(entry.file_size + 1)
    if len(content) != entry.file_size:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED")
    return content


def _preflight_zip_bundle(
    output_bundle: Path,
    *,
    file_size: int,
    expected_names: set[str],
) -> None:
    expected_entry_count = len(expected_names)
    if (
        type(file_size) is not int
        or file_size < _ZIP_EOCD.size
        or not 1 <= expected_entry_count <= 120
        or any(type(name) is not str for name in expected_names)
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    tail_size = min(file_size, _ZIP_EOCD_MAX_SEARCH_BYTES)
    try:
        with output_bundle.open("rb") as source:
            source.seek(file_size - tail_size)
            tail = source.read(tail_size + 1)
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc
    if len(tail) != tail_size:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED")
    relative_eocd_offset = tail.rfind(_ZIP_EOCD_SIGNATURE)
    if relative_eocd_offset < 0:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    if len(tail) - relative_eocd_offset < _ZIP_EOCD.size:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    try:
        (
            signature,
            disk_number,
            central_directory_disk,
            entries_on_disk,
            total_entries,
            central_directory_size,
            central_directory_offset,
            comment_length,
        ) = _ZIP_EOCD.unpack_from(tail, relative_eocd_offset)
    except struct.error as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
    absolute_eocd_offset = file_size - tail_size + relative_eocd_offset
    if (
        signature != _ZIP_EOCD_SIGNATURE
        or absolute_eocd_offset + _ZIP_EOCD.size + comment_length != file_size
        or disk_number != 0
        or central_directory_disk != 0
        or entries_on_disk != total_entries
        or total_entries in {0xFFFF}
        or central_directory_size == 0xFFFFFFFF
        or central_directory_offset == 0xFFFFFFFF
        or total_entries != expected_entry_count
        or central_directory_size > _MAX_CENTRAL_DIRECTORY_BYTES
        or central_directory_size < total_entries * 46
        or central_directory_offset + central_directory_size
        != absolute_eocd_offset
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    locator_offset = relative_eocd_offset - 20
    if (
        locator_offset >= 0
        and tail[locator_offset : locator_offset + 4]
        == _ZIP64_EOCD_LOCATOR_SIGNATURE
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
    _preflight_zip_central_directory(
        output_bundle,
        central_directory_offset=central_directory_offset,
        central_directory_size=central_directory_size,
        expected_names=expected_names,
    )


def _preflight_zip_central_directory(
    output_bundle: Path,
    *,
    central_directory_offset: int,
    central_directory_size: int,
    expected_names: set[str],
) -> None:
    expected_entry_count = len(expected_names)
    try:
        with output_bundle.open("rb") as source:
            source.seek(central_directory_offset)
            central_directory = source.read(central_directory_size)
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc
    if len(central_directory) != central_directory_size:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED")

    offset = 0
    decoded_names: list[str] = []
    for _ in range(expected_entry_count):
        if len(central_directory) - offset < _ZIP_CENTRAL_HEADER.size:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        try:
            (
                signature,
                _version_made_by,
                version_needed,
                flags,
                _compression,
                _modified_time,
                _modified_date,
                _crc32,
                compressed_size,
                uncompressed_size,
                filename_length,
                extra_length,
                comment_length,
                disk_start,
                _internal_attributes,
                _external_attributes,
                local_header_offset,
            ) = _ZIP_CENTRAL_HEADER.unpack_from(central_directory, offset)
        except struct.error as exc:
            raise AttachmentParserError(
                "ATTACHMENT_OUTPUT_PATH_INVALID"
            ) from exc
        if (
            signature != _ZIP_CENTRAL_HEADER_SIGNATURE
            or version_needed >= 45
            or compressed_size == 0xFFFFFFFF
            or uncompressed_size == 0xFFFFFFFF
            or disk_start != 0
            or local_header_offset == 0xFFFFFFFF
            or local_header_offset >= central_directory_offset
        ):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        variable_start = offset + _ZIP_CENTRAL_HEADER.size
        variable_end = (
            variable_start
            + filename_length
            + extra_length
            + comment_length
        )
        if variable_end > len(central_directory):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        extra_start = variable_start + filename_length
        filename_bytes = central_directory[
            variable_start : variable_start + filename_length
        ]
        try:
            decoded_names.append(
                filename_bytes.decode("utf-8" if flags & 0x0800 else "cp437")
            )
        except UnicodeError as exc:
            raise AttachmentParserError(
                "ATTACHMENT_OUTPUT_PATH_INVALID"
            ) from exc
        _reject_zip64_extra_field(
            central_directory[extra_start : extra_start + extra_length]
        )
        offset = variable_end
    if (
        offset != len(central_directory)
        or len(set(decoded_names)) != len(decoded_names)
        or set(decoded_names) != expected_names
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")


def _reject_zip64_extra_field(extra: bytes) -> None:
    offset = 0
    while offset < len(extra):
        if len(extra) - offset < 4:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        header_id, data_size = struct.unpack_from("<HH", extra, offset)
        offset += 4
        if offset + data_size > len(extra) or header_id == 0x0001:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        offset += data_size


def _validate_research_ocr_jpeg(content: bytes) -> int:
    if (
        len(content) < 5
        or not content.startswith(b"\xff\xd8\xff")
        or not content.endswith(b"\xff\xd9")
    ):
        raise AttachmentParserError("ATTACHMENT_OUTPUT_IMAGE_INVALID")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
                if (
                    image.format != "JPEG"
                    or type(width) is not int
                    or type(height) is not int
                    or width <= 0
                    or height <= 0
                    or width * height > RESEARCH_PDF_MAX_PAGE_PIXELS
                ):
                    raise AttachmentParserError(
                        "ATTACHMENT_OUTPUT_IMAGE_INVALID"
                    )
                image.verify()
            with Image.open(io.BytesIO(content)) as decoded_image:
                if (
                    decoded_image.format != "JPEG"
                    or decoded_image.size != (width, height)
                ):
                    raise AttachmentParserError(
                        "ATTACHMENT_OUTPUT_IMAGE_INVALID"
                    )
                decoded_image.load()
            return width * height
    except AttachmentParserError:
        raise
    except Exception as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_IMAGE_INVALID") from exc


def _copy_and_revalidate_input(downloaded: Any, destination: Path) -> None:
    source = Path(_value(downloaded, "path"))
    try:
        metadata = source.lstat()
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_INPUT_PATH_INVALID") from exc
    if source.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise AttachmentParserError("ATTACHMENT_INPUT_PATH_INVALID")

    digest = hashlib.sha256()
    total = 0
    try:
        file_descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with source.open("rb") as input_file, os.fdopen(file_descriptor, "wb") as output:
            while True:
                chunk = input_file.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 40 * 1024 * 1024:
                    raise AttachmentParserError("ATTACHMENT_INPUT_LIMIT")
                output.write(chunk)
                digest.update(chunk)
    except AttachmentParserError:
        raise
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_INPUT_COPY_FAILED") from exc
    expected_size = _value(downloaded, "size_bytes")
    if (
        type(expected_size) is not int
        or total != expected_size
        or digest.hexdigest() != str(_value(downloaded, "content_sha256"))
    ):
        raise AttachmentParserError("ATTACHMENT_INPUT_CHANGED")


def _worker_error_code(stderr: bytes) -> str:
    if len(stderr) > _MAX_STDOUT_BYTES:
        return "ATTACHMENT_WORKER_FAILED"
    try:
        decoded = json.loads(stderr)
        code = decoded.get("error_code") if isinstance(decoded, dict) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        code = None
    if isinstance(code, str) and _SAFE_ERROR_PATTERN.fullmatch(code):
        return code
    return "ATTACHMENT_WORKER_FAILED"


def _value(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item[name]
    return getattr(item, name)
