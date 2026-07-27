import unittest
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

from fastapi import HTTPException
from starlette.requests import Request

from application.services.chat_persistence_service import (
    ChatPersistenceService,
)
from application.services.platform_conversation_purge_service import (
    PlatformConversationPurgeBusyError,
    PlatformConversationPurgeForbiddenError,
    PlatformConversationPurgeNotFoundError,
    PlatformConversationPurgeResult,
    PlatformConversationPurgeService,
)
from domain.security.principal import CurrentPrincipal
from presentation.routers.platform_conversation_purge_router import (
    purge_platform_conversation,
    router,
)
from presentation.schemas.platform_conversation_purge_schemas import (
    PlatformConversationPurgeRequest,
)


class ScriptedDB:
    def __init__(self, fetch_one_results, execute_results=None):
        self.fetch_one_results = list(fetch_one_results)
        self.execute_results = list(execute_results or [])
        self.operations = []
        self.transaction_events = []
        self.transaction_depth = 0

    @contextmanager
    def transaction(self):
        self.transaction_events.append("begin")
        self.transaction_depth += 1
        try:
            yield
        except Exception:
            self.transaction_events.append("rollback")
            raise
        else:
            self.transaction_events.append("commit")
        finally:
            self.transaction_depth -= 1

    def fetch_one(self, sql, params=None):
        self.operations.append(
            ("fetch_one", sql, params, self.transaction_depth)
        )
        return self._next(self.fetch_one_results, None)

    def execute(self, sql, params=None):
        self.operations.append(
            ("execute", sql, params, self.transaction_depth)
        )
        return self._next(self.execute_results, 1)

    @staticmethod
    def _next(values, default):
        value = values.pop(0) if values else default
        if isinstance(value, BaseException):
            raise value
        return value


def principal(scopes=None):
    return CurrentPrincipal(
        issuer="eye-agent-backend",
        subject="doctor-1",
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=frozenset(scopes or {"conversation:write"}),
        institution_id="institution-1",
        tenant_id="tenant-1",
        authorized_party="eye-agent-java-gateway",
        schema_version=1,
        token_id="token-1",
        issued_at=1,
        not_before=1,
        expires_at=9999999999,
    )


def request(identity=None):
    value = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "DELETE",
            "scheme": "https",
            "path": "/api/platform/conversations/conversation-1/purge",
            "raw_path": (
                b"/api/platform/conversations/conversation-1/purge"
            ),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("test", 443),
        }
    )
    if identity is not None:
        value.state.internal_principal = identity
    return value


