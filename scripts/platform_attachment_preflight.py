#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
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
from infrastructure.database.mysql_connection import (  # noqa: E402
    MySQLConnectionPool,
)


DEFAULT_RUNNER = REPOSITORY_ROOT / "scripts/run_attachment_parser_sandbox.sh"
DEFAULT_IMAGE = "eyeagent/attachment-parser:research-c3-xlsx"
IMMUTABLE_IMAGE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._/:+-]*@sha256:[0-9a-f]{64}$"
)
MYSQL_INTEGER_DISPLAY_WIDTH_PATTERN = re.compile(
    r"^(tinyint|smallint|mediumint|int|bigint)\(\d+\)(?=\s|$)"
)
MYSQL_INTEGRATION_TEST_NAME = (
    "tests.test_research_document_repository_mysql_integration"
)
MYSQL_INTEGRATION_TEST_COUNT = 6
MYSQL_REQUIRED_TABLES = (
    "chat_turn_request",
    "research_document_ingestion",
    "research_document_segment",
    "research_dataset",
    "research_dataset_sheet",
    "research_dataset_row_chunk",
)
MYSQL_REQUIRED_COLUMN_DEFINITIONS = (
    ("chat_turn_request", "protocol_version", "tinyint unsigned", "NO", "1"),
    ("chat_turn_request", "agent_type", "varchar(16)", "NO", "health"),
    ("chat_turn_request", "attachment_scope", "varchar(16)", "NO", "patient"),
    ("chat_turn_request", "research_options_json", "json", "YES", None),
    ("chat_turn_request", "ingestion_ids_json", "json", "YES", None),
    ("chat_turn_request", "assistant_message_id", "varchar(36)", "NO", None),
    ("chat_turn_request", "deadline_at", "datetime(6)", "YES", None),
    ("research_dataset", "date_system", "varchar(4)", "YES", None),
    (
        "research_dataset",
        "workbook_sheet_count",
        "smallint unsigned",
        "YES",
        None,
    ),
    (
        "research_dataset",
        "empty_sheet_count",
        "smallint unsigned",
        "YES",
        None,
    ),
    (
        "research_dataset",
        "total_record_count",
        "int unsigned",
        "YES",
        None,
    ),
    (
        "research_dataset",
        "total_formula_cell_count",
        "bigint unsigned",
        "NO",
        "0",
    ),
    (
        "research_dataset",
        "total_merged_range_count",
        "bigint unsigned",
        "NO",
        "0",
    ),
    (
        "research_dataset_sheet",
        "visibility",
        "varchar(16)",
        "NO",
        "visible",
    ),
    (
        "research_dataset_sheet",
        "formula_cell_count",
        "bigint unsigned",
        "NO",
        "0",
    ),
    (
        "research_dataset_sheet",
        "merged_range_count",
        "bigint unsigned",
        "NO",
        "0",
    ),
    (
        "research_dataset_row_chunk",
        "formula_cell_count",
        "bigint unsigned",
        "NO",
        "0",
    ),
)
MYSQL_REQUIRED_INDEX_DEFINITIONS = (
    ("chat_turn_request", "PRIMARY", 0, 1, "doctor_id"),
    ("chat_turn_request", "PRIMARY", 0, 2, "request_id"),
    (
        "chat_turn_request",
        "uk_chat_turn_request_assistant_message",
        0,
        1,
        "assistant_message_id",
    ),
    (
        "chat_turn_request",
        "idx_chat_turn_request_conversation_status",
        1,
        1,
        "conversation_id",
    ),
    (
        "chat_turn_request",
        "idx_chat_turn_request_conversation_status",
        1,
        2,
        "status",
    ),
    (
        "chat_turn_request",
        "idx_chat_turn_request_conversation_status",
        1,
        3,
        "deadline_at",
    ),
)
MYSQL_REQUIRED_CASCADE_DEFINITIONS = (
    (
        "fk_research_document_segment_ingestion",
        1,
        "research_document_segment",
        "ingestion_id",
        "research_document_ingestion",
        "id",
        "CASCADE",
    ),
    (
        "fk_research_dataset_ingestion",
        1,
        "research_dataset",
        "ingestion_id",
        "research_document_ingestion",
        "id",
        "CASCADE",
    ),
    (
        "fk_research_dataset_sheet_dataset",
        1,
        "research_dataset_sheet",
        "dataset_id",
        "research_dataset",
        "id",
        "CASCADE",
    ),
    (
        "fk_research_dataset_row_chunk_sheet",
        1,
        "research_dataset_row_chunk",
        "sheet_id",
        "research_dataset_sheet",
        "id",
        "CASCADE",
    ),
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


@dataclass(frozen=True, slots=True)
class MySQLSchemaEvidence:
    table_engines: tuple[tuple[str, str], ...]
    column_definitions: tuple[
        tuple[str, str, str, str, str | None],
        ...,
    ]
    index_definitions: tuple[tuple[str, str, int, int, str], ...]
    cascade_definitions: tuple[
        tuple[str, int, str, str, str, str, str],
        ...,
    ]
    sheet_name_collation: str | None
    required_dml_present: bool
    least_privilege_exact: bool


@dataclass(frozen=True, slots=True)
class MySQLSuiteEvidence:
    tests_run: int
    skipped: int
    failures: int
    errors: int


DockerProbe = Callable[[str], DockerImageEvidence]
MySQLSchemaProbe = Callable[[], MySQLSchemaEvidence]
MySQLSuiteProbe = Callable[[], MySQLSuiteEvidence]


def _mysql_identifier(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
        return value[1:-1].replace("``", "`")
    return value


def _inspect_mysql_grants(
    grant_rows: Sequence[Mapping[str, object]],
    database_name: str,
) -> tuple[bool, bool]:
    required_privileges = {"SELECT", "INSERT", "UPDATE", "DELETE"}
    coverage = {
        table_name: set()
        for table_name in MYSQL_REQUIRED_TABLES
    }
    least_privilege_exact = bool(grant_rows)

    for row in grant_rows:
        if len(row) != 1:
            least_privilege_exact = False
            continue
        grant = str(next(iter(row.values()))).strip()
        upper_grant = grant.upper()
        match = re.fullmatch(
            r"GRANT\s+(.+?)\s+ON\s+(\S+)\s+TO\s+(.+)",
            grant,
            flags=re.IGNORECASE,
        )
        if match is None or " WITH GRANT OPTION" in upper_grant:
            least_privilege_exact = False
            continue

        privilege_text, scope, _grantee = match.groups()
        privileges = {
            privilege.strip().upper()
            for privilege in privilege_text.split(",")
            if privilege.strip()
        }
        scope_match = re.fullmatch(
            r"(\*|`(?:``|[^`])+`|[A-Za-z0-9_$-]+)"
            r"\."
            r"(\*|`(?:``|[^`])+`|[A-Za-z0-9_$-]+)",
            scope,
        )
        if scope_match is None:
            least_privilege_exact = False
            continue
        schema_scope = _mysql_identifier(scope_match.group(1))
        table_scope = _mysql_identifier(scope_match.group(2))

        if privileges == {"USAGE"} and (schema_scope, table_scope) == ("*", "*"):
            continue
        if (
            not privileges
            or not privileges.issubset(required_privileges)
            or schema_scope != database_name
            or table_scope not in {"*", *MYSQL_REQUIRED_TABLES}
        ):
            least_privilege_exact = False
            continue

        target_tables = (
            MYSQL_REQUIRED_TABLES
            if table_scope == "*"
            else (table_scope,)
        )
        for table_name in target_tables:
            coverage[table_name].update(privileges)

    required_dml_present = all(
        privileges == required_privileges
        for privileges in coverage.values()
    )
    return required_dml_present, (
        least_privilege_exact and required_dml_present
    )


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


def inspect_mysql_schema() -> MySQLSchemaEvidence:
    database = MySQLConnectionPool()
    try:
        database_row = database.fetch_one(
            "SELECT DATABASE() AS database_name"
        )
        if database_row is None or not database_row.get("database_name"):
            raise RuntimeError("MySQL database name is unavailable")
        database_name = str(database_row["database_name"])
        table_rows = database.fetch_all(
            """
                SELECT TABLE_NAME AS table_name, ENGINE AS engine
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name IN (%s, %s, %s, %s, %s, %s)
            """,
            MYSQL_REQUIRED_TABLES,
        )
        column_rows = database.fetch_all(
            """
                SELECT TABLE_NAME AS table_name,
                       COLUMN_NAME AS column_name,
                       COLUMN_TYPE AS column_type,
                       IS_NULLABLE AS is_nullable,
                       COLUMN_DEFAULT AS column_default
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name IN (%s, %s, %s, %s, %s, %s)
            """,
            MYSQL_REQUIRED_TABLES,
        )
        index_rows = database.fetch_all(
            """
                SELECT TABLE_NAME AS table_name,
                       INDEX_NAME AS index_name,
                       NON_UNIQUE AS non_unique,
                       SEQ_IN_INDEX AS seq_in_index,
                       COLUMN_NAME AS column_name
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = 'chat_turn_request'
            """
        )
        cascade_rows = database.fetch_all(
            """
                SELECT rc.CONSTRAINT_NAME AS constraint_name,
                       kcu.ORDINAL_POSITION AS ordinal_position,
                       kcu.TABLE_NAME AS child_table,
                       kcu.COLUMN_NAME AS child_column,
                       kcu.REFERENCED_TABLE_NAME AS parent_table,
                       kcu.REFERENCED_COLUMN_NAME AS parent_column,
                       rc.DELETE_RULE AS delete_rule
                FROM information_schema.referential_constraints rc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
                 AND kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                 AND kcu.TABLE_NAME = rc.TABLE_NAME
                WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
                  AND rc.CONSTRAINT_NAME IN (%s, %s, %s, %s)
            """,
            tuple(
                definition[0]
                for definition in MYSQL_REQUIRED_CASCADE_DEFINITIONS
            ),
        )
        collation_row = database.fetch_one(
            """
                SELECT COLLATION_NAME AS collation_name
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'research_dataset_sheet'
                  AND column_name = 'name'
            """
        )
        grant_rows = database.fetch_all("SHOW GRANTS")
    finally:
        database.close()

    required_dml_present, least_privilege_exact = _inspect_mysql_grants(
        grant_rows,
        database_name,
    )
    return MySQLSchemaEvidence(
        table_engines=tuple(
            sorted(
                (
                    str(row["table_name"]),
                    str(row["engine"] or ""),
                )
                for row in table_rows
            )
        ),
        column_definitions=tuple(
            sorted(
                (
                    str(row["table_name"]),
                    str(row["column_name"]),
                    str(row["column_type"]).lower(),
                    str(row["is_nullable"]).upper(),
                    (
                        None
                        if row["column_default"] is None
                        else str(row["column_default"])
                    ),
                )
                for row in column_rows
            )
        ),
        index_definitions=tuple(
            sorted(
                (
                    str(row["table_name"]),
                    str(row["index_name"]),
                    int(row["non_unique"]),
                    int(row["seq_in_index"]),
                    str(row["column_name"]),
                )
                for row in index_rows
            )
        ),
        cascade_definitions=tuple(
            sorted(
                (
                    str(row["constraint_name"]),
                    int(row["ordinal_position"]),
                    str(row["child_table"]),
                    str(row["child_column"]),
                    str(row["parent_table"]),
                    str(row["parent_column"]),
                    str(row["delete_rule"]).upper(),
                )
                for row in cascade_rows
            )
        ),
        sheet_name_collation=(
            str(collation_row["collation_name"])
            if collation_row is not None
            else None
        ),
        required_dml_present=required_dml_present,
        least_privilege_exact=least_privilege_exact,
    )


def run_mysql_integration_suite() -> MySQLSuiteEvidence:
    suite = unittest.defaultTestLoader.loadTestsFromName(
        MYSQL_INTEGRATION_TEST_NAME
    )
    output = io.StringIO()
    result = unittest.TextTestRunner(
        stream=output,
        verbosity=0,
    ).run(suite)
    return MySQLSuiteEvidence(
        tests_run=result.testsRun,
        skipped=len(result.skipped),
        failures=len(result.failures),
        errors=len(result.errors),
    )


def _normalize_mysql_column_type(column_type: str) -> str:
    normalized = re.sub(r"\s+", " ", column_type.strip().lower())
    return MYSQL_INTEGER_DISPLAY_WIDTH_PATTERN.sub(r"\1", normalized)


def _mysql_schema_checks(
    evidence: MySQLSchemaEvidence,
) -> tuple[CheckResult, ...]:
    table_engines = dict(evidence.table_engines)
    tables_pass = set(table_engines) == set(MYSQL_REQUIRED_TABLES)
    engines_pass = tables_pass and all(
        engine.lower() == "innodb" for engine in table_engines.values()
    )
    normalized_column_definitions = {
        (
            table_name,
            column_name,
            _normalize_mysql_column_type(column_type),
            nullable,
            default,
        )
        for (
            table_name,
            column_name,
            column_type,
            nullable,
            default,
        ) in evidence.column_definitions
    }
    columns_pass = set(MYSQL_REQUIRED_COLUMN_DEFINITIONS).issubset(
        normalized_column_definitions
    )
    required_index_keys = {
        definition[:2]
        for definition in MYSQL_REQUIRED_INDEX_DEFINITIONS
    }
    indexes_pass = all(
        tuple(
            sorted(
                definition
                for definition in evidence.index_definitions
                if definition[:2] == required_key
            )
        )
        == tuple(
            sorted(
                definition
                for definition in MYSQL_REQUIRED_INDEX_DEFINITIONS
                if definition[:2] == required_key
            )
        )
        for required_key in required_index_keys
    )
    required_cascade_names = {
        definition[0]
        for definition in MYSQL_REQUIRED_CASCADE_DEFINITIONS
    }
    cascade_pass = all(
        tuple(
            sorted(
                definition
                for definition in evidence.cascade_definitions
                if definition[0] == required_name
            )
        )
        == tuple(
            sorted(
                definition
                for definition in MYSQL_REQUIRED_CASCADE_DEFINITIONS
                if definition[0] == required_name
            )
        )
        for required_name in required_cascade_names
    )
    collation_pass = evidence.sheet_name_collation == "utf8mb4_bin"
    return (
        CheckResult(
            name="mysql.tables",
            passed=tables_pass,
            detail=(
                "all six platform attachment tables are present"
                if tables_pass
                else "the isolated database must contain all six required tables"
            ),
        ),
        CheckResult(
            name="mysql.engines",
            passed=engines_pass,
            detail=(
                "all required tables use InnoDB"
                if engines_pass
                else "all required tables must use InnoDB"
            ),
        ),
        CheckResult(
            name="mysql.columns",
            passed=columns_pass,
            detail=(
                "chat turn and C3-2 column definitions match"
                if columns_pass
                else "required column types, nullability, or defaults differ"
            ),
        ),
        CheckResult(
            name="mysql.indexes",
            passed=indexes_pass,
            detail=(
                "chat turn index uniqueness and column order match"
                if indexes_pass
                else "chat turn index definitions differ"
            ),
        ),
        CheckResult(
            name="mysql.cascade",
            passed=cascade_pass,
            detail=(
                "all four research foreign keys delete by cascade"
                if cascade_pass
                else "research foreign key or cascade definitions differ"
            ),
        ),
        CheckResult(
            name="mysql.sheet_collation",
            passed=collation_pass,
            detail=(
                "sheet names use utf8mb4_bin"
                if collation_pass
                else "research_dataset_sheet.name must use utf8mb4_bin"
            ),
        ),
        CheckResult(
            name="mysql.required_dml",
            passed=evidence.required_dml_present,
            detail=(
                "application account has required DML privileges"
                if evidence.required_dml_present
                else "application account needs SELECT/INSERT/UPDATE/DELETE"
            ),
        ),
        CheckResult(
            name="mysql.least_privilege",
            passed=evidence.least_privilege_exact,
            detail=(
                "application account has exactly required DML grant types"
                if evidence.least_privilege_exact
                else "reject extra privileges, scopes, roles, or grant option"
            ),
        ),
    )


def _mysql_suite_check(evidence: MySQLSuiteEvidence) -> CheckResult:
    passed = (
        evidence.tests_run == MYSQL_INTEGRATION_TEST_COUNT
        and evidence.skipped == 0
        and evidence.failures == 0
        and evidence.errors == 0
    )
    return CheckResult(
        name="mysql.integration_suite",
        passed=passed,
        detail=(
            f"{evidence.tests_run} real MySQL tests passed with zero skips"
            if passed
            else (
                "real MySQL suite must run exactly "
                f"{MYSQL_INTEGRATION_TEST_COUNT} tests with zero skips, "
                "failures, or errors"
            )
        ),
    )


def collect_mysql_checks(
    environ: Mapping[str, str],
    *,
    schema_probe: MySQLSchemaProbe = inspect_mysql_schema,
    suite_probe: MySQLSuiteProbe = run_mysql_integration_suite,
) -> tuple[CheckResult, ...]:
    enabled = environ.get("RUN_MYSQL_INTEGRATION") == "1"
    disposable = (
        environ.get("PLATFORM_ATTACHMENT_PREFLIGHT_DISPOSABLE_DB") == "true"
    )
    checks = [
        CheckResult(
            name="mysql.integration_enabled",
            passed=enabled,
            detail=(
                "real MySQL integration gate is enabled"
                if enabled
                else "RUN_MYSQL_INTEGRATION must equal 1"
            ),
        ),
        CheckResult(
            name="mysql.disposable_database",
            passed=disposable,
            detail=(
                "operator confirmed an isolated disposable database"
                if disposable
                else (
                    "PLATFORM_ATTACHMENT_PREFLIGHT_DISPOSABLE_DB "
                    "must equal true"
                )
            ),
        ),
    ]
    if not enabled or not disposable:
        return tuple(checks)

    try:
        schema_evidence = schema_probe()
    except Exception:
        checks.append(
            CheckResult(
                name="mysql.schema_probe",
                passed=False,
                detail="isolated MySQL schema could not be verified",
            )
        )
        return tuple(checks)
    schema_checks = _mysql_schema_checks(schema_evidence)
    checks.extend(schema_checks)
    if not all(check.passed for check in schema_checks):
        return tuple(checks)

    try:
        suite_evidence = suite_probe()
    except Exception:
        checks.append(
            CheckResult(
                name="mysql.integration_suite",
                passed=False,
                detail="real MySQL integration suite could not be completed",
            )
        )
        return tuple(checks)
    checks.append(_mysql_suite_check(suite_evidence))
    return tuple(checks)


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
    mysql_parser = subparsers.add_parser(
        "mysql",
        help="validate the isolated schema and run the real MySQL gate",
    )
    mysql_parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable evidence",
    )
    args = parser.parse_args(argv)

    if args.command == "config":
        checks = collect_config_checks(os.environ)
    else:
        checks = collect_mysql_checks(os.environ)
    print(_render_json(checks) if args.json else _render_text(checks))
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
