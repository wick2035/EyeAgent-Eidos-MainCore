import asyncio
import json
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from starlette.requests import Request

from application.services.chat_turn_execution_registry import (
    ChatTurnExecutionRegistry,
)
from application.services.chat_turn_fingerprint import fingerprint_turn
from domain.security.principal import CurrentPrincipal
from presentation.routers.platform_chat_turn_router import (
    abort_platform_chat_turn,
    execute_platform_chat_turn,
    get_platform_chat_turn_status,
    prepare_platform_chat_turn,
    router,
)
from presentation.schemas.platform_chat_turn_schemas import (
    AbortPlatformChatTurnRequest,
    AbortPlatformChatTurnResponse,
    ExecutePlatformChatTurnRequest,
    PlatformChatTurnStatusResponse,
    PreparePlatformChatTurnRequest,
    PreparePlatformChatTurnResponse,
)


def principal(doctor_id="doctor-1", scopes=None):
    return CurrentPrincipal(
        issuer="java",
        subject=doctor_id,
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=frozenset(scopes or {"ai:chat"}),
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
        self.access_calls = []
        self.abort_calls = []
        self.prepare_calls = []
        self.entity = SimpleNamespace(
            doctor_id="doctor-1",
            request_id="request-1",
            conversation_id="conversation-1",
            agent_type="health",
        )

    def prepare(self, payload):
        self.prepare_calls.append(payload)
        return PreparePlatformChatTurnResponse(
            request_id=payload.request_id,
            request_fingerprint=payload.request_fingerprint,
            status="prepared",
            attachment_only=payload.attachment_only,
            implicit_prompt_id=payload.implicit_prompt_id,
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
        self.access_calls.append((doctor_id, request_id, conversation_id))
        entity = self._get_turn(doctor_id, request_id)
        if entity is None or (
            conversation_id is not None
            and entity.conversation_id != conversation_id
        ):
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


def research_prepare_request():
    payload = {
        "version": 2,
        "request_id": "request-research",
        "operation": "normal",
        "conversation_id": "conversation-1",
        "session_id": "session-1",
        "patient_id": None,
        "doctor_id": "doctor-1",
        "agent_type": "research",
        "attachment_scope": "research",
        "research_options": {
            "enable_institution_data": True,
            "enable_web_search": False,
            "types": [],
        },
        "message": "研究附件",
        "source_message_id": None,
        "implicit_prompt_id": None,
        "attachment_ids": ["attachment-1"],
    }
    payload["request_fingerprint"] = fingerprint_turn(
        version=payload["version"],
        operation=payload["operation"],
        conversation_id=payload["conversation_id"],
        session_id=payload["session_id"],
        patient_id=payload["patient_id"],
        message=payload["message"],
        source_message_id=payload["source_message_id"],
        implicit_prompt_id=payload["implicit_prompt_id"],
        attachment_ids=payload["attachment_ids"],
        agent_type=payload["agent_type"],
        attachment_scope=payload["attachment_scope"],
        research_options=payload["research_options"],
    )
    return PreparePlatformChatTurnRequest(**payload)


def research_execute_request():
    return ExecutePlatformChatTurnRequest(
        version=2,
        request_id="request-research",
        request_fingerprint="a" * 64,
        conversation_id="conversation-1",
        session_id="session-1",
        patient_id=None,
        doctor_id="doctor-1",
        agent_type="research",
        attachment_scope="research",
        research_options={
            "enable_institution_data": True,
            "enable_web_search": False,
            "types": [],
        },
        user_message_id="user-1",
        assistant_message_id="assistant-1",
        attachments=[
            {
                "attachment_id": "attachment-1",
                "file_type": "image",
                "filename": "research.png",
                "mime_type": "image/png",
                "size_bytes": 1024,
                "page_count": None,
                "content_sha256": "b" * 64,
                "document_version": 1,
                "analysis_attempt_id": "attempt-1",
                "download_url": "https://storage.example/file",
            }
        ],
    )


class PlatformChatTurnRouterContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_prepare_source_mismatch_is_safe_400_without_new_records(self):
        source_id = "PRIVATE_SOURCE_MESSAGE_ID_SENTINEL"
        private_context = "PRIVATE_SOURCE_CONTEXT_SENTINEL"

        class RejectingService(FakeTurnService):
            def __init__(self):
                super().__init__()
                self.turns = ["source-turn"]
                self.messages = ["source-user", "source-assistant"]

            def prepare(self, payload):
                self.prepare_calls.append(payload)
                raise ValueError(f"{private_context}:{source_id}")

        service = RejectingService()
        payload = research_prepare_request().model_copy(
            update={
                "operation": "regenerate",
                "source_message_id": source_id,
            }
        )
        before = (list(service.turns), list(service.messages))

        with self.assertRaises(HTTPException) as caught:
            await prepare_platform_chat_turn(
                payload,
                starlette_request(principal(scopes={"ai:research"})),
                service,
                ChatTurnExecutionRegistry(),
            )

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(
            caught.exception.detail,
            {"error_code": "PLATFORM_TURN_PREPARE_REJECTED"},
        )
        serialized = json.dumps(caught.exception.detail)
        self.assertNotIn(source_id, serialized)
        self.assertNotIn(private_context, serialized)
        self.assertEqual((service.turns, service.messages), before)

    async def test_prepare_and_execute_research_require_ai_research_scope(self):
        service = FakeTurnService()
        with self.assertRaises(HTTPException) as prepare_error:
            await prepare_platform_chat_turn(
                research_prepare_request(),
                starlette_request(principal(scopes={"ai:chat"})),
                service,
                ChatTurnExecutionRegistry(),
            )
        self.assertEqual(prepare_error.exception.status_code, 403)
        self.assertEqual(service.prepare_calls, [])

        with self.assertRaises(HTTPException) as execute_error:
            await execute_platform_chat_turn(
                research_execute_request(),
                starlette_request(principal(scopes={"ai:chat"})),
                SimpleNamespace(),
                ChatTurnExecutionRegistry(),
            )
        self.assertEqual(execute_error.exception.status_code, 403)

        response = await prepare_platform_chat_turn(
            research_prepare_request(),
            starlette_request(principal(scopes={"ai:research"})),
            service,
            ChatTurnExecutionRegistry(),
        )
        self.assertEqual(response.status, "prepared")

    async def test_draining_rejects_prepare_and_execute_but_keeps_control_routes(self):
        service = FakeTurnService()
        registry = ChatTurnExecutionRegistry()
        registry.begin_drain()
        request = starlette_request(principal(scopes={"ai:research"}))

        with self.assertRaises(HTTPException) as prepare_error:
            await prepare_platform_chat_turn(
                research_prepare_request(),
                request,
                service,
                registry,
            )
        self.assertEqual(prepare_error.exception.status_code, 503)
        self.assertEqual(
            prepare_error.exception.detail,
            {"error_code": "SERVICE_DRAINING"},
        )
        self.assertEqual(service.prepare_calls, [])

        with self.assertRaises(HTTPException) as execute_error:
            await execute_platform_chat_turn(
                research_execute_request(),
                request,
                SimpleNamespace(),
                registry,
            )
        self.assertEqual(execute_error.exception.status_code, 503)

        status = await get_platform_chat_turn_status(
            "request-1",
            starlette_request(),
            service,
        )
        aborted = await abort_platform_chat_turn(
            "request-1",
            AbortPlatformChatTurnRequest(
                conversation_id="conversation-1",
                doctor_id="doctor-1",
            ),
            starlette_request(),
            service,
            registry,
        )
        self.assertEqual(status.status, "streaming")
        self.assertEqual(aborted.status, "cancelled")

    async def test_execute_admission_is_held_across_drain(self):
        class ExecutionService:
            async def stream(self, payload, current, cancel_event=None):
                self.cancel_event = cancel_event
                yield {
                    "event": "execution_started",
                    "request_id": payload.request_id,
                }

        service = ExecutionService()
        registry = ChatTurnExecutionRegistry()
        payload = research_execute_request()
        response = await execute_platform_chat_turn(
            payload,
            starlette_request(principal(scopes={"ai:research"})),
            service,
            registry,
        )
        self.assertEqual(registry.active_count(), 1)

        registry.begin_drain()
        self.assertFalse(await registry.wait_until_idle(0))
        chunks = [chunk async for chunk in response.body_iterator]

        self.assertEqual(len(chunks), 1)
        self.assertIsNotNone(service.cancel_event)
        self.assertTrue(await registry.wait_until_idle(0.1))

    async def test_execute_background_releases_unstarted_stream(self):
        class ExecutionService:
            async def stream(self, payload, current, cancel_event=None):
                yield {
                    "event": "execution_started",
                    "request_id": payload.request_id,
                }

        registry = ChatTurnExecutionRegistry()
        response = await execute_platform_chat_turn(
            research_execute_request(),
            starlette_request(principal(scopes={"ai:research"})),
            ExecutionService(),
            registry,
        )
        self.assertEqual(registry.active_count(), 1)
        self.assertIsNotNone(response.background)
        registry.begin_drain()
        idle_waiter = asyncio.create_task(registry.wait_until_idle(0.5))
        await asyncio.sleep(0)

        await response.background()

        self.assertEqual(registry.active_count(), 0)
        self.assertTrue(await idle_waiter)

    async def test_status_research_scope_comes_from_persisted_turn(self):
        service = FakeTurnService()
        service.entity.agent_type = "research"

        with self.assertRaises(HTTPException) as caught:
            await get_platform_chat_turn_status(
                "request-1",
                starlette_request(principal(scopes={"ai:chat"})),
                service,
            )
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(
            service.access_calls,
            [("doctor-1", "request-1", None)],
        )
        self.assertEqual(service.status_calls, [])

        response = await get_platform_chat_turn_status(
            "request-1",
            starlette_request(principal(scopes={"ai:research"})),
            service,
        )
        self.assertEqual(response.status, "streaming")

    async def test_abort_research_scope_is_checked_before_signal(self):
        service = FakeTurnService()
        service.entity.agent_type = "research"
        registry = ChatTurnExecutionRegistry()
        registered = registry.register("doctor-1", "request-1")

        with self.assertRaises(HTTPException) as caught:
            await abort_platform_chat_turn(
                "request-1",
                AbortPlatformChatTurnRequest(
                    conversation_id="conversation-1",
                    doctor_id="doctor-1",
                ),
                starlette_request(principal(scopes={"ai:chat"})),
                service,
                registry,
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertFalse(registered.is_set())
        self.assertEqual(service.abort_calls, [])

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

        self.assertEqual(
            service.access_calls,
            [("doctor-1", "request-1", None)],
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
        self.assertEqual(
            service.access_calls,
            [("doctor-1", "request-1", "conversation-1")],
        )
        self.assertEqual(service.status_calls, [])
        self.assertEqual(service.abort_calls, [])


if __name__ == "__main__":
    unittest.main()
