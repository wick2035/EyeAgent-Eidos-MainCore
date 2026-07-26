#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.parse import urlsplit


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from infrastructure.attachments.config import (  # noqa: E402
    AttachmentConfigurationError,
    AttachmentDownloadSettings,
)
from infrastructure.security.config import (  # noqa: E402
    InternalAuthMode,
    InternalAuthSettings,
)


DEFAULT_RUNNER = REPOSITORY_ROOT / "scripts/run_attachment_parser_sandbox.sh"
DEFAULT_IMAGE = "eyeagent/attachment-parser:research-c3-xlsx"
IMMUTABLE_IMAGE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._/:+-]*@sha256:[0-9a-f]{64}$"
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class DockerImageEvidence:
    server_version: str
    configured_user: str
    repo_digests: tuple[str, ...]


DockerProbe = Callable[[str], DockerImageEvidence]


def _run_docker_command(*arguments: str) -> str:
    completed = subprocess.run(
        ("docker", *arguments),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError("docker command failed")
    output = completed.stdout.strip()
    if not output:
        raise RuntimeError("docker command returned no evidence")
    return output


def inspect_docker_image(image: str) -> DockerImageEvidence:
    if shutil.which("docker") is None:
        raise RuntimeError("docker is unavailable")
    server_version = _run_docker_command("info", "--format", "{{.ServerVersion}}")
    configured_user = _run_docker_command(
        "image",
        "inspect",
        image,
        "--format",
        "{{json .Config.User}}",
    )
    raw_repo_digests = _run_docker_command(
        "image",
        "inspect",
        image,
        "--format",
        "{{json .RepoDigests}}",
    )
    try:
        decoded_user = json.loads(configured_user)
        decoded_digests = json.loads(raw_repo_digests)
    except json.JSONDecodeError as exc:
        raise RuntimeError("docker evidence is invalid") from exc
    if not isinstance(decoded_user, str) or not isinstance(
        decoded_digests,
        list,
    ):
        raise RuntimeError("docker evidence has an unexpected shape")
    repo_digests = tuple(
        digest for digest in decoded_digests if isinstance(digest, str)
    )
    return DockerImageEvidence(
        server_version=server_version,
        configured_user=decoded_user,
        repo_digests=repo_digests,
    )


def _runner_check(runner_path: Path) -> CheckResult:
    usable = (
        runner_path.is_file()
        and not runner_path.is_symlink()
        and os.access(runner_path, os.X_OK)
    )
    return CheckResult(
        name="parser.runner",
        passed=usable,
        detail=(
            "sandbox runner is executable"
            if usable
            else "sandbox runner must be a regular executable file"
        ),
    )


def _parser_config_checks(
    environ: Mapping[str, str],
) -> tuple[CheckResult, CheckResult, str]:
    image = environ.get("PLATFORM_ATTACHMENT_PARSER_IMAGE", DEFAULT_IMAGE)
    immutable = bool(IMMUTABLE_IMAGE_PATTERN.fullmatch(image))
    require_digest = (
        environ.get("PLATFORM_ATTACHMENT_PARSER_REQUIRE_DIGEST") == "true"
    )
    return (
        CheckResult(
            name="parser.immutable_image",
            passed=immutable,
            detail=(
                "parser image uses an immutable sha256 reference"
                if immutable
                else "set an explicit repository@sha256 reference"
            ),
        ),
        CheckResult(
            name="parser.digest_required",
            passed=require_digest,
            detail=(
                "digest enforcement is enabled"
                if require_digest
                else "PLATFORM_ATTACHMENT_PARSER_REQUIRE_DIGEST must equal true"
            ),
        ),
        image,
    )


def _download_config_checks(
    environ: Mapping[str, str],
) -> tuple[CheckResult, CheckResult]:
    try:
        settings = AttachmentDownloadSettings.from_env(environ)
    except AttachmentConfigurationError:
        return (
            CheckResult(
                name="download.allowlist",
                passed=False,
                detail="attachment download allowlist is missing or invalid",
            ),
            CheckResult(
                name="download.https_only",
                passed=False,
                detail="production attachment downloads require HTTPS only",
            ),
        )
    https_only = (
        not settings.allow_http
        and all(endpoint.scheme == "https" for endpoint in settings.endpoints)
    )
    return (
        CheckResult(
            name="download.allowlist",
            passed=True,
            detail=f"{len(settings.endpoints)} exact endpoint(s) configured",
        ),
        CheckResult(
            name="download.https_only",
            passed=https_only,
            detail=(
                "HTTP is disabled and every endpoint uses HTTPS"
                if https_only
                else "production allowlist must contain only HTTPS endpoints"
            ),
        ),
    )


def _internal_auth_checks(
    environ: Mapping[str, str],
) -> tuple[CheckResult, CheckResult]:
    try:
        settings = InternalAuthSettings.from_env(environ)
    except (TypeError, ValueError):
        return (
            CheckResult(
                name="auth.enforce",
                passed=False,
                detail="internal auth configuration is invalid",
            ),
            CheckResult(
                name="auth.jwks_transport",
                passed=False,
                detail="production JWKS transport requires HTTPS",
            ),
        )
    enforce = settings.mode is InternalAuthMode.ENFORCE
    try:
        parsed = urlsplit(settings.jwks_url or "")
        parsed_port = parsed.port
        secure_transport = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.query == ""
            and parsed.fragment == ""
            and (parsed_port is None or 1 <= parsed_port <= 65535)
            and not settings.allow_insecure_non_loopback_http_jwks
        )
    except ValueError:
        secure_transport = False
    return (
        CheckResult(
            name="auth.enforce",
            passed=enforce,
            detail=(
                "internal authentication is enforced"
                if enforce
                else "INTERNAL_AUTH_MODE must equal enforce"
            ),
        ),
        CheckResult(
            name="auth.jwks_transport",
            passed=secure_transport,
            detail=(
                "JWKS uses HTTPS without insecure opt-in"
                if secure_transport
                else "production JWKS URL must use HTTPS"
            ),
        ),
    )