class PlatformConversationPurgeServiceTest(unittest.TestCase):
    def test_purge_is_atomic_and_matches_only_base_and_branch_threads(self):
        db = ScriptedDB(
            [
                {
                    "id": "conversation-1",
                    "user_type": "doctor",
                    "host_id": "doctor-1",
                    "deleted": 0,
                },
                None,
                None,
            ]
        )

        result = PlatformConversationPurgeService(db).purge(
            "conversation-1",
            "doctor-1",
        )

        self.assertEqual(
            result,
            PlatformConversationPurgeResult(
                conversation_id="conversation-1",
                already_deleted=False,
            ),
        )
        self.assertEqual(db.transaction_events, ["begin", "commit"])
        self.assertTrue(
            all(operation[3] == 1 for operation in db.operations)
        )

        execute_operations = [
            operation for operation in db.operations if operation[0] == "execute"
        ]
        self.assertEqual(len(execute_operations), 7)
        self.assertIn(
            "DELETE FROM chat_turn_request",
            execute_operations[2][1],
        )
        for _, sql, params, _depth in execute_operations[3:]:
            self.assertIn("thread_id = %s", sql)
            self.assertIn(
                "LEFT(thread_id, CHAR_LENGTH(%s)) = %s",
                sql,
            )
            self.assertNotIn("LIKE", sql.upper())
            self.assertEqual(
                params,
                (
                    "conv_conversation-1",
                    "conv_conversation-1_branch_",
                    "conv_conversation-1_branch_",
                ),
            )

    def test_already_soft_deleted_conversation_remains_retryable(self):
        db = ScriptedDB(
            [
                {
                    "id": "conversation-1",
                    "user_type": "doctor",
                    "host_id": "doctor-1",
                    "deleted": 1,
                },
                None,
                None,
            ]
        )

        result = PlatformConversationPurgeService(db).purge(
            "conversation-1",
            "doctor-1",
        )

        self.assertTrue(result.already_deleted)
        self.assertEqual(db.transaction_events, ["begin", "commit"])

    def test_active_prepared_or_streaming_turn_rolls_back_with_busy(self):
        for active_status in ("prepared", "streaming"):
            with self.subTest(status=active_status):
                db = ScriptedDB(
                    [
                        {
                            "id": "conversation-1",
                            "user_type": "doctor",
                            "host_id": "doctor-1",
                            "deleted": 1,
                        },
                        {"request_id": f"{active_status}-request"},
                    ]
                )

                with self.assertRaises(PlatformConversationPurgeBusyError):
                    PlatformConversationPurgeService(db).purge(
                        "conversation-1",
                        "doctor-1",
                    )

                self.assertEqual(
                    db.transaction_events,
                    ["begin", "rollback"],
                )
                self.assertFalse(
                    any(operation[0] == "execute" for operation in db.operations)
                )

    def test_active_legacy_assistant_rolls_back_with_busy(self):
        db = ScriptedDB(
            [
                {
                    "id": "conversation-1",
                    "user_type": "doctor",
                    "host_id": "doctor-1",
                    "deleted": 0,
                },
                None,
                {"id": "assistant-1"},
            ]
        )

        with self.assertRaises(PlatformConversationPurgeBusyError):
            PlatformConversationPurgeService(db).purge(
                "conversation-1",
                "doctor-1",
            )

        self.assertEqual(db.transaction_events, ["begin", "rollback"])
        active_query = db.operations[2]
        self.assertIn("message_type = 'assistant'", active_query[1])
        self.assertIn("status IN ('running', 'streaming')", active_query[1])
        self.assertNotIn("deleted = 0", active_query[1])
        self.assertFalse(
            any(operation[0] == "execute" for operation in db.operations)
        )

    def test_owner_mismatch_and_missing_conversation_fail_closed(self):
        cases = (
            (
                [
                    {
                        "id": "conversation-1",
                        "user_type": "doctor",
                        "host_id": "doctor-2",
                        "deleted": 1,
                    }
                ],
                PlatformConversationPurgeForbiddenError,
            ),
            ([None], PlatformConversationPurgeNotFoundError),
        )
        for rows, expected_error in cases:
            with self.subTest(error=expected_error.__name__):
                db = ScriptedDB(rows)
                with self.assertRaises(expected_error):
                    PlatformConversationPurgeService(db).purge(
                        "conversation-1",
                        "doctor-1",
                    )
                self.assertEqual(
                    db.transaction_events,
                    ["begin", "rollback"],
                )

    def test_database_failure_rolls_back_whole_purge(self):
        db = ScriptedDB(
            [
                {
                    "id": "conversation-1",
                    "user_type": "doctor",
                    "host_id": "doctor-1",
                    "deleted": 1,
                },
                None,
                None,
            ],
            execute_results=[1, 1, 1, RuntimeError("checkpoint failure")],
        )

        with self.assertRaisesRegex(RuntimeError, "checkpoint failure"):
            PlatformConversationPurgeService(db).purge(
                "conversation-1",
                "doctor-1",
            )

        self.assertEqual(db.transaction_events, ["begin", "rollback"])


class TombstoneConversationRepo:
    def __init__(self):
        self.summary_updates = []

    def update_summary_and_count(self, *args):
        self.summary_updates.append(args)
        return False

    def get_by_id(self, _conversation_id):
        return None

    def get_by_id_including_deleted(self, conversation_id):
        return SimpleNamespace(id=conversation_id, deleted=True)


class TombstoneMessageRepo:
    def __init__(self):
        self.regular_updates = []
        self.maintenance_updates = []

    def update(self, message_id, updates):
        self.regular_updates.append((message_id, updates))
        return False

    def update_including_deleted(self, message_id, updates):
        self.maintenance_updates.append((message_id, updates))
        return True

    def get_by_id(self, _message_id):
        return None

    def get_by_id_including_deleted(self, message_id):
        return SimpleNamespace(
            id=message_id,
            chat_id="conversation-1",
            deleted=True,
        )


