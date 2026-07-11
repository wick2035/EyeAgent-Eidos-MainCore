import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from starlette.requests import Request

from application.services.chat_turn_execution_registry import (
    ChatTurnExecutionRegistry,
)
from domain.security.principal import CurrentPrincipal
from presentation.routers.platform_chat_turn_router import (
    abort_platform_chat_turn,
    get_platform_chat_turn_status,
    router,
)
from presentation.schemas.platform_chat_turn_schemas import (
    AbortPlatformChatTurnRequest,
    AbortPlatformChatTurnResponse,
    PlatformChatTurnStatusResponse,
)


def principal(doctor_id="doctor-1"):
    return CurrentPrincipal(
        issuer="java",
        subject=doctor_id,
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=frozenset({"ai:chat"}),
        institution_id="inst-1",
        tenant_id="tenant-1",
        authorized_party="eye-agent-platform",
        schema_version=1,
        token_id="jwt-1",
        issued_at=1,
        not_before=1,
        expires_at=9999999999,
    )


def starlette_request(identity=None):
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("test", 443),
        }
    )
    request.state.internal_principal = identity or principal()
    return request


class FakeTurnService:
    def __init__(self):
        self.status_calls = []
        self.abort_calls = []
        self.entity = SimpleNamespace(
            doctor_id="doctor-1",
            request_id="request-1",
            conversation_id="conversation-1",
        )

    def status(self, doctor_id, request_id):
        self.status_calls.append((doctor_id, request_id))
        if doctor_id != self.entity.doctor_id or request_id != self.entity.request_id:
            from application.services.platform_chat_turn_service import ChatTurnNotFoundError

            raise ChatTurnNotFoundError()
        return PlatformChatTurnStatusResponse(
            request_id=request_id,
            status="streaming",
            session_id="session-1",
            user_message_id="user-1",
            assistant_message_id="assistant-1",
            error_code=None,
            updated_at="2026-07-11T10:00:00",
        )

    def _get_turn(self, doctor_id, request_id):
        if doctor_id == self.entity.doctor_id and request_id == self.entity.request_id:
            return self.entity
        return None

    def assert_turn_conversation(self, doctor_id, request_id, conversation_id):
        self.status(doctor_id, request_id)
        entity = self._get_turn(doctor_id, request_id)
        if entity is None or entity.conversation_id != conversation_id:
            from application.services.platform_chat_turn_service import ChatTurnNotFoundError

            raise ChatTurnNotFoundError()
        return entity

    def abort(self, doctor_id, request_id, conversation_id):
        self.abort_calls.append((doctor_id, request_id, conversation_id))
        return AbortPlatformChatTurnResponse(
            request_id=request_id,
            conversation_id=conversation_id,
            status="cancelled",
        )


class PlatformChatTurnRouterContractTest(unittest.IsolatedAsyncioTestCase):
    def test_router_exposes_only_the_four_approved_platform_routes(self):
        routes = {
            (route.path, tuple(sorted(route.methods or ())))
            for route in router.routes
        }
        self.assertEqual(
            routes,
            {
                ("/api/platform/chat/turns/prepare", ("POST",)),
                ("/api/platform/chat/turns/execute", ("POST",)),
                ("/api/platform/chat/turns/{request_id}", ("GET",)),
                ("/api/platform/chat/turns/{request_id}/abort", ("POST",)),
            },
        )

    async def test_status_contains_only_control_plane_fields(self):
        response = await get_platform_chat_turn_status(
            "request-1",
            starlette_request(),
            FakeTurnService(),
        )

        self.assertEqual(
            set(response.model_dump()),
            {
                "request_id",
                "status",
                "session_id",
                "user_message_id",
                "assistant_message_id",
                "error_code",
                "updated_at",
            },
        )

    async def test_status_is_scoped_by_principal_subject_and_request_id(self):
        service = FakeTurnService()

        await get_platform_chat_turn_status(
            "request-1",
            starlette_request(principal("doctor-1")),
            service,
        )

        self.assertEqual(service.status_calls, [("doctor-1", "request-1")])

    async def test_abort_rejects_conversation_mismatch(self):
        service = FakeTurnService()
        registry = ChatTurnExecutionRegistry()

        with self.assertRaises(HTTPException) as caught:
            await abort_platform_chat_turn(
                "request-1",
                AbortPlatformChatTurnRequest(
                    conversation_id="other-conversation",
                    doctor_id="doctor-1",
                ),
                starlette_request(),
                service,
                registry,
            )

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(service.abort_calls, [])
        self.assertFalse(
            registry.register("doctor-1", "request-1").is_set()
        )

    async def test_abort_signal_does_not_cross_doctor_boundary(self):
        service = FakeTurnService()
        registry = ChatTurnExecutionRegistry()
        other_doctor = registry.register("doctor-2", "request-1")
        current_doctor = registry.register("doctor-1", "request-1")

        response = await abort_platform_chat_turn(
            "request-1",
            AbortPlatformChatTurnRequest(
                conversation_id="conversation-1",
                doctor_id="doctor-1",
            ),
            starlette_request(principal("doctor-1")),
            service,
            registry,
        )

        self.assertEqual(response.status, "cancelled")
        self.assertTrue(current_doctor.is_set())
        self.assertFalse(other_doctor.is_set())

    async def test_abort_rejects_other_doctor_request_id(self):
        service = FakeTurnService()
        service.entity.doctor_id = "doctor-2"

        with self.assertRaises(HTTPException) as caught:
            await abort_platform_chat_turn(
                "request-1",
                AbortPlatformChatTurnRequest(
                    conversation_id="conversation-1",
                    doctor_id="doctor-1",
                ),
                starlette_request(principal("doctor-1")),
                service,
                ChatTurnExecutionRegistry(),
            )

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(service.status_calls, [("doctor-1", "request-1")])
        self.assertEqual(service.abort_calls, [])


if __name__ == "__main__":
    unittest.main()