def _docker_checks(
    image: str,
    docker_probe: DockerProbe,
) -> tuple[CheckResult, CheckResult, CheckResult]:
    try:
        evidence = docker_probe(image)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        unavailable = CheckResult(
            name="parser.docker",
            passed=False,
            detail="Docker daemon or configured parser image is unavailable",
        )
        return (
            unavailable,
            CheckResult(
                name="parser.non_root",
                passed=False,
                detail="parser image user could not be verified",
            ),
            CheckResult(
                name="parser.repo_digest",
                passed=False,
                detail="registry RepoDigest could not be verified",
            ),
        )
    configured_user = evidence.configured_user.strip().lower()
    primary_user = configured_user.split(":", 1)[0].strip()
    if primary_user in {"", "root"}:
        non_root = False
    else:
        try:
            non_root = int(primary_user, 10) != 0
        except ValueError:
            non_root = True
    repo_digest_matches = image in evidence.repo_digests
    return (
        CheckResult(
            name="parser.docker",
            passed=bool(evidence.server_version),
            detail="Docker daemon and parser image are available",
        ),
        CheckResult(
            name="parser.non_root",
            passed=non_root,
            detail=(
                "parser image declares a non-root user"
                if non_root
                else "parser image must declare a non-root user"
            ),
        ),
        CheckResult(
            name="parser.repo_digest",
            passed=repo_digest_matches,
            detail=(
                "local image evidence matches the configured registry digest"
                if repo_digest_matches
                else "pull the exact registry digest before release"
            ),
        ),
    )


def collect_config_checks(
    environ: Mapping[str, str],
    *,
    runner_path: Path = DEFAULT_RUNNER,
    docker_probe: DockerProbe = inspect_docker_image,
) -> tuple[CheckResult, ...]:
    image_check, digest_check, image = _parser_config_checks(environ)
    download_checks = _download_config_checks(environ)
    auth_checks = _internal_auth_checks(environ)
    docker_checks = _docker_checks(image, docker_probe)
    return (
        image_check,
        digest_check,
        _runner_check(runner_path),
        *docker_checks,
        *download_checks,
        *auth_checks,
    )


def _render_text(checks: Sequence[CheckResult]) -> str:
    return "\n".join(
        f"{'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}"
        for check in checks
    )


def _render_json(checks: Sequence[CheckResult]) -> str:
    payload = {
        "status": "pass" if all(check.passed for check in checks) else "fail",
        "checks": [asdict(check) for check in checks],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate production attachment release prerequisites.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    config_parser = subparsers.add_parser(
        "config",
        help="validate immutable parser, download, and JWT/JWKS configuration",
    )
    config_parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable evidence",
    )
    args = parser.parse_args(argv)

    checks = collect_config_checks(os.environ)
    print(_render_json(checks) if args.json else _render_text(checks))
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
