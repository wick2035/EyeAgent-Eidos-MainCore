import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from domain.security.principal import CurrentPrincipal
from application.services.legacy_text_turn_authority import (
    build_legacy_text_turn_authority,
)
from presentation.dependencies.security import LegacyRouteError
from presentation.routers import chat_router, research_router
from presentation.schemas.chat_schemas import (
    ChatRequest,
    EditResendRequest,
    RegenerateRequest,
)
from presentation.schemas.research_schemas import ResearchChatRequest


DOCTOR_ID = "660e8400-e29b-41d4-a716-446655440001"
PATIENT_ID = "550e8400-e29b-41d4-a716-446655440000"


def principal(*, subject=DOCTOR_ID, scopes=frozenset({"ai:research"})):
    return CurrentPrincipal(
        issuer="java",
        subject=subject,
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=frozenset(scopes),
        institution_id="institution-1",
        tenant_id="tenant-1",
        authorized_party="eye-agent-platform",
        schema_version=1,
        token_id="token-1",
        issued_at=1,
        not_before=1,
        expires_at=9_999_999_999,
    )


def starlette_request(identity):
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
    )
    request.state.internal_principal = identity
    return request


class LegacyResearchSchemaBoundaryTest(unittest.TestCase):
    def test_research_requests_require_no_patient(self):
        edit = EditResendRequest(
            message="科研问题",
            patient_id=None,
            doctor_id=DOCTOR_ID,
            agent_type="research",
            role="doctor",
            conversation_id="conversation-1",
            source_message_id="user-1",
        )
        regenerate = RegenerateRequest(
            patient_id=None,
            doctor_id=DOCTOR_ID,
            agent_type="research",
            role="doctor",
            conversation_id="conversation-1",
            source_message_id="assistant-1",
        )
        research = ResearchChatRequest(
            message="科研问题",
            patient_id=None,
            doctor_id=DOCTOR_ID,
            conversation_id="conversation-1",
        )

        self.assertIsNone(edit.patient_id)
        self.assertIsNone(regenerate.patient_id)
        self.assertIsNone(research.patient_id)

    def test_research_requests_reject_doctor_as_patient(self):
        payloads = (
            (
                EditResendRequest,
                {
                    "message": "科研问题",
                    "patient_id": DOCTOR_ID,
                    "doctor_id": DOCTOR_ID,
                    "agent_type": "research",
                    "role": "doctor",
                    "conversation_id": "conversation-1",
                    "source_message_id": "user-1",
                },
            ),
            (
                RegenerateRequest,
                {
                    "patient_id": DOCTOR_ID,
                    "doctor_id": DOCTOR_ID,
                    "agent_type": "research",
                    "role": "doctor",
                    "conversation_id": "conversation-1",
                    "source_message_id": "assistant-1",
                },
            ),
            (
                ResearchChatRequest,
                {
                    "message": "科研问题",
                    "patient_id": DOCTOR_ID,
                    "doctor_id": DOCTOR_ID,
                    "conversation_id": "conversation-1",
                },
            ),
        )

        for schema, payload in payloads:
            with self.subTest(schema=schema.__name__):
                with self.assertRaises(ValidationError):
                    schema(**payload)

    def test_health_branch_requests_still_require_patient(self):
        with self.assertRaises(ValidationError):
            EditResendRequest(
                message="健康问题",
                patient_id=None,
                doctor_id=DOCTOR_ID,
                agent_type="health",
                role="doctor",
                conversation_id="conversation-1",
                source_message_id="user-1",
            )

    def test_research_options_require_exact_canonical_web_contract(self):
        invalid_options = (
            (True, []),
            (False, ["general"]),
            (True, ["pubmed", "general"]),
            (True, ["general", "general"]),
        )

        for enable_web_search, web_search_types in invalid_options:
            with self.subTest(
                enable_web_search=enable_web_search,
                web_search_types=web_search_types,
            ):
                with self.assertRaises(ValidationError):
                    ResearchChatRequest(
                        message="科研问题",
                        doctor_id=DOCTOR_ID,
                        enable_web_search=enable_web_search,
                        web_search_types=web_search_types,
                    )


class LegacyResearchRouteSecurityTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _edit_request():
        return EditResendRequest(
            message="科研问题",
            patient_id=None,
            doctor_id=DOCTOR_ID,
            agent_type="research",
            role="doctor",
            conversation_id="conversation-1",
            source_message_id="user-1",
        )

    @staticmethod
    def _regenerate_request():
        return RegenerateRequest(
            patient_id=None,
            doctor_id=DOCTOR_ID,
            agent_type="research",
            role="doctor",
            conversation_id="conversation-1",
            source_message_id="assistant-1",
        )

    async def test_branch_routes_require_matching_subject_and_research_scope(self):
        cases = (
            (chat_router.chat_edit_resend_stream, self._edit_request()),
            (chat_router.chat_regenerate_stream, self._regenerate_request()),
        )
        for route, body in cases:
            with self.subTest(route=route.__name__):
                with self.assertRaises(LegacyRouteError) as missing_scope:
                    await route(
                        body,
                        starlette_request(principal(scopes={"ai:chat"})),
                    )
                self.assertEqual(missing_scope.exception.status_code, 403)

                with self.assertRaises(LegacyRouteError) as wrong_subject:
                    await route(
                        body,
                        starlette_request(principal(subject=PATIENT_ID)),
                    )
                self.assertEqual(wrong_subject.exception.status_code, 403)

    async def test_branch_routes_accept_matching_research_principal(self):
        sentinel = object()
        authority = build_legacy_text_turn_authority(
            agent_type="research",
            patient_id=None,
            enable_institution_data=True,
            enable_web_search=True,
            web_search_types=["general", "pubmed"],
        )
        cases = (
            (chat_router.chat_edit_resend_stream, self._edit_request()),
            (chat_router.chat_regenerate_stream, self._regenerate_request()),
        )
        with patch.object(
            chat_router,
            "_streaming_response_for_request",
            return_value=sentinel,
        ) as streaming, patch.object(
            chat_router,
            "_assert_legacy_branch_authority",
            return_value=authority,
        ):
            for route, body in cases:
                with self.subTest(route=route.__name__):
                    result = await route(
                        body,
                        starlette_request(principal()),
                    )
                    self.assertIs(result, sentinel)
        self.assertEqual(streaming.call_count, 2)
        for call in streaming.call_args_list:
            self.assertIs(
                call.kwargs["legacy_text_turn_authority"],
                authority,
            )

    async def test_health_edit_route_keeps_patient_and_ai_chat_scope(self):
        body = EditResendRequest(
            message="健康问题",
            patient_id=PATIENT_ID,
            doctor_id=DOCTOR_ID,
            agent_type="health",
            role="doctor",
            conversation_id="conversation-1",
            source_message_id="user-1",
        )
        sentinel = object()
        authority = build_legacy_text_turn_authority(
            agent_type="health",
            patient_id=PATIENT_ID,
        )
        with patch.object(
            chat_router,
            "_streaming_response_for_request",
            return_value=sentinel,
        ), patch.object(
            chat_router,
            "_assert_legacy_branch_authority",
            return_value=authority,
        ):
            result = await chat_router.chat_edit_resend_stream(
                body,
                starlette_request(principal(scopes={"ai:chat"})),
            )

        self.assertIs(result, sentinel)
        self.assertEqual(body.patient_id, PATIENT_ID)

    async def test_research_stream_requires_matching_research_scope(self):
        body = ResearchChatRequest(
            message="科研问题",
            patient_id=None,
            doctor_id=DOCTOR_ID,
            conversation_id="conversation-1",
        )
        with self.assertRaises(LegacyRouteError) as raised:
            await research_router.research_chat_stream(
                body,
                starlette_request(principal(scopes={"ai:chat"})),
            )

        self.assertEqual(raised.exception.status_code, 403)

    async def test_generic_chat_routes_reject_research_agent(self):
        body = ChatRequest(
            message="科研问题",
            patient_id=None,
            doctor_id=DOCTOR_ID,
            agent_type="research",
            role="doctor",
            conversation_id="conversation-1",
        )

        for route in (chat_router.chat, chat_router.chat_stream):
            with self.subTest(route=route.__name__):
                with self.assertRaises(HTTPException) as raised:
                    await route(body)
                self.assertEqual(raised.exception.status_code, 403)
                self.assertEqual(
                    raised.exception.detail,
                    {"error_code": "PLATFORM_RESEARCH_ROUTE_REQUIRED"},
                )

    async def test_non_stream_research_route_requires_scope_and_keeps_null_patient(self):
        body = ResearchChatRequest(
            message="科研问题",
            patient_id=None,
            doctor_id=DOCTOR_ID,
            session_id="session-1",
            conversation_id="conversation-1",
        )
        with self.assertRaises(LegacyRouteError) as raised:
            await research_router.research_chat(
                body,
                starlette_request(principal(scopes={"ai:chat"})),
            )
        self.assertEqual(raised.exception.status_code, 403)

        captured = {}

        def chat(**kwargs):
            captured.update(kwargs)
            return {
                "response": "完成",
                "is_completed": True,
                "stage": "research",
                "thread_id": "thread-1",
                "citations": [],
            }

        with (
            patch.object(
                research_router,
                "graph_manager",
                SimpleNamespace(chat=chat),
            ),
            patch.object(
                research_router,
                "_assert_research_conversation_owner",
                return_value=None,
            ),
            patch.object(research_router, "verify_doctor_role", return_value=True),
            patch.object(
                research_router,
                "get_chat_persistence_service",
                return_value=SimpleNamespace(),
            ),
        ):
            result = await research_router.research_chat(
                body,
                starlette_request(principal()),
            )

        self.assertEqual(result.response, "完成")
        self.assertIsNone(captured["patient_id"])
        self.assertEqual(captured["doctor_id"], DOCTOR_ID)

    async def test_research_stream_passes_null_patient_to_graph(self):
        body = ResearchChatRequest(
            message="科研问题",
            patient_id=None,
            doctor_id=DOCTOR_ID,
            session_id="session-1",
            conversation_id="conversation-1",
        )

        class CapturingGraph:
            def __init__(self):
                self.kwargs = None

            async def chat_stream_async(self, **kwargs):
                self.kwargs = kwargs
                yield {
                    "type": "done",
                    "content": "完成",
                    "metadata": {"stage": "research"},
                }

        graph = CapturingGraph()
        with (
            patch.object(research_router, "graph_manager", graph),
            patch.object(
                research_router,
                "_assert_research_conversation_owner",
                return_value=None,
            ),
            patch.object(research_router, "verify_doctor_role", return_value=True),
            patch.object(
                research_router,
                "get_chat_persistence_service",
                return_value=SimpleNamespace(),
            ),
            patch(
                "agents.graph.id_mapping.get_thread_config",
                return_value={"configurable": {"thread_id": "thread-1"}},
            ),
        ):
            response = await research_router.research_chat_stream(
                body,
                starlette_request(principal()),
            )
            async for _chunk in response.body_iterator:
                pass

        self.assertIsNotNone(graph.kwargs)
        self.assertIsNone(graph.kwargs["patient_id"])
        self.assertEqual(graph.kwargs["doctor_id"], DOCTOR_ID)
