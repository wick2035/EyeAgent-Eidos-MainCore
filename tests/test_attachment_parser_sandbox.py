import asyncio
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image

from infrastructure.attachments.parser_protocol import AttachmentParserError
from infrastructure.attachments.parser_sandbox import (
    AttachmentParserSandbox,
    _cleanup_container,
    _read_validated_bundle,
    _run_capture_command,
)
from infrastructure.attachments.secure_downloader import DownloadedAttachment


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_IMAGE = "eyeagent/attachment-parser:1"
_LABEL_KEY = "eyeagent.attachment-parser.run"


def _png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (8, 8), color=(20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


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
            _IMAGE,
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runner)
        self.assertNotIn("output-staging", runner)


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
