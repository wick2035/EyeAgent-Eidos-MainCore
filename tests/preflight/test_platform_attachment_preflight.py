import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.platform_attachment_preflight import (
    DockerImageEvidence,
    collect_config_checks,
)


IMMUTABLE_IMAGE = (
    "registry.example.com/eyeagent/attachment-parser@sha256:"
    + "a" * 64
)


def passing_environment() -> dict[str, str]:
    return {
        "PLATFORM_ATTACHMENT_PARSER_IMAGE": IMMUTABLE_IMAGE,
        "PLATFORM_ATTACHMENT_PARSER_REQUIRE_DIGEST": "true",
        "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
            [["https", "backend.example", 443, "192.0.2.10"]]
        ),
        "PLATFORM_ATTACHMENT_ALLOW_HTTP": "false",
        "INTERNAL_AUTH_MODE": "enforce",
        "INTERNAL_JWT_JWKS_URL": (
            "https://backend.example/.well-known/eye-agent-internal-jwks.json"
        ),
        "INTERNAL_JWT_ALLOW_INSECURE_NON_LOOPBACK_HTTP": "false",
    }


class PlatformAttachmentPreflightTest(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.runner = Path(self.temp_directory.name) / "runner.sh"
        self.runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(self.runner, 0o700)

    def tearDown(self):
        self.temp_directory.cleanup()

    @staticmethod
    def passing_probe(image: str) -> DockerImageEvidence:
        return DockerImageEvidence(
            server_version="28.0.0",
            configured_user="65532:65532",
            repo_digests=(image,),
        )

    def test_production_configuration_passes_with_registry_evidence(self):
        checks = collect_config_checks(
            passing_environment(),
            runner_path=self.runner,
            docker_probe=self.passing_probe,
        )

        self.assertTrue(all(check.passed for check in checks))

    def test_mutable_parser_http_download_and_auth_off_fail_closed(self):
        environment = passing_environment()
        environment.update(
            {
                "PLATFORM_ATTACHMENT_PARSER_IMAGE": (
                    "eyeagent/attachment-parser:research-c3-xlsx"
                ),
                "PLATFORM_ATTACHMENT_PARSER_REQUIRE_DIGEST": "false",
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON": json.dumps(
                    [["http", "127.0.0.1", 8081, "127.0.0.1"]]
                ),
                "PLATFORM_ATTACHMENT_ALLOW_HTTP": "true",
                "INTERNAL_AUTH_MODE": "off",
                "INTERNAL_JWT_JWKS_URL": "http://127.0.0.1:8081/jwks",
            }
        )

        checks = collect_config_checks(
            environment,
            runner_path=self.runner,
            docker_probe=self.passing_probe,
        )
        failures = {check.name for check in checks if not check.passed}

        self.assertIn("parser.immutable_image", failures)
        self.assertIn("parser.digest_required", failures)
        self.assertIn("download.https_only", failures)
        self.assertIn("auth.enforce", failures)
        self.assertIn("auth.jwks_transport", failures)

    def test_repo_digest_must_match_the_configured_image(self):
        def mismatched_probe(_image: str) -> DockerImageEvidence:
            return DockerImageEvidence(
                server_version="28.0.0",
                configured_user="65532",
                repo_digests=(
                    "registry.example.com/eyeagent/attachment-parser@sha256:"
                    + "b" * 64,
                ),
            )

        checks = collect_config_checks(
            passing_environment(),
            runner_path=self.runner,
            docker_probe=mismatched_probe,
        )
        by_name = {check.name: check for check in checks}

        self.assertFalse(by_name["parser.repo_digest"].passed)

    def test_root_image_user_with_group_fails_closed(self):
        for configured_user in ("0:65532", "0000:65532", "root:65532"):
            with self.subTest(configured_user=configured_user):
                checks = collect_config_checks(
                    passing_environment(),
                    runner_path=self.runner,
                    docker_probe=lambda image: DockerImageEvidence(
                        server_version="28.0.0",
                        configured_user=configured_user,
                        repo_digests=(image,),
                    ),
                )
                by_name = {check.name: check for check in checks}

                self.assertFalse(by_name["parser.non_root"].passed)

    def test_invalid_or_credentialed_jwks_url_fails_closed(self):
        invalid_urls = (
            "https://user:secret@backend.example/jwks",
            "https://backend.example:bad/jwks",
            "https://[invalid/jwks",
            "https://backend.example/jwks?token=secret",
        )
        for jwks_url in invalid_urls:
            with self.subTest(jwks_url=jwks_url):
                environment = passing_environment()
                environment["INTERNAL_JWT_JWKS_URL"] = jwks_url

                checks = collect_config_checks(
                    environment,
                    runner_path=self.runner,
                    docker_probe=self.passing_probe,
                )
                by_name = {check.name: check for check in checks}

                self.assertFalse(by_name["auth.jwks_transport"].passed)


if __name__ == "__main__":
    unittest.main()
