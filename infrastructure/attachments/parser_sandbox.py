import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from infrastructure.attachments.parser_protocol import (
    AttachmentParserError,
    ParsedAttachment,
    ParsedAttachmentPage,
    WorkerManifest,
    WorkerRequest,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_RUNNER = _REPOSITORY_ROOT / "scripts" / "run_attachment_parser_sandbox.sh"
_DEFAULT_IMAGE = "eyeagent/attachment-parser:1"
_CID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ERROR_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_MAX_STDOUT_BYTES = 64 * 1024
_MAX_OUTPUT_BYTES = 64 * 1024 * 1024


CommandRunner = Callable[..., Awaitable[int]]


class AttachmentParserSandbox:
    def __init__(
        self,
        *,
        runner_path: Path | str = _DEFAULT_RUNNER,
        docker_binary: str = "docker",
        image: str = _DEFAULT_IMAGE,
        temp_root: Path | str | None = None,
        timeout_seconds: float = 120.0,
        uid_getter: Callable[[], int] = os.getuid,
        gid_getter: Callable[[], int] = os.getgid,
        label_factory: Callable[[], str] | None = None,
    ) -> None:
        self._runner_path = Path(runner_path)
        self._docker_binary = docker_binary
        self._image = image
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

    async def parse(self, downloaded: Any) -> ParsedAttachment:
        await self.preflight()
        self._ensure_temp_root()
        request_directory: Path | None = None
        cid_directory: Path | None = None
        cidfile: Path | None = None
        process: asyncio.subprocess.Process | None = None
        runner_launch_attempted = False

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
                output_directory = request_directory / "output"
                input_directory.mkdir(mode=0o700)
                output_directory.mkdir(mode=0o700)
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
            )
            label = self._label_factory()
            if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", label):
                raise AttachmentParserError("ATTACHMENT_SANDBOX_LABEL_INVALID")

            try:
                runner_launch_attempted = True
                process = await asyncio.create_subprocess_exec(
                    str(self._runner_path),
                    str(input_directory),
                    str(output_directory),
                    str(cidfile),
                    label,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except (OSError, asyncio.SubprocessError) as exc:
                raise AttachmentParserError("ATTACHMENT_SANDBOX_UNAVAILABLE") from exc

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(request.to_json_bytes()),
                    timeout=self._timeout_seconds,
                )
            except asyncio.TimeoutError as exc:
                await _stop_process(process)
                raise AttachmentParserError("ATTACHMENT_PARSER_TIMEOUT") from exc
            except asyncio.CancelledError:
                await asyncio.shield(_stop_process(process))
                raise

            if process.returncode != 0:
                raise AttachmentParserError(_worker_error_code(stderr))
            pages = _read_validated_pages(
                output_directory,
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
            if process is not None and process.returncode is None:
                await asyncio.shield(_stop_process(process))
            if cidfile is not None:
                await asyncio.shield(
                    _cleanup_container(
                        cidfile,
                        docker_binary=self._docker_binary,
                        wait_for_cidfile_seconds=(
                            1.0
                            if runner_launch_attempted and process is None
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
    wait_for_cidfile_seconds: float = 0.0,
) -> None:
    runner = command_runner or _run_cleanup_command
    try:
        deadline = asyncio.get_running_loop().time() + max(
            wait_for_cidfile_seconds,
            0.0,
        )
        container_id = ""
        while True:
            try:
                container_id = cidfile.read_text(encoding="ascii").strip()
                break
            except FileNotFoundError:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(0.05, remaining))
            except (OSError, UnicodeError):
                break
        if _CID_PATTERN.fullmatch(container_id):
            try:
                await runner(docker_binary, "kill", container_id)
            except BaseException:
                pass
            try:
                await runner(docker_binary, "rm", "-f", container_id)
            except BaseException:
                pass
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
    except (OSError, asyncio.SubprocessError):
        return 127


async def _run_capture_command(*command: str) -> tuple[int, bytes, bytes]:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
        return process.returncode or 0, stdout, stderr
    except (OSError, asyncio.SubprocessError, asyncio.TimeoutError):
        return 127, b"", b""


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


def _read_validated_pages(
    output_directory: Path,
    stdout: bytes,
    mime_type: str,
) -> tuple[ParsedAttachmentPage, ...]:
    if len(stdout) > _MAX_STDOUT_BYTES:
        raise AttachmentParserError("ATTACHMENT_WORKER_MANIFEST_INVALID")
    manifest = WorkerManifest.from_json_bytes(stdout)
    try:
        output_root = output_directory.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc

    expected_names = {page.relative_path for page in manifest.pages}
    try:
        actual_names = {entry.name for entry in output_root.iterdir()}
    except OSError as exc:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
    if actual_names != expected_names:
        raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")

    parsed_pages: list[ParsedAttachmentPage] = []
    total_bytes = 0
    for page in manifest.pages:
        candidate = output_root / page.relative_path
        try:
            metadata = candidate.lstat()
            real_path = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID") from exc
        if (
            candidate.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or real_path.parent != output_root
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise AttachmentParserError("ATTACHMENT_OUTPUT_PATH_INVALID")
        total_bytes += metadata.st_size
        if total_bytes > _MAX_OUTPUT_BYTES:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_LIMIT")
        try:
            content = real_path.read_bytes()
        except OSError as exc:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_READ_FAILED") from exc
        digest = hashlib.sha256(content).hexdigest()
        if digest != page.sha256:
            raise AttachmentParserError("ATTACHMENT_OUTPUT_HASH_MISMATCH")
        parsed_pages.append(
            ParsedAttachmentPage(
                page_number=page.page_number,
                mime_type=mime_type,
                sha256=digest,
                content=content,
            )
        )
    return tuple(parsed_pages)


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
    if (
        total != int(_value(downloaded, "size_bytes"))
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
