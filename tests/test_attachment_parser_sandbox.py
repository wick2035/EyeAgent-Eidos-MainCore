import asyncio
import hashlib
import io
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image

from infrastructure.attachments import parser_sandbox as sandbox_module
from infrastructure.attachments.parser_protocol import AttachmentParserError
from infrastructure.attachments.parser_protocol import (
    ParsedResearchPdf,
    ParsedResearchText,
    ResearchPdfManifest,
    ResearchPdfPageManifest,
    ResearchTextManifest,
)
from infrastructure.attachments.parser_sandbox import (
    AttachmentParserSandbox,
    _cleanup_container,
    _read_validated_bundle,
    _run_capture_command,
)
from infrastructure.attachments.secure_downloader import DownloadedAttachment
from utils.pdf_utils import RESEARCH_PDF_MAX_OCR_TOTAL_PIXELS, fitz


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_IMAGE = "eyeagent/attachment-parser:research-c2a"
_LABEL_KEY = "eyeagent.attachment-parser.run"


def _png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (8, 8), color=(20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


def _jpeg_bytes():
    output = io.BytesIO()
    Image.new("RGB", (8, 8), color=(80, 60, 40)).save(output, format="JPEG")
    return output.getvalue()


def _jpeg_bytes_with_size(width, height):
    output = io.BytesIO()
    Image.new("L", (width, height), color=80).save(output, format="JPEG")
    return output.getvalue()


def _entropy_corrupted_jpeg_bytes():
    image = Image.frombytes(
        "L",
        (512, 512),
        bytes(range(256)) * 1024,
    ).convert("RGB")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    corrupted = bytearray(output.getvalue())
    scan_offset = corrupted.find(b"\xff\xda")
    if scan_offset < 0:
        raise AssertionError("JPEG fixture has no start-of-scan marker")
    corrupted[scan_offset + 20 : scan_offset + 25] = b"\xff" * 5
    return bytes(corrupted)


def _corrupt_zip_filename_utf8(bundle, *, corrupt_central=True):
    payload = bytearray(bundle.read_bytes())
    eocd_offset = payload.rfind(b"PK\x05\x06")
    if eocd_offset < 0:
        raise AssertionError("ZIP fixture has no EOCD")
    central_offset = struct.unpack_from("<I", payload, eocd_offset + 16)[0]
    local_offset = struct.unpack_from("<I", payload, central_offset + 42)[0]
    local_flags = struct.unpack_from("<H", payload, local_offset + 6)[0]
    struct.pack_into("<H", payload, local_offset + 6, local_flags | 0x0800)
    payload[local_offset + 30] = 0xFF
    if corrupt_central:
        central_flags = struct.unpack_from("<H", payload, central_offset + 8)[0]
        struct.pack_into(
            "<H",
            payload,
            central_offset + 8,
            central_flags | 0x0800,
        )
        payload[central_offset + 46] = 0xFF
    bundle.write_bytes(payload)


class AttachmentParserSandboxUnitTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _downloaded(source):
        payload = source.read_bytes()
        return DownloadedAttachment(
            attachment_id="attachment-unit",
            analysis_attempt_id="attempt-unit",
            file_type="image",
            filename="fundus.png",
            mime_type="image/png",
            size_bytes=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
            page_count=None,
            path=source,
        )

    def test_default_image_uses_research_c2a_tag(self):
        self.assertEqual(AttachmentParserSandbox()._image, _IMAGE)

    async def test_setup_failure_removes_partially_created_request_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sandbox"
            sandbox = AttachmentParserSandbox(temp_root=root)
            sandbox.preflight = AsyncMock()
            real_mkdtemp = tempfile.mkdtemp
            calls = 0

            def fail_second_mkdtemp(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return real_mkdtemp(*args, **kwargs)
                raise OSError("cid directory unavailable")

            with patch(
                "infrastructure.attachments.parser_sandbox.tempfile.mkdtemp",
                side_effect=fail_second_mkdtemp,
            ):
                with self.assertRaisesRegex(
                    AttachmentParserError, "ATTACHMENT_SANDBOX_UNAVAILABLE"
                ):
                    await sandbox.parse(object())

            self.assertEqual(list(root.iterdir()), [])

    async def test_production_missing_isolation_command_refuses_to_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            source.write_bytes(_png_bytes())
            downloaded = DownloadedAttachment(
                attachment_id="attachment-1",
                analysis_attempt_id="attempt-1",
                file_type="image",
                filename="fundus.png",
                mime_type="image/png",
                size_bytes=source.stat().st_size,
                content_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                page_count=None,
                path=source,
            )
            sandbox = AttachmentParserSandbox(
                runner_path=root / "missing-runner.sh",
                docker_binary="missing-docker-command",
                temp_root=root / "sandbox",
            )

            with self.assertRaisesRegex(
                AttachmentParserError, "ATTACHMENT_SANDBOX_UNAVAILABLE"
            ):
                await sandbox.parse(downloaded)

    async def test_launch_subprocess_error_maps_to_safe_unavailable_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            source.write_bytes(_png_bytes())
            sandbox = AttachmentParserSandbox(
                runner_path="/bin/true",
                docker_binary="true",
                temp_root=root / "sandbox",
            )
            sandbox.preflight = AsyncMock()

            with patch(
                "infrastructure.attachments.parser_sandbox.asyncio.create_subprocess_exec",
                side_effect=subprocess.SubprocessError("sensitive launch detail"),
            ):
                with self.assertRaises(AttachmentParserError) as raised:
                    await sandbox.parse(self._downloaded(source))

            self.assertEqual(
                raised.exception.error_code,
                "ATTACHMENT_SANDBOX_UNAVAILABLE",
            )
            self.assertNotIn("sensitive", str(raised.exception))

    async def test_preflight_subprocess_error_maps_to_127(self):
        with patch(
            "infrastructure.attachments.parser_sandbox.asyncio.create_subprocess_exec",
            side_effect=subprocess.SubprocessError("sensitive preflight detail"),
        ):
            result = await _run_capture_command("docker", "info")

        self.assertEqual(result, (127, b"", b""))

    async def test_host_root_uid_fails_closed(self):
        sandbox = AttachmentParserSandbox(uid_getter=lambda: 0)

        with self.assertRaisesRegex(
            AttachmentParserError, "ATTACHMENT_SANDBOX_ROOT_FORBIDDEN"
        ):
            await sandbox.preflight()

    async def test_image_reference_is_strict_and_identical_for_preflight_and_run(self):
        invalid_images = (
            "",
            "--network=host",
            "eyeagent/parser:tag with-space",
            "eyeagent/parser:tag\n--privileged",
            " eyeagent/parser:tag",
        )
        for image in invalid_images:
            with self.subTest(image=repr(image)):
                with self.assertRaisesRegex(
                    AttachmentParserError,
                    "ATTACHMENT_SANDBOX_IMAGE_INVALID",
                ):
                    AttachmentParserSandbox(image=image)

        configured_image = "registry.test:5000/eyeagent/parser@sha256:" + "a" * 64
        sandbox = AttachmentParserSandbox(
            runner_path=(
                _REPOSITORY_ROOT / "scripts" / "run_attachment_parser_sandbox.sh"
            ),
            docker_binary="docker-test",
            image=configured_image,
            uid_getter=lambda: 1000,
        )
        with patch(
            "infrastructure.attachments.parser_sandbox.shutil.which",
            return_value="/usr/bin/docker-test",
        ), patch(
            "infrastructure.attachments.parser_sandbox._run_capture_command",
            new=AsyncMock(
                side_effect=[
                    (0, b"27.0", b""),
                    (0, b"65532:65532", b""),
                ]
            ),
        ) as capture:
            await sandbox.preflight()
        self.assertEqual(capture.await_args_list[1].args[3], configured_image)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            source.write_bytes(_png_bytes())
            run_sandbox = AttachmentParserSandbox(
                runner_path="/bin/true",
                docker_binary="docker-test",
                image=configured_image,
                temp_root=root / "sandbox",
            )
            run_sandbox.preflight = AsyncMock()

            class FailedProcess:
                returncode = 2

            create_process = AsyncMock(return_value=FailedProcess())
            with patch(
                "infrastructure.attachments.parser_sandbox.asyncio.create_subprocess_exec",
                create_process,
            ), patch(
                "infrastructure.attachments.parser_sandbox._communicate_bounded",
                new=AsyncMock(
                    return_value=(b"", b'{"error_code":"ATTACHMENT_WORKER_FAILED"}')
                ),
            ), patch(
                "infrastructure.attachments.parser_sandbox._cleanup_container",
                new=AsyncMock(),
            ):
                with self.assertRaises(AttachmentParserError):
                    await run_sandbox.parse(self._downloaded(source))

            launch_args = create_process.await_args.args
            self.assertEqual(launch_args[5], configured_image)

    async def test_cleanup_accepts_only_full_container_id_and_always_removes_cidfile(self):
        calls = []

        async def run_command(*command):
            calls.append(command)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            cidfile = Path(temporary) / "worker.cid"
            container_id = "a" * 64
            cidfile.write_text(container_id + "\n", encoding="ascii")

            await _cleanup_container(
                cidfile,
                docker_binary="docker",
                command_runner=run_command,
            )

            self.assertEqual(
                calls,
                [
                    ("docker", "kill", container_id),
                    ("docker", "rm", "-f", container_id),
                ],
            )
            self.assertFalse(cidfile.exists())

            cidfile.write_text("a" * 63 + "../escape", encoding="ascii")
            calls.clear()
            await _cleanup_container(
                cidfile,
                docker_binary="docker",
                command_runner=run_command,
            )
            self.assertEqual(calls, [])
            self.assertFalse(cidfile.exists())

    async def test_startup_interruption_waits_for_late_cidfile_then_cleans(self):
        calls = []

        async def run_command(*command):
            calls.append(command)
            return 0

        with tempfile.TemporaryDirectory() as temporary:
            cidfile = Path(temporary) / "worker.cid"
            container_id = "b" * 64

            async def write_late_cidfile():
                await asyncio.sleep(1.1)
                cidfile.write_text(container_id + "\n", encoding="ascii")

            writer = asyncio.create_task(write_late_cidfile())
            await _cleanup_container(
                cidfile,
                docker_binary="docker",
                command_runner=run_command,
                wait_for_cidfile_seconds=1.5,
            )
            await writer

            self.assertEqual(
                calls,
                [
                    ("docker", "kill", container_id),
                    ("docker", "rm", "-f", container_id),
                ],
            )
            self.assertFalse(cidfile.exists())

    async def test_missing_cid_uses_random_label_for_cleanup(self):
        calls = []
        container_id = "c" * 64

        async def run_command(*command):
            calls.append(command)
            return 0

        async def find_by_label(_docker_binary, label):
            self.assertEqual(label, "random-label")
            return (container_id,)

        with tempfile.TemporaryDirectory() as temporary:
            cidfile = Path(temporary) / "missing.cid"
            await _cleanup_container(
                cidfile,
                docker_binary="docker",
                command_runner=run_command,
                label="random-label",
                label_finder=find_by_label,
            )

        self.assertEqual(
            calls,
            [
                ("docker", "kill", container_id),
                ("docker", "rm", "-f", container_id),
            ],
        )

    async def test_cleanup_keeps_polling_for_late_label_after_cid(self):
        calls = []
        cid_container = "d" * 64
        late_container = "e" * 64

        async def run_command(*command):
            calls.append(command)
            return 0

        started_at = asyncio.get_running_loop().time()

        async def find_by_label(_docker_binary, _label):
            if asyncio.get_running_loop().time() - started_at > 1.05:
                return (late_container,)
            return ()

        with tempfile.TemporaryDirectory() as temporary:
            cidfile = Path(temporary) / "worker.cid"
            cidfile.write_text(cid_container, encoding="ascii")
            await _cleanup_container(
                cidfile,
                docker_binary="docker",
                command_runner=run_command,
                label="late-label",
                label_finder=find_by_label,
                wait_for_cidfile_seconds=1.2,
            )

        cleaned = [command[-1] for command in calls if command[1] == "kill"]
        self.assertEqual(cleaned, [cid_container, late_container])

    async def test_parse_cancellation_reclaims_launch_task_with_late_process(self):
        class LateProcess:
            def __init__(self):
                self.returncode = None
                self.killed = False

            def kill(self):
                self.killed = True
                self.returncode = -9

            async def wait(self):
                return self.returncode

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            source.write_bytes(_png_bytes())
            process = LateProcess()
            launched = asyncio.Event()

            async def delayed_launch(*_args, **_kwargs):
                await asyncio.sleep(1.1)
                launched.set()
                return process

            sandbox = AttachmentParserSandbox(
                temp_root=root / "sandbox",
                label_factory=lambda: "launch-cancel-label",
            )
            sandbox.preflight = AsyncMock()
            cleanup = AsyncMock()
            with patch(
                "infrastructure.attachments.parser_sandbox.asyncio.create_subprocess_exec",
                side_effect=delayed_launch,
            ), patch(
                "infrastructure.attachments.parser_sandbox._cleanup_container",
                cleanup,
            ):
                task = asyncio.create_task(sandbox.parse(self._downloaded(source)))
                await asyncio.sleep(0.01)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

            self.assertTrue(launched.is_set())
            self.assertTrue(process.killed)
            cleanup.assert_awaited_once()
            cleanup_kwargs = cleanup.await_args.kwargs
            self.assertEqual(cleanup_kwargs["label"], "launch-cancel-label")
            self.assertGreater(cleanup_kwargs["wait_for_cidfile_seconds"], 1.0)

    async def test_real_worker_stdout_and_stderr_are_bounded_during_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            source.write_bytes(_png_bytes())
            downloaded = self._downloaded(source)
            for stream_name in ("stdout", "stderr"):
                with self.subTest(stream_name=stream_name):
                    runner = root / f"overflow-{stream_name}.py"
                    runner.write_text(
                        "#!" + sys.executable + "\n"
                        "import sys, time\n"
                        "sys.stdin.buffer.read()\n"
                        f"stream = sys.{stream_name}.buffer\n"
                        "stream.write(b'x' * (64 * 1024 + 1))\n"
                        "stream.flush()\n"
                        "time.sleep(30)\n",
                        encoding="utf-8",
                    )
                    os.chmod(runner, 0o700)
                    sandbox_root = root / f"sandbox-{stream_name}"
                    sandbox = AttachmentParserSandbox(
                        runner_path=runner,
                        docker_binary="true",
                        temp_root=sandbox_root,
                        timeout_seconds=5,
                    )
                    sandbox.preflight = AsyncMock()

                    with self.assertRaisesRegex(
                        AttachmentParserError,
                        "ATTACHMENT_WORKER_OUTPUT_LIMIT",
                    ):
                        await asyncio.wait_for(
                            sandbox.parse(downloaded),
                            timeout=1,
                        )
                    self.assertEqual(list(sandbox_root.iterdir()), [])

    async def test_host_rejects_output_traversal_and_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_bundle = Path(temporary) / "output.bundle"
            with zipfile.ZipFile(
                output_bundle,
                mode="w",
                compression=zipfile.ZIP_STORED,
            ) as archive:
                archive.writestr("page-0001.jpg", b"page")
            os.chmod(output_bundle, 0o600)
            digest = hashlib.sha256(b"page").hexdigest()
            traversal = json.dumps(
                {
                    "pages": [
                        {
                            "page_number": 1,
                            "relative_path": "../escape.jpg",
                            "sha256": digest,
                        }
                    ]
                }
            ).encode()
            mismatch = json.dumps(
                {
                    "pages": [
                        {
                            "page_number": 1,
                            "relative_path": "page-0001.jpg",
                            "sha256": "0" * 64,
                        }
                    ]
                }
            ).encode()

            with self.assertRaisesRegex(
                AttachmentParserError, "ATTACHMENT_OUTPUT_PATH_INVALID"
            ):
                _read_validated_bundle(
                    output_bundle,
                    traversal,
                    "image/jpeg",
                )
            with self.assertRaisesRegex(
                AttachmentParserError, "ATTACHMENT_OUTPUT_HASH_MISMATCH"
            ):
                _read_validated_bundle(
                    output_bundle,
                    mismatch,
                    "image/jpeg",
                )

    async def test_host_validates_research_text_ocr_hashes_and_exact_entry_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_bundle = root / "output.bundle"
            text = "科研正文 1234567890 ABCDEFGHIJ".encode("utf-8")
            image = _jpeg_bytes()
            manifest = ResearchPdfManifest(
                pages=(
                    ResearchPdfPageManifest(
                        page_number=1,
                        text_relative_path="page-0001.txt",
                        text_sha256=hashlib.sha256(text).hexdigest(),
                        ocr_image_relative_path="page-0001-ocr.jpg",
                        ocr_image_sha256=hashlib.sha256(image).hexdigest(),
                    ),
                )
            )

            def write_bundle(*, extra=False):
                with zipfile.ZipFile(
                    output_bundle,
                    mode="w",
                    compression=zipfile.ZIP_STORED,
                ) as archive:
                    archive.writestr("page-0001.txt", text)
                    archive.writestr("page-0001-ocr.jpg", image)
                    if extra:
                        archive.writestr("extra.bin", b"extra")
                os.chmod(output_bundle, 0o600)

            write_bundle()
            pages = sandbox_module._read_validated_research_bundle(
                output_bundle,
                manifest.to_json_bytes(),
                expected_page_count=1,
            )
            self.assertEqual(pages[0].text, text.decode("utf-8"))
            self.assertEqual(pages[0].ocr_image_content, image)

            bad_hash = json.loads(manifest.to_json_bytes())
            bad_hash["pages"][0]["text_sha256"] = "0" * 64
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_HASH_MISMATCH",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    json.dumps(bad_hash).encode("utf-8"),
                    expected_page_count=1,
                )

            traversal = json.loads(manifest.to_json_bytes())
            traversal["pages"][0]["text_relative_path"] = "../page-0001.txt"
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_PATH_INVALID",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    json.dumps(traversal).encode("utf-8"),
                    expected_page_count=1,
                )

            write_bundle(extra=True)
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_PATH_INVALID",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    manifest.to_json_bytes(),
                    expected_page_count=1,
                )

            write_bundle()
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_PAGE_COUNT_MISMATCH",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    manifest.to_json_bytes(),
                    expected_page_count=2,
                )

            invalid_image = b"not-a-jpeg"
            invalid_manifest = ResearchPdfManifest(
                pages=(
                    ResearchPdfPageManifest(
                        page_number=1,
                        text_relative_path="page-0001.txt",
                        text_sha256=hashlib.sha256(text).hexdigest(),
                        ocr_image_relative_path="page-0001-ocr.jpg",
                        ocr_image_sha256=hashlib.sha256(invalid_image).hexdigest(),
                    ),
                )
            )
            with zipfile.ZipFile(
                output_bundle,
                mode="w",
                compression=zipfile.ZIP_STORED,
            ) as archive:
                archive.writestr("page-0001.txt", text)
                archive.writestr("page-0001-ocr.jpg", invalid_image)
            os.chmod(output_bundle, 0o600)
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_IMAGE_INVALID",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    invalid_manifest.to_json_bytes(),
                    expected_page_count=1,
                )

            huge_image = bytearray(_jpeg_bytes())
            sof_offset = huge_image.find(b"\xff\xc0")
            self.assertGreaterEqual(sof_offset, 0)
            struct.pack_into(">HH", huge_image, sof_offset + 5, 0xFFFF, 0xFFFF)
            huge_image_bytes = bytes(huge_image)
            huge_manifest = ResearchPdfManifest(
                pages=(
                    ResearchPdfPageManifest(
                        page_number=1,
                        text_relative_path="page-0001.txt",
                        text_sha256=hashlib.sha256(text).hexdigest(),
                        ocr_image_relative_path="page-0001-ocr.jpg",
                        ocr_image_sha256=hashlib.sha256(
                            huge_image_bytes
                        ).hexdigest(),
                    ),
                )
            )
            with zipfile.ZipFile(
                output_bundle,
                mode="w",
                compression=zipfile.ZIP_STORED,
            ) as archive:
                archive.writestr("page-0001.txt", text)
                archive.writestr("page-0001-ocr.jpg", huge_image_bytes)
            os.chmod(output_bundle, 0o600)
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_IMAGE_INVALID",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    huge_manifest.to_json_bytes(),
                    expected_page_count=1,
                )

    async def test_host_validates_research_text_manifest_and_canonical_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_bundle = root / "output.bundle"
            canonical_text = "Caf\u00e9\nline"
            canonical = canonical_text.encode("utf-8")
            manifest = ResearchTextManifest(
                profile="research_text_v1",
                text_relative_path="document.txt",
                text_sha256=hashlib.sha256(canonical).hexdigest(),
                character_count=len(canonical_text),
            )

            def write_bundle(content=canonical, *, extra=False):
                with zipfile.ZipFile(
                    output_bundle,
                    mode="w",
                    compression=zipfile.ZIP_STORED,
                ) as archive:
                    archive.writestr("document.txt", content)
                    if extra:
                        archive.writestr("extra.bin", b"extra")
                os.chmod(output_bundle, 0o600)

            write_bundle()
            parsed = sandbox_module._read_validated_research_text_bundle(
                output_bundle,
                manifest.to_json_bytes(),
            )
            self.assertEqual(parsed.text, canonical_text)
            self.assertEqual(parsed.utf8_bytes, canonical)
            self.assertEqual(parsed.sha256, manifest.text_sha256)
            self.assertEqual(parsed.character_count, manifest.character_count)

            decoded = json.loads(manifest.to_json_bytes())
            invalid_manifests = (
                (
                    {**decoded, "profile": "research_pdf_v1"},
                    "ATTACHMENT_WORKER_MANIFEST_INVALID",
                ),
                (
                    {**decoded, "unknown": True},
                    "ATTACHMENT_WORKER_MANIFEST_INVALID",
                ),
                (
                    {**decoded, "text_relative_path": "../document.txt"},
                    "ATTACHMENT_OUTPUT_PATH_INVALID",
                ),
                (
                    {**decoded, "text_sha256": "0" * 64},
                    "ATTACHMENT_OUTPUT_HASH_MISMATCH",
                ),
                (
                    {**decoded, "character_count": len(canonical_text) + 1},
                    "ATTACHMENT_OUTPUT_TEXT_INVALID",
                ),
            )
            for mutation, error_code in invalid_manifests:
                with self.subTest(mutation=mutation):
                    write_bundle()
                    with self.assertRaisesRegex(AttachmentParserError, error_code):
                        sandbox_module._read_validated_research_text_bundle(
                            output_bundle,
                            json.dumps(mutation).encode("utf-8"),
                        )

            invalid_utf8 = b"\xff"
            invalid_utf8_manifest = ResearchTextManifest(
                profile="research_text_v1",
                text_relative_path="document.txt",
                text_sha256=hashlib.sha256(invalid_utf8).hexdigest(),
                character_count=1,
            )
            write_bundle(invalid_utf8)
            with self.assertRaisesRegex(
                AttachmentParserError,
                "RESEARCH_TXT_ENCODING_UNSUPPORTED",
            ):
                sandbox_module._read_validated_research_text_bundle(
                    output_bundle,
                    invalid_utf8_manifest.to_json_bytes(),
                )

            noncanonical = b"Cafe\xcc\x81\r\nline"
            noncanonical_manifest = ResearchTextManifest(
                profile="research_text_v1",
                text_relative_path="document.txt",
                text_sha256=hashlib.sha256(noncanonical).hexdigest(),
                character_count=len(noncanonical.decode("utf-8")),
            )
            write_bundle(noncanonical)
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_TEXT_INVALID",
            ):
                sandbox_module._read_validated_research_text_bundle(
                    output_bundle,
                    noncanonical_manifest.to_json_bytes(),
                )

            write_bundle(extra=True)
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_PATH_INVALID",
            ):
                sandbox_module._read_validated_research_text_bundle(
                    output_bundle,
                    manifest.to_json_bytes(),
                )

            write_bundle()
            with patch(
                "infrastructure.attachments.parser_sandbox._MAX_OUTPUT_BYTES",
                output_bundle.stat().st_size - 1,
            ):
                with self.assertRaisesRegex(
                    AttachmentParserError,
                    "ATTACHMENT_OUTPUT_LIMIT",
                ):
                    sandbox_module._read_validated_research_text_bundle(
                        output_bundle,
                        manifest.to_json_bytes(),
                    )

    async def test_host_rejects_more_than_twenty_research_ocr_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_bundle = Path(temporary) / "output.bundle"
            output_bundle.touch(mode=0o600)
            empty_hash = hashlib.sha256(b"").hexdigest()
            jpeg_hash = hashlib.sha256(_jpeg_bytes()).hexdigest()
            manifest = ResearchPdfManifest(
                pages=tuple(
                    ResearchPdfPageManifest(
                        page_number=page_number,
                        text_relative_path=f"page-{page_number:04d}.txt",
                        text_sha256=empty_hash,
                        ocr_image_relative_path=(
                            f"page-{page_number:04d}-ocr.jpg"
                        ),
                        ocr_image_sha256=jpeg_hash,
                    )
                    for page_number in range(1, 22)
                )
            )

            with self.assertRaisesRegex(
                AttachmentParserError,
                "RESEARCH_PDF_OCR_PAGE_LIMIT",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    manifest.to_json_bytes(),
                    expected_page_count=21,
                )

    async def test_host_fully_decodes_jpeg_and_limits_total_ocr_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_bundle = root / "output.bundle"
            corrupted = _entropy_corrupted_jpeg_bytes()
            with Image.open(io.BytesIO(corrupted)) as image:
                image.verify()
            with self.assertRaises(OSError):
                with Image.open(io.BytesIO(corrupted)) as image:
                    image.load()

            empty_hash = hashlib.sha256(b"").hexdigest()
            corrupted_manifest = ResearchPdfManifest(
                pages=(
                    ResearchPdfPageManifest(
                        page_number=1,
                        text_relative_path="page-0001.txt",
                        text_sha256=empty_hash,
                        ocr_image_relative_path="page-0001-ocr.jpg",
                        ocr_image_sha256=hashlib.sha256(corrupted).hexdigest(),
                    ),
                )
            )
            with zipfile.ZipFile(
                output_bundle,
                mode="w",
                compression=zipfile.ZIP_STORED,
            ) as archive:
                archive.writestr("page-0001.txt", b"")
                archive.writestr("page-0001-ocr.jpg", corrupted)
            os.chmod(output_bundle, 0o600)
            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_IMAGE_INVALID",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    corrupted_manifest.to_json_bytes(),
                    expected_page_count=1,
                )

            page_limit_image = _jpeg_bytes_with_size(5000, 5000)
            one_pixel_image = _jpeg_bytes_with_size(1, 1)

            def write_images(images):
                pages = []
                with zipfile.ZipFile(
                    output_bundle,
                    mode="w",
                    compression=zipfile.ZIP_STORED,
                ) as archive:
                    for page_number, image_bytes in enumerate(images, start=1):
                        text_path = f"page-{page_number:04d}.txt"
                        image_path = f"page-{page_number:04d}-ocr.jpg"
                        archive.writestr(text_path, b"")
                        archive.writestr(image_path, image_bytes)
                        pages.append(
                            ResearchPdfPageManifest(
                                page_number=page_number,
                                text_relative_path=text_path,
                                text_sha256=empty_hash,
                                ocr_image_relative_path=image_path,
                                ocr_image_sha256=hashlib.sha256(
                                    image_bytes
                                ).hexdigest(),
                            )
                        )
                os.chmod(output_bundle, 0o600)
                return ResearchPdfManifest(pages=tuple(pages))

            exact_images = [page_limit_image] * 4
            exact_manifest = write_images(exact_images)
            exact_pages = sandbox_module._read_validated_research_bundle(
                output_bundle,
                exact_manifest.to_json_bytes(),
                expected_page_count=4,
            )
            self.assertEqual(len(exact_pages), 4)
            self.assertEqual(
                4 * 5000 * 5000,
                RESEARCH_PDF_MAX_OCR_TOTAL_PIXELS,
            )

            over_manifest = write_images(exact_images + [one_pixel_image])
            with self.assertRaisesRegex(
                AttachmentParserError,
                "RESEARCH_PDF_OCR_TOTAL_PIXEL_LIMIT",
            ):
                sandbox_module._read_validated_research_bundle(
                    output_bundle,
                    over_manifest.to_json_bytes(),
                    expected_page_count=5,
                )

    async def test_bundle_readers_normalize_invalid_utf8_filename_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assistant_bundle = root / "assistant.bundle"
            assistant_content = b"page"
            with zipfile.ZipFile(
                assistant_bundle,
                mode="w",
                compression=zipfile.ZIP_STORED,
            ) as archive:
                archive.writestr("page-0001.jpg", assistant_content)
            os.chmod(assistant_bundle, 0o600)
            _corrupt_zip_filename_utf8(assistant_bundle)
            assistant_manifest = json.dumps(
                {
                    "pages": [
                        {
                            "page_number": 1,
                            "relative_path": "page-0001.jpg",
                            "sha256": hashlib.sha256(
                                assistant_content
                            ).hexdigest(),
                        }
                    ]
                }
            ).encode("utf-8")

            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_PATH_INVALID",
            ):
                _read_validated_bundle(
                    assistant_bundle,
                    assistant_manifest,
                    "image/jpeg",
                )

            research_bundle = root / "research.bundle"
            research_text = b"research"
            with zipfile.ZipFile(
                research_bundle,
                mode="w",
                compression=zipfile.ZIP_STORED,
            ) as archive:
                archive.writestr("page-0001.txt", research_text)
            os.chmod(research_bundle, 0o600)
            _corrupt_zip_filename_utf8(
                research_bundle,
                corrupt_central=False,
            )
            research_manifest = ResearchPdfManifest(
                pages=(
                    ResearchPdfPageManifest(
                        page_number=1,
                        text_relative_path="page-0001.txt",
                        text_sha256=hashlib.sha256(research_text).hexdigest(),
                    ),
                )
            )

            with self.assertRaisesRegex(
                AttachmentParserError,
                "ATTACHMENT_OUTPUT_READ_FAILED",
            ):
                sandbox_module._read_validated_research_bundle(
                    research_bundle,
                    research_manifest.to_json_bytes(),
                    expected_page_count=1,
                )

    async def test_bundle_readers_preflight_eocd_before_zipfile_construction(self):
        manifest = json.dumps(
            {
                "pages": [
                    {
                        "page_number": 1,
                        "relative_path": "page-0001.jpg",
                        "sha256": hashlib.sha256(b"page").hexdigest(),
                    }
                ]
            }
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            many_entries = root / "many-entries.bundle"
            with zipfile.ZipFile(
                many_entries,
                mode="w",
                compression=zipfile.ZIP_STORED,
            ) as archive:
                for index in range(50_000):
                    archive.writestr(f"entry-{index:05d}", b"")
            os.chmod(many_entries, 0o600)

            valid = root / "valid.bundle"
            with zipfile.ZipFile(
                valid,
                mode="w",
                compression=zipfile.ZIP_STORED,
            ) as archive:
                archive.writestr("page-0001.jpg", b"page")
            valid_bytes = valid.read_bytes()
            eocd_offset = valid_bytes.rfind(b"PK\x05\x06")
            self.assertGreaterEqual(eocd_offset, 0)

            zip64 = bytearray(valid_bytes)
            struct.pack_into("<HH", zip64, eocd_offset + 8, 0xFFFF, 0xFFFF)
            zip64_bundle = root / "zip64.bundle"
            zip64_bundle.write_bytes(zip64)
            os.chmod(zip64_bundle, 0o600)

            zip64_extra_bundle = root / "zip64-extra.bundle"
            zip64_info = zipfile.ZipInfo("page-0001.jpg")
            zip64_info.compress_type = zipfile.ZIP_STORED
            zip64_info.extract_version = 45
            zip64_info.extra = struct.pack("<HH", 0x0001, 0)
            with zipfile.ZipFile(zip64_extra_bundle, mode="w") as archive:
                archive.writestr(zip64_info, b"page")
            os.chmod(zip64_extra_bundle, 0o600)

            multidisk = bytearray(valid_bytes)
            struct.pack_into("<HH", multidisk, eocd_offset + 4, 1, 1)
            multidisk_bundle = root / "multidisk.bundle"
            multidisk_bundle.write_bytes(multidisk)
            os.chmod(multidisk_bundle, 0o600)

            fake_eocd_bundle = root / "fake-eocd.bundle"
            fake_eocd_bundle.write_bytes(
                b"not-a-zip"
                + struct.pack(
                    "<4sHHHHIIH",
                    b"PK\x05\x06",
                    0,
                    0,
                    1,
                    1,
                    46,
                    999_999,
                    0,
                )
            )
            os.chmod(fake_eocd_bundle, 0o600)

            for bundle in (
                many_entries,
                zip64_bundle,
                zip64_extra_bundle,
                multidisk_bundle,
                fake_eocd_bundle,
            ):
                with self.subTest(bundle=bundle.name), patch(
                    "infrastructure.attachments.parser_sandbox.zipfile.ZipFile",
                    side_effect=AssertionError(
                        "ZipFile must not be constructed before EOCD preflight"
                    ),
                ):
                    with self.assertRaises(AttachmentParserError):
                        _read_validated_bundle(
                            bundle,
                            manifest,
                            "image/jpeg",
                        )

    async def test_parse_research_profile_returns_text_and_optional_ocr_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.pdf"
            source.write_bytes(b"%PDF-fake")
            text = "科研正文 1234567890 ABCDEFGHIJ"
            image = _jpeg_bytes()
            runner = root / "research-runner.py"
            runner.write_text(
                "#!" + sys.executable + "\n"
                "import hashlib, json, os, sys, zipfile\n"
                "request = json.loads(sys.stdin.buffer.read())\n"
                "if request.get('profile') != 'research_pdf_v1':\n"
                "    raise SystemExit(9)\n"
                f"text = {text.encode('utf-8')!r}\n"
                f"image = {image!r}\n"
                "with zipfile.ZipFile(sys.argv[2], 'w', compression=zipfile.ZIP_STORED) as archive:\n"
                "    archive.writestr('page-0001.txt', text)\n"
                "    archive.writestr('page-0001-ocr.jpg', image)\n"
                "manifest = {'profile': 'research_pdf_v1', 'pages': [{'page_number': 1, "
                "'text_relative_path': 'page-0001.txt', 'text_sha256': hashlib.sha256(text).hexdigest(), "
                "'ocr_image_relative_path': 'page-0001-ocr.jpg', 'ocr_image_sha256': hashlib.sha256(image).hexdigest()}]}\n"
                "sys.stdout.write(json.dumps(manifest, separators=(',', ':')))\n",
                encoding="utf-8",
            )
            os.chmod(runner, 0o700)
            payload = source.read_bytes()
            downloaded = DownloadedAttachment(
                attachment_id="research-attachment",
                analysis_attempt_id="research-attempt",
                file_type="pdf",
                filename="paper.pdf",
                mime_type="application/pdf",
                size_bytes=len(payload),
                content_sha256=hashlib.sha256(payload).hexdigest(),
                page_count=1,
                path=source,
                document_version=7,
            )
            sandbox = AttachmentParserSandbox(
                runner_path=runner,
                docker_binary="true",
                temp_root=root / "sandbox",
            )
            sandbox.preflight = AsyncMock()
            with patch(
                "infrastructure.attachments.parser_sandbox._cleanup_container",
                new=AsyncMock(),
            ):
                parsed = await sandbox.parse(
                    downloaded,
                    profile="research_pdf_v1",
                )

            self.assertIsInstance(parsed, ParsedResearchPdf)
            self.assertEqual(parsed.attachment_id, "research-attachment")
            self.assertEqual(parsed.document_version, 7)
            self.assertEqual(parsed.pages[0].text, text)
            self.assertEqual(parsed.pages[0].ocr_image_content, image)
            self.assertEqual(list((root / "sandbox").iterdir()), [])

    async def test_parse_research_text_profile_returns_canonical_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_bytes("Caf\u00e9\nline".encode("utf-8"))
            runner = root / "research-text-runner.py"
            runner.write_text(
                "#!" + sys.executable + "\n"
                "import hashlib, json, sys, zipfile\n"
                "request = json.loads(sys.stdin.buffer.read())\n"
                "if request != {'input_filename': 'attachment.bin', 'file_type': 'text', "
                "'mime_type': 'text/plain', 'declared_page_count': None, "
                "'profile': 'research_text_v1'}:\n"
                "    raise SystemExit(9)\n"
                "text = 'Caf\\u00e9\\nline'.encode('utf-8')\n"
                "with zipfile.ZipFile(sys.argv[2], 'w', compression=zipfile.ZIP_STORED) as archive:\n"
                "    archive.writestr('document.txt', text)\n"
                "manifest = {'profile': 'research_text_v1', 'text_relative_path': 'document.txt', "
                "'text_sha256': hashlib.sha256(text).hexdigest(), 'character_count': 9}\n"
                "sys.stdout.write(json.dumps(manifest, separators=(',', ':')))\n",
                encoding="utf-8",
            )
            os.chmod(runner, 0o700)
            payload = source.read_bytes()
            downloaded = DownloadedAttachment(
                attachment_id="research-text-attachment",
                analysis_attempt_id="research-text-attempt",
                file_type="text",
                filename="notes.txt",
                mime_type="text/plain",
                size_bytes=len(payload),
                content_sha256=hashlib.sha256(payload).hexdigest(),
                page_count=None,
                path=source,
                document_version=7,
            )
            sandbox = AttachmentParserSandbox(
                runner_path=runner,
                docker_binary="true",
                temp_root=root / "sandbox",
            )
            sandbox.preflight = AsyncMock()
            with patch(
                "infrastructure.attachments.parser_sandbox._cleanup_container",
                new=AsyncMock(),
            ):
                parsed = await sandbox.parse(
                    downloaded,
                    profile="research_text_v1",
                )

            self.assertIsInstance(parsed, ParsedResearchText)
            self.assertEqual(parsed.attachment_id, "research-text-attachment")
            self.assertEqual(parsed.document_version, 7)
            self.assertEqual(parsed.mime_type, "text/plain")
            self.assertEqual(parsed.text, "Caf\u00e9\nline")
            self.assertEqual(
                parsed.text_sha256,
                hashlib.sha256(payload).hexdigest(),
            )
            self.assertEqual(parsed.character_count, len("Caf\u00e9\nline"))
            self.assertEqual(list((root / "sandbox").iterdir()), [])

    async def test_research_worker_error_code_is_preserved_by_host(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.pdf"
            source.write_bytes(b"%PDF-fake")
            runner = root / "failing-research-runner.py"
            runner.write_text(
                "#!" + sys.executable + "\n"
                "import sys\n"
                "sys.stdin.buffer.read()\n"
                "sys.stderr.write('{\"error_code\":\"RESEARCH_PDF_ENCRYPTED\"}')\n"
                "raise SystemExit(2)\n",
                encoding="utf-8",
            )
            os.chmod(runner, 0o700)
            payload = source.read_bytes()
            downloaded = DownloadedAttachment(
                attachment_id="research-error",
                analysis_attempt_id="research-error-attempt",
                file_type="pdf",
                filename="paper.pdf",
                mime_type="application/pdf",
                size_bytes=len(payload),
                content_sha256=hashlib.sha256(payload).hexdigest(),
                page_count=1,
                path=source,
                document_version=1,
            )
            sandbox = AttachmentParserSandbox(
                runner_path=runner,
                docker_binary="true",
                temp_root=root / "sandbox",
            )
            sandbox.preflight = AsyncMock()
            with patch(
                "infrastructure.attachments.parser_sandbox._cleanup_container",
                new=AsyncMock(),
            ):
                with self.assertRaises(AttachmentParserError) as raised:
                    await sandbox.parse(
                        downloaded,
                        profile="research_pdf_v1",
                    )
            self.assertEqual(
                raised.exception.error_code,
                "RESEARCH_PDF_ENCRYPTED",
            )

    async def test_fixed_runner_contains_all_required_isolation_flags(self):
        runner = (
            _REPOSITORY_ROOT / "scripts" / "run_attachment_parser_sandbox.sh"
        ).read_text(encoding="utf-8")
        required_fragments = (
            "--network none",
            "--read-only",
            "--cap-drop ALL",
            "--security-opt no-new-privileges",
            "--pids-limit 64",
            "--memory 768m",
            "--cpus 1",
            "--tmpfs /tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs /output:rw,noexec,nosuid,size=64m",
            '$(id -u):$(id -g)',
            "--rm",
            "--cidfile",
            ":/input:ro",
            ":/output.bundle:rw",
            'image_ref="$5"',
            '"$image_ref"',
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runner)
        self.assertNotIn("output-staging", runner)
        self.assertNotIn("eyeagent/attachment-parser:1", runner)


class AttachmentParserSandboxDockerIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        subprocess.run(
            ["docker", "image", "inspect", _IMAGE],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        os.chmod(self.root, 0o700)
        self.source = self.root / "source.png"
        self.source.write_bytes(_png_bytes())
        os.chmod(self.source, 0o600)
        payload = self.source.read_bytes()
        self.downloaded = DownloadedAttachment(
            attachment_id="attachment-integration",
            analysis_attempt_id="attempt-integration",
            file_type="image",
            filename="fundus.png",
            mime_type="image/png",
            size_bytes=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
            page_count=None,
            path=self.source,
        )

    async def asyncTearDown(self):
        subprocess.run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"label={_LABEL_KEY}",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._temporary.cleanup()

    def _containers_for_label(self, label):
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"label={_LABEL_KEY}={label}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return tuple(line for line in result.stdout.splitlines() if line)

    async def _wait_for_container(self, label):
        for _ in range(100):
            containers = self._containers_for_label(label)
            if containers:
                return containers
            await asyncio.sleep(0.02)
        self.fail("test container did not start")

    def _custom_runner(self, name, python_code):
        path = self.root / name
        path.write_text(
            "#!/bin/bash\n"
            "set -eu\n"
            'input_dir="$1"\n'
            'output_bundle="$2"\n'
            'cidfile="$3"\n'
            'label="$4"\n'
            "docker run --network none --read-only --cap-drop ALL "
            "--security-opt no-new-privileges --pids-limit 64 --memory 768m "
            "--cpus 1 --tmpfs /tmp:rw,noexec,nosuid,size=64m "
            '--tmpfs /output:rw,noexec,nosuid,size=64m,mode=0700,uid="$(id -u)",gid="$(id -g)" '
            '--user "$(id -u):$(id -g)" --rm --cidfile "$cidfile" '
            f'--label "{_LABEL_KEY}=$label" '
            '-v "$input_dir:/input:ro" -v "$output_bundle:/output.bundle:rw" '
            f"--entrypoint python {_IMAGE} -c {json.dumps(python_code)}\n",
            encoding="utf-8",
        )
        os.chmod(path, 0o700)
        return path

    async def test_image_user_permissions_read_only_input_network_none_and_cleanup(self):
        label = "integration-success"
        sandbox_root = self.root / "sandbox-success"
        sandbox = AttachmentParserSandbox(
            temp_root=sandbox_root,
            label_factory=lambda: label,
        )

        parsed = await sandbox.parse(self.downloaded)

        configured_user = subprocess.run(
            ["docker", "image", "inspect", _IMAGE, "--format", "{{.Config.User}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertTrue(configured_user)
        self.assertNotIn(configured_user.lower(), {"root", "0", "0:0"})
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.source.stat().st_mode), 0o600)
        self.assertEqual(parsed.pages[0].content, self.source.read_bytes())
        self.assertEqual(self._containers_for_label(label), ())
        self.assertEqual(list(sandbox_root.iterdir()), [])

    async def test_research_mixed_pdf_returns_physical_text_and_only_one_ocr_image(self):
        source = self.root / "mixed-research.pdf"
        document = fitz.open()
        digital_page = document.new_page()
        digital_page.insert_text(
            (72, 72),
            "Research document 1234567890 ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        )
        document.new_page()
        document.save(source)
        document.close()
        os.chmod(source, 0o600)
        payload = source.read_bytes()
        downloaded = DownloadedAttachment(
            attachment_id="research-integration",
            analysis_attempt_id="research-integration-attempt",
            file_type="pdf",
            filename="mixed.pdf",
            mime_type="application/pdf",
            size_bytes=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
            page_count=2,
            path=source,
            document_version=9,
        )
        label = "integration-research-mixed"
        sandbox_root = self.root / "sandbox-research"
        sandbox = AttachmentParserSandbox(
            temp_root=sandbox_root,
            label_factory=lambda: label,
        )

        parsed = await sandbox.parse(downloaded, profile="research_pdf_v1")

        self.assertIsInstance(parsed, ParsedResearchPdf)
        self.assertEqual(parsed.document_version, 9)
        self.assertEqual([page.page_number for page in parsed.pages], [1, 2])
        self.assertIn("Research document", parsed.pages[0].text)
        self.assertIsNone(parsed.pages[0].ocr_image_content)
        self.assertEqual(parsed.pages[1].text, "")
        self.assertTrue(parsed.pages[1].ocr_image_content.startswith(b"\xff\xd8"))
        self.assertEqual(self._containers_for_label(label), ())
        self.assertEqual(list(sandbox_root.iterdir()), [])

    async def test_research_text_returns_normalized_utf8_and_metadata(self):
        source = self.root / "research-notes.txt"
        source.write_bytes(b"\xef\xbb\xbfCafe\xcc\x81\r\nline")
        os.chmod(source, 0o600)
        payload = source.read_bytes()
        downloaded = DownloadedAttachment(
            attachment_id="research-text-integration",
            analysis_attempt_id="research-text-integration-attempt",
            file_type="text",
            filename="notes.txt",
            mime_type="text/plain",
            size_bytes=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
            page_count=None,
            path=source,
            document_version=11,
        )
        label = "integration-research-text"
        sandbox_root = self.root / "sandbox-research-text"
        sandbox = AttachmentParserSandbox(
            temp_root=sandbox_root,
            label_factory=lambda: label,
        )

        parsed = await sandbox.parse(downloaded, profile="research_text_v1")

        canonical_text = "Caf\u00e9\nline"
        canonical = canonical_text.encode("utf-8")
        self.assertIsInstance(parsed, ParsedResearchText)
        self.assertEqual(parsed.document_version, 11)
        self.assertEqual(parsed.text, canonical_text)
        self.assertEqual(parsed.text_sha256, hashlib.sha256(canonical).hexdigest())
        self.assertEqual(parsed.character_count, len(canonical_text))
        self.assertEqual(self._containers_for_label(label), ())
        self.assertEqual(list(sandbox_root.iterdir()), [])

    async def test_research_empty_password_encrypted_pdf_preserves_error_code(self):
        source = self.root / "empty-password-encrypted.pdf"
        document = fitz.open()
        page = document.new_page()
        page.insert_text(
            (72, 72),
            "Research 1234567890 ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        )
        document.save(
            source,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw="",
        )
        document.close()
        os.chmod(source, 0o600)
        payload = source.read_bytes()
        downloaded = DownloadedAttachment(
            attachment_id="research-encrypted-integration",
            analysis_attempt_id="research-encrypted-attempt",
            file_type="pdf",
            filename="encrypted.pdf",
            mime_type="application/pdf",
            size_bytes=len(payload),
            content_sha256=hashlib.sha256(payload).hexdigest(),
            page_count=1,
            path=source,
            document_version=10,
        )
        label = "integration-research-encrypted"
        sandbox_root = self.root / "sandbox-research-encrypted"
        sandbox = AttachmentParserSandbox(
            temp_root=sandbox_root,
            label_factory=lambda: label,
        )

        with self.assertRaises(AttachmentParserError) as raised:
            await sandbox.parse(downloaded, profile="research_pdf_v1")

        self.assertEqual(
            raised.exception.error_code,
            "RESEARCH_PDF_ENCRYPTED",
        )
        self.assertEqual(self._containers_for_label(label), ())
        self.assertEqual(list(sandbox_root.iterdir()), [])

    async def test_timeout_cancel_and_worker_failure_leave_no_containers(self):
        cases = (
            ("timeout", "import time; time.sleep(30)"),
            ("failure", "raise SystemExit(9)"),
        )
        for mode, code in cases:
            with self.subTest(mode=mode):
                label = f"integration-{mode}"
                runner = self._custom_runner(f"runner-{mode}.sh", code)
                sandbox = AttachmentParserSandbox(
                    runner_path=runner,
                    temp_root=self.root / f"sandbox-{mode}",
                    timeout_seconds=0.2 if mode == "timeout" else 5,
                    label_factory=lambda value=label: value,
                )
                with self.assertRaises(AttachmentParserError):
                    await sandbox.parse(self.downloaded)
                self.assertEqual(self._containers_for_label(label), ())

        cancel_label = "integration-cancel"
        cancel_runner = self._custom_runner(
            "runner-cancel.sh", "import time; time.sleep(30)"
        )
        cancel_sandbox = AttachmentParserSandbox(
            runner_path=cancel_runner,
            temp_root=self.root / "sandbox-cancel",
            timeout_seconds=30,
            label_factory=lambda: cancel_label,
        )
        task = asyncio.create_task(cancel_sandbox.parse(self.downloaded))
        await self._wait_for_container(cancel_label)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self._containers_for_label(cancel_label), ())

    def _run_bundle_container(self, bundle, code):
        uid = os.getuid()
        gid = os.getgid()
        bundle.touch(mode=0o600)
        os.chmod(bundle, 0o600)
        return subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--user",
                f"{uid}:{gid}",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--tmpfs",
                (
                    "/output:rw,noexec,nosuid,size=2m,mode=0700,"
                    f"uid={uid},gid={gid}"
                ),
                "-v",
                f"{bundle}:/output.bundle:rw",
                "--entrypoint",
                "python",
                _IMAGE,
                "-c",
                code,
            ],
            check=False,
            capture_output=True,
        )

    def test_untrusted_parser_cannot_open_host_staging_directory(self):
        bundle = self.root / "direct-write.bundle"
        code = (
            "from pathlib import Path\n"
            "try:\n"
            "    Path('/output-staging').mkdir()\n"
            "    Path('/output-staging/escape.bin').write_bytes(b'escape')\n"
            "except OSError:\n"
            "    pass\n"
            "else:\n"
            "    raise SystemExit(9)\n"
            "Path('/output.bundle').write_bytes(b'bounded')\n"
        )

        result = self._run_bundle_container(bundle, code)

        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(bundle.read_bytes(), b"bounded")
        self.assertFalse((self.root / "output-staging").exists())

    def test_cumulative_multi_file_limit_leaves_host_bundle_empty(self):
        bundle = self.root / "cumulative.bundle"
        code = (
            "from pathlib import Path\n"
            "import hashlib\n"
            "import infrastructure.attachments.attachment_parser_worker as worker\n"
            "from infrastructure.attachments.parser_protocol import "
            "AttachmentParserError, WorkerManifest, WorkerPageManifest\n"
            "output = Path('/output')\n"
            "first = output / 'page-0001.jpg'\n"
            "second = output / 'page-0002.jpg'\n"
            "first.write_bytes(b'a' * 6)\n"
            "second.write_bytes(b'b' * 6)\n"
            "first.chmod(0o600)\n"
            "second.chmod(0o600)\n"
            "manifest = WorkerManifest((\n"
            "    WorkerPageManifest(1, first.name, hashlib.sha256(first.read_bytes()).hexdigest()),\n"
            "    WorkerPageManifest(2, second.name, hashlib.sha256(second.read_bytes()).hexdigest()),\n"
            "))\n"
            "worker._MAX_OUTPUT_TOTAL_BYTES = 10\n"
            "try:\n"
            "    worker._write_output_bundle(manifest, output, Path('/output.bundle'))\n"
            "except AttachmentParserError as error:\n"
            "    raise SystemExit(0 if error.error_code == 'ATTACHMENT_OUTPUT_LIMIT' else 8)\n"
            "raise SystemExit(9)\n"
        )

        result = self._run_bundle_container(bundle, code)

        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(bundle.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
