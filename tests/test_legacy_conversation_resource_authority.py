import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import Request

from domain.security.principal import CurrentPrincipal
from presentation.dependencies.security import (
    INTERNAL_AUTH_EFFECTIVE_MODE_SCOPE_KEY,
    LegacyRouteError,
    require_legacy_conversation_resource,
)
from presentation.routers import conversation_router
from presentation.schemas.conversation_schemas import ActiveBranchRequest


def _principal(
    subject: str,
    principal_type: str,
    scopes: set[str],
) -> CurrentPrincipal:
    return CurrentPrincipal(
        issuer="eye-agent-backend",
        subject=subject,
        principal_type=principal_type,
        roles=frozenset({principal_type}),
        scopes=frozenset(scopes),
        institution_id=None,
        tenant_id=None,
        authorized_party="eye-agent-maincore",
        schema_version=1,
        token_id="token-1",
        issued_at=1,
        not_before=1,
        expires_at=2,
    )


def _request(mode="enforce", principal=None):
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/api/conversations/conversation-1",
        "headers": [],
        INTERNAL_AUTH_EFFECTIVE_MODE_SCOPE_KEY: mode,
    })
    request.state.internal_principal = principal
    return request


class LegacyConversationResourceAuthorityTest(unittest.TestCase):
    def test_enforce_rejects_wrong_owner_without_leaking_owner(self):
        conversation = SimpleNamespace(
            id="conversation-1",
            user_type="doctor",
            host_id="doctor-1",
        )

        with self.assertRaisesRegex(
            LegacyRouteError,
            "CONVERSATION_FORBIDDEN",
        ) as raised:
            require_legacy_conversation_resource(
                _request(
                    principal=_principal(
                        "doctor-2",
                        "doctor",
                        {"conversation:read"},
                    )
                ),
                conversation,
                "conversation:read",
            )

        self.assertEqual(raised.exception.status_code, 403)

    def test_off_and_observe_keep_rollout_compatibility(self):
        for mode in ("off", "observe"):
            with self.subTest(mode=mode):
                self.assertIsNone(require_legacy_conversation_resource(
                    _request(mode=mode),
                    SimpleNamespace(
                        user_type="doctor",
                        host_id="doctor-1",
                    ),
                    "conversation:read",
                ))

    def test_enforce_rejects_missing_principal_with_401(self):
        conversation = SimpleNamespace(
            user_type="doctor",
            host_id="doctor-1",
        )

        with self.assertRaisesRegex(
            LegacyRouteError,
            "INTERNAL_AUTH_REQUIRED",
        ) as raised:
            require_legacy_conversation_resource(
                _request(),
                conversation,
                "conversation:read",
            )

        self.assertEqual(raised.exception.status_code, 401)

    def test_enforce_rejects_missing_scope_with_403(self):
        conversation = SimpleNamespace(
            user_type="doctor",
            host_id="doctor-1",
        )

        with self.assertRaises(LegacyRouteError) as raised:
            require_legacy_conversation_resource(
                _request(principal=_principal("doctor-1", "doctor", set())),
                conversation,
                "conversation:read",
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "CONVERSATION_FORBIDDEN")

    def test_enforce_rejects_wrong_principal_type_with_403(self):
        conversation = SimpleNamespace(
            user_type="doctor",
            host_id="doctor-1",
        )

        with self.assertRaises(LegacyRouteError) as raised:
            require_legacy_conversation_resource(
                _request(principal=_principal(
                    "doctor-1",
                    "patient",
                    {"conversation:read"},
                )),
                conversation,
                "conversation:read",
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "CONVERSATION_FORBIDDEN")

    def test_enforce_rejects_unknown_conversation_user_type_with_403(self):
        conversation = SimpleNamespace(
            user_type="admin",
            host_id="doctor-1",
        )

        with self.assertRaises(LegacyRouteError) as raised:
            require_legacy_conversation_resource(
                _request(principal=_principal(
                    "doctor-1",
                    "doctor",
                    {"conversation:read"},
                )),
                conversation,
                "conversation:read",
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "CONVERSATION_FORBIDDEN")

    def test_doctor_conversation_accepts_only_doctor(self):
        conversation = SimpleNamespace(
            user_type="doctor",
            host_id="doctor-1",
        )

        principal = require_legacy_conversation_resource(
            _request(principal=_principal(
                "doctor-1",
                "doctor",
                {"conversation:read"},
            )),
            conversation,
            "conversation:read",
        )

        self.assertEqual(principal.principal_type, "doctor")

    def test_patient_conversation_accepts_patient_and_user(self):
        conversation = SimpleNamespace(
            user_type="patient",
            host_id="patient-1",
        )

        for principal_type in ("patient", "user"):
            with self.subTest(principal_type=principal_type):
                principal = require_legacy_conversation_resource(
                    _request(principal=_principal(
                        "patient-1",
                        principal_type,
                        {"conversation:read"},
                    )),
                    conversation,
                    "conversation:read",
                )
                self.assertEqual(principal.principal_type, principal_type)

    def test_correct_owner_and_scope_returns_principal(self):
        principal = _principal(
            "doctor-1",
            "doctor",
            {"conversation:read", "conversation:write"},
        )

        result = require_legacy_conversation_resource(
            _request(principal=principal),
            SimpleNamespace(user_type="doctor", host_id="doctor-1"),
            "conversation:write",
        )

        self.assertIs(result, principal)


