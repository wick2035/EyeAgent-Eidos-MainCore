import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from scripts.platform_attachment_preflight import (
    DockerImageEvidence,
    MYSQL_REQUIRED_CASCADE_DEFINITIONS,
    MYSQL_REQUIRED_COLUMN_DEFINITIONS,
    MYSQL_REQUIRED_INDEX_DEFINITIONS,
    MYSQL_REQUIRED_TABLES,
    MySQLSchemaEvidence,
    MySQLSuiteEvidence,
    _inspect_mysql_grants,
    collect_config_checks,
    collect_mysql_checks,
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


def passing_mysql_environment() -> dict[str, str]:
    return {
        "RUN_MYSQL_INTEGRATION": "1",
        "PLATFORM_ATTACHMENT_PREFLIGHT_DISPOSABLE_DB": "true",
    }


def passing_mysql_schema() -> MySQLSchemaEvidence:
    return MySQLSchemaEvidence(
        table_engines=tuple(
            (table_name, "InnoDB") for table_name in MYSQL_REQUIRED_TABLES
        ),
        column_definitions=MYSQL_REQUIRED_COLUMN_DEFINITIONS,
        index_definitions=MYSQL_REQUIRED_INDEX_DEFINITIONS,
        cascade_definitions=MYSQL_REQUIRED_CASCADE_DEFINITIONS,
        sheet_name_collation="utf8mb4_bin",
        required_dml_present=True,
        least_privilege_exact=True,
    )


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

    def test_mysql_gate_requires_explicit_real_and_disposable_flags(self):
        probe_called = False

        def schema_probe() -> MySQLSchemaEvidence:
            nonlocal probe_called
            probe_called = True
            return passing_mysql_schema()

        checks = collect_mysql_checks(
            {},
            schema_probe=schema_probe,
            suite_probe=lambda: MySQLSuiteEvidence(6, 0, 0, 0),
        )

        self.assertFalse(probe_called)
        self.assertEqual(
            {check.name for check in checks if not check.passed},
            {
                "mysql.integration_enabled",
                "mysql.disposable_database",
            },
        )

    def test_mysql_gate_passes_complete_schema_and_zero_skip_suite(self):
        checks = collect_mysql_checks(
            passing_mysql_environment(),
            schema_probe=passing_mysql_schema,
            suite_probe=lambda: MySQLSuiteEvidence(6, 0, 0, 0),
        )

        self.assertTrue(all(check.passed for check in checks))

    def test_mysql_gate_rejects_extra_privileges_before_suite(self):
        evidence = passing_mysql_schema()
        unsafe_schema = replace(
            evidence,
            least_privilege_exact=False,
        )
        suite_called = False

        def suite_probe() -> MySQLSuiteEvidence:
            nonlocal suite_called
            suite_called = True
            return MySQLSuiteEvidence(6, 0, 0, 0)

        checks = collect_mysql_checks(
            passing_mysql_environment(),
            schema_probe=lambda: unsafe_schema,
            suite_probe=suite_probe,
        )
        by_name = {check.name: check for check in checks}

        self.assertFalse(by_name["mysql.least_privilege"].passed)
        self.assertFalse(suite_called)

    def test_mysql_gate_checks_exact_schema_definitions(self):
        evidence = passing_mysql_schema()
        mutations = (
            (
                "mysql.columns",
                replace(
                    evidence,
                    column_definitions=tuple(
                        definition
                        for definition in evidence.column_definitions
                        if definition[1] != "protocol_version"
                    )
                    + (
                        (
                            "chat_turn_request",
                            "protocol_version",
                            "tinyint unsigned",
                            "YES",
                            "1",
                        ),
                    ),
                ),
            ),
            (
                "mysql.indexes",
                replace(
                    evidence,
                    index_definitions=tuple(
                        definition
                        for definition in evidence.index_definitions
                        if definition[1]
                        != "uk_chat_turn_request_assistant_message"
                    )
                    + (
                        (
                            "chat_turn_request",
                            "uk_chat_turn_request_assistant_message",
                            1,
                            1,
                            "assistant_message_id",
                        ),
                    ),
                ),
            ),
            (
                "mysql.cascade",
                replace(
                    evidence,
                    cascade_definitions=tuple(
                        definition
                        for definition in evidence.cascade_definitions
                        if definition[0]
                        != "fk_research_dataset_sheet_dataset"
                    )
                    + (
                        (
                            "fk_research_dataset_sheet_dataset",
                            1,
                            "research_dataset_sheet",
                            "dataset_id",
                            "research_dataset",
                            "id",
                            "RESTRICT",
                        ),
                    ),
                ),
            ),
            (
                "mysql.indexes",
                replace(
                    evidence,
                    index_definitions=evidence.index_definitions
                    + (
                        (
                            "chat_turn_request",
                            "PRIMARY",
                            0,
                            3,
                            "request_fingerprint",
                        ),
                    ),
                ),
            ),
            (
                "mysql.cascade",
                replace(
                    evidence,
                    cascade_definitions=evidence.cascade_definitions
                    + (
                        (
                            "fk_research_dataset_sheet_dataset",
                            2,
                            "research_dataset_sheet",
                            "ordinal",
                            "research_dataset",
                            "sheet_count",
                            "CASCADE",
                        ),
                    ),
                ),
            ),
        )

        for check_name, unsafe_schema in mutations:
            with self.subTest(check_name=check_name):
                checks = collect_mysql_checks(
                    passing_mysql_environment(),
                    schema_probe=lambda: unsafe_schema,
                    suite_probe=lambda: MySQLSuiteEvidence(6, 0, 0, 0),
                )
                by_name = {check.name: check for check in checks}

                self.assertFalse(by_name[check_name].passed)

    def test_mysql_grants_require_exact_dml_scope_and_types(self):
        exact_grants = (
            {"grant": "GRANT USAGE ON *.* TO `app`@`%`"},
            {
                "grant": (
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    "ON `eye_agent_gate`.* TO `app`@`%`"
                )
            },
        )
        self.assertEqual(
            _inspect_mysql_grants(exact_grants, "eye_agent_gate"),
            (True, True),
        )

        unsafe_grants = (
            exact_grants
            + ({"grant": "GRANT FILE ON *.* TO `app`@`%`"},),
            exact_grants
            + (
                {
                    "grant": (
                        "GRANT SELECT ON `other_database`.* TO `app`@`%`"
                    )
                },
            ),
            exact_grants
            + (
                {
                    "grant": (
                        "GRANT SELECT ON `eye_agent_gate`.* TO `app`@`%` "
                        "WITH GRANT OPTION"
                    )
                },
            ),
            ({"grant": "GRANT `app_role`@`%` TO `app`@`%`"},),
        )
        for grants in unsafe_grants:
            with self.subTest(grants=grants):
                required_dml, least_privilege = _inspect_mysql_grants(
                    grants,
                    "eye_agent_gate",
                )

                self.assertFalse(least_privilege)
                if len(grants) > 1:
                    self.assertTrue(required_dml)

    def test_mysql_grants_accept_per_table_dml_coverage(self):
        grants = ({"grant": "GRANT USAGE ON *.* TO `app`@`%`"},) + tuple(
            {
                "grant": (
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    f"ON `eye_agent_gate`.`{table_name}` TO `app`@`%`"
                )
            }
            for table_name in MYSQL_REQUIRED_TABLES
        )

        self.assertEqual(
            _inspect_mysql_grants(grants, "eye_agent_gate"),
            (True, True),
        )

    def test_mysql_gate_rejects_skips_or_unexpected_test_count(self):
        for suite_evidence in (
            MySQLSuiteEvidence(6, 1, 0, 0),
            MySQLSuiteEvidence(5, 0, 0, 0),
            MySQLSuiteEvidence(6, 0, 1, 0),
            MySQLSuiteEvidence(6, 0, 0, 1),
        ):
            with self.subTest(suite_evidence=suite_evidence):
                checks = collect_mysql_checks(
                    passing_mysql_environment(),
                    schema_probe=passing_mysql_schema,
                    suite_probe=lambda: suite_evidence,
                )
                by_name = {check.name: check for check in checks}

                self.assertFalse(by_name["mysql.integration_suite"].passed)


if __name__ == "__main__":
    unittest.main()