class DeletedConversationTurnFinalizationTest(unittest.TestCase):
    def setUp(self):
        self.conversation_repo = TombstoneConversationRepo()
        self.message_repo = TombstoneMessageRepo()
        self.service = ChatPersistenceService(
            conversation_repo=self.conversation_repo,
            message_repo=self.message_repo,
            activity_guard=False,
        )

    def test_platform_turn_can_finalize_deleted_assistant(self):
        success = self.service.finalize_platform_assistant(
            "assistant-1",
            status="success",
            content="ignored after deletion",
        )

        self.assertTrue(success)
        self.assertEqual(len(self.message_repo.regular_updates), 1)
        self.assertEqual(len(self.message_repo.maintenance_updates), 1)
        self.assertEqual(self.conversation_repo.summary_updates, [])

    def test_legacy_stream_can_finalize_deleted_assistant(self):
        success = self.service.update_message(
            "assistant-1",
            content="ignored after deletion",
            status="success",
        )

        self.assertTrue(success)
        self.assertEqual(len(self.message_repo.regular_updates), 1)
        self.assertEqual(len(self.message_repo.maintenance_updates), 1)
        self.assertEqual(self.conversation_repo.summary_updates, [])


class FakePurgeService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def purge(self, conversation_id, doctor_id):
        self.calls.append((conversation_id, doctor_id))
        if self.error is not None:
            raise self.error
        return PlatformConversationPurgeResult(
            conversation_id=conversation_id,
            already_deleted=True,
        )


class PlatformConversationPurgeRouterTest(
    unittest.IsolatedAsyncioTestCase
):
    async def test_route_requires_doctor_conversation_write_scope(self):
        cases = (
            (request(), 401, "PLATFORM_AUTH_REQUIRED"),
            (
                request(
                    replace(
                        principal(),
                        scopes=frozenset({"conversation:read"}),
                    )
                ),
                403,
                "PLATFORM_CONVERSATION_FORBIDDEN",
            ),
            (
                request(
                    replace(
                        principal(),
                        principal_type="patient",
                    )
                ),
                403,
                "PLATFORM_DOCTOR_FORBIDDEN",
            ),
        )
        for http_request, status_code, error_code in cases:
            with self.subTest(status_code=status_code):
                service = FakePurgeService()
                with self.assertRaises(HTTPException) as caught:
                    await purge_platform_conversation(
                        "conversation-1",
                        PlatformConversationPurgeRequest(
                            doctor_id="doctor-1"
                        ),
                        http_request,
                        service,
                    )
                self.assertEqual(caught.exception.status_code, status_code)
                self.assertEqual(
                    caught.exception.detail,
                    {"error_code": error_code},
                )
                self.assertEqual(service.calls, [])

    async def test_route_uses_body_owner_and_returns_204(self):
        service = FakePurgeService()

        response = await purge_platform_conversation(
            "conversation-1",
            PlatformConversationPurgeRequest(doctor_id="doctor-1"),
            request(principal()),
            service,
        )

        self.assertEqual(
            service.calls,
            [("conversation-1", "doctor-1")],
        )
        self.assertEqual(response.status_code, 204)

    async def test_route_rejects_body_subject_mismatch_before_purge(self):
        service = FakePurgeService()

        with self.assertRaises(HTTPException) as caught:
            await purge_platform_conversation(
                "conversation-1",
                PlatformConversationPurgeRequest(doctor_id="doctor-2"),
                request(principal()),
                service,
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(service.calls, [])

    async def test_route_maps_service_errors_to_stable_statuses(self):
        cases = (
            (
                PlatformConversationPurgeNotFoundError(),
                404,
                "PLATFORM_CONVERSATION_NOT_FOUND",
            ),
            (
                PlatformConversationPurgeForbiddenError(),
                403,
                "PLATFORM_CONVERSATION_FORBIDDEN",
            ),
            (
                PlatformConversationPurgeBusyError(),
                409,
                "PLATFORM_CONVERSATION_BUSY",
            ),
        )
        for error, status_code, error_code in cases:
            with self.subTest(status_code=status_code):
                with self.assertRaises(HTTPException) as caught:
                    await purge_platform_conversation(
                        "conversation-1",
                        PlatformConversationPurgeRequest(
                            doctor_id="doctor-1"
                        ),
                        request(principal()),
                        FakePurgeService(error),
                    )
                self.assertEqual(caught.exception.status_code, status_code)
                self.assertEqual(
                    caught.exception.detail,
                    {"error_code": error_code},
                )

    def test_router_exposes_only_internal_purge_contract(self):
        paths = {
            (method, route.path)
            for route in router.routes
            for method in route.methods
        }
        self.assertEqual(
            paths,
            {
                (
                    "DELETE",
                    "/api/platform/conversations/{conversationId}/purge",
                )
            },
        )