class FakePersistenceService:
    def __init__(self, owner: str) -> None:
        self.conversation = SimpleNamespace(
            id="conversation-1",
            user_type="doctor",
            host_id=owner,
            title="新对话",
            summary=None,
            total_messages=0,
            create_time=datetime(2026, 1, 1),
            update_time=datetime(2026, 1, 1),
            active_node_id="message-2",
        )
        self.load_calls = []
        self.switch_calls = []

    def get_conversation(self, conversation_id: str):
        if conversation_id != self.conversation.id:
            return None
        return self.conversation

    def load_active_path(self, conversation_id: str):
        self.load_calls.append(conversation_id)
        return self.conversation, [], {}

    def switch_active_branch(
        self,
        conversation_id: str,
        through_message_id: str,
    ) -> bool:
        self.switch_calls.append((conversation_id, through_message_id))
        return True


class LegacyConversationRouteAuthorityTest(unittest.IsolatedAsyncioTestCase):
    async def test_active_branch_denial_happens_before_write(self):
        service = FakePersistenceService(owner="doctor-1")
        with patch.object(
            conversation_router,
            "get_chat_persistence_service",
            return_value=service,
        ):
            with self.assertRaises(LegacyRouteError):
                await conversation_router.switch_active_branch(
                    "conversation-1",
                    ActiveBranchRequest(through_message_id="message-2"),
                    _request(principal=_principal(
                        "doctor-2",
                        "doctor",
                        {"conversation:write"},
                    )),
                )

        self.assertEqual(service.switch_calls, [])

    async def test_conversation_detail_rejects_wrong_owner(self):
        service = FakePersistenceService(owner="doctor-1")
        with patch.object(
            conversation_router,
            "get_chat_persistence_service",
            return_value=service,
        ):
            with self.assertRaisesRegex(
                LegacyRouteError,
                "CONVERSATION_FORBIDDEN",
            ):
                await conversation_router.get_conversation_detail(
                    "conversation-1",
                    _request(principal=_principal(
                        "doctor-2",
                        "doctor",
                        {"conversation:read"},
                    )),
                )

        self.assertEqual(service.load_calls, [])

    async def test_conversation_detail_accepts_correct_owner(self):
        service = FakePersistenceService(owner="doctor-1")
        with patch.object(
            conversation_router,
            "get_chat_persistence_service",
            return_value=service,
        ):
            response = await conversation_router.get_conversation_detail(
                "conversation-1",
                _request(principal=_principal(
                    "doctor-1",
                    "doctor",
                    {"conversation:read"},
                )),
            )

        self.assertEqual(response.id, "conversation-1")
        self.assertEqual(service.load_calls, ["conversation-1"])


if __name__ == "__main__":
    unittest.main()
