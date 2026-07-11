import json
import logging
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from application.services.chat_persistence_service import ChatPersistenceService
from domain.models.chat_entity import (
    ChatConversationEntity,
    ChatMessageEntity,
    MessageContext,
)
from domain.security.principal import CurrentPrincipal
from infrastructure.security.config import InternalAuthMode, InternalAuthSettings
from infrastructure.security.errors import TokenValidationError
from presentation.middleware.internal_jwt_auth import install_internal_auth
from presentation.routers import chat_router, research_router
from presentation.schemas.research_schemas import ResearchChatRequest


DOCTOR_ID = "660e8400-e29b-41d4-a716-446655440001"
OTHER_DOCTOR_ID = "770e8400-e29b-41d4-a716-446655440002"
PATIENT_ID = "550e8400-e29b-41d4-a716-446655440000"
SENTINEL = "PRIVATE_PROVIDER_SENTINEL_7F0A"
JWKS_URL = "https://backend.example/internal/auth/jwks"


def _principal(*, scopes=frozenset({"ai:research"})) -> CurrentPrincipal:
    return CurrentPrincipal(
        issuer="eye-agent-backend",
        subject=DOCTOR_ID,
        principal_type="doctor",
        roles=frozenset({"doctor"}),
        scopes=frozenset(scopes),
        institution_id="institution-1",
        tenant_id="tenant-1",
        authorized_party="eye-agent-java-gateway",
        schema_version=1,
        token_id="token-1",
        issued_at=1,
        not_before=1,
        expires_at=9_999_999_999,
    )


class _TokenVerifier:
    async def verify(self, token: str) -> CurrentPrincipal:
        if token == "invalid-token":
            raise TokenValidationError("invalid token")
        if token == "wrong-scope-token":
            return _principal(scopes={"ai:chat"})
        if token == "valid-token":
            return _principal()
        raise AssertionError("unexpected test token")


class _ConversationRepo:
    def __init__(self, conversation: ChatConversationEntity) -> None:
        self.conversation = conversation
        self.write_count = 0

    def get_by_id(self, conversation_id: str):
        if conversation_id == self.conversation.id:
            return self.conversation
        return None

    def lock_by_id(self, conversation_id: str):
        return self.get_by_id(conversation_id)


class _MessageRepo:
    def __init__(self, messages: list[ChatMessageEntity]) -> None:
        self.messages = {message.id: message for message in messages}
        self.write_count = 0

    def get_by_id(self, message_id: str):
        return self.messages.get(message_id)


def _source_context(
    *,
    agent_type: str = "research",
    patient_id=None,
) -> str:
    return MessageContext(
        metadata={
            "agent_type": agent_type,
            "patient_id": patient_id,
        }
    ).to_json()


def _persistence(
    *,
    owner: str = DOCTOR_ID,
    user_context: str | None = None,
    assistant_parent_id: str | None = "user-1",
) -> tuple[ChatPersistenceService, _ConversationRepo, _MessageRepo]:
    conversation_repo = _ConversationRepo(
        ChatConversationEntity(
            id="conversation-1",
            user_type="doctor",
            host_id=owner,
            title="科研对话",
            active_node_id="assistant-1",
        )
    )
    message_repo = _MessageRepo(
        [
            ChatMessageEntity(
                id="root-1",
                chat_id="conversation-1",
                parent_id=None,
                message_order=0,
                message_content="",
                message_type="root",
                sender_id=None,
                status="success",
            ),
            ChatMessageEntity(
                id="user-1",
                chat_id="conversation-1",
                parent_id="root-1",
                message_order=1,
                message_content="原始科研问题",
                message_type="user",
                sender_id=DOCTOR_ID,
                context=(
                    _source_context()
                    if user_context is None
                    else user_context
                ),
            ),
            ChatMessageEntity(
                id="assistant-1",
                chat_id="conversation-1",
                parent_id=assistant_parent_id,
                message_order=2,
                message_content="原始科研回答",
                message_type="assistant",
            ),
        ]
    )
    service = ChatPersistenceService(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        activity_guard=None,
    )
    return service, conversation_repo, message_repo


class _SuccessfulGraph:
    def __init__(self) -> None:
        self.chat_calls = 0
        self.stream_calls = 0
        self.checkpointer = SimpleNamespace(
            get_current_agent=lambda _thread_id: None,
        )

    def chat(self, **_kwargs):
        self.chat_calls += 1
        return {
            "response": "科研回答",
            "is_completed": True,
            "stage": "research",
            "agent_type": "research",
            "thread_id": "thread-1",
            "citations": [],
        }

    async def chat_stream_async(self, **_kwargs):
        self.stream_calls += 1
        yield {
            "type": "done",
            "content": "科研回答",
            "metadata": {"stage": "research", "agent_type": "research"},
        }


class _ExplodingGraph(_SuccessfulGraph):
    def chat(self, **_kwargs):
        self.chat_calls += 1
        raise RuntimeError(SENTINEL)

    async def chat_stream_async(self, **_kwargs):
        self.stream_calls += 1
        raise RuntimeError(SENTINEL)
        yield


class _FailedResultGraph(_SuccessfulGraph):
    def chat(self, **_kwargs):
        self.chat_calls += 1
        return {
            "response": "内部失败",
            "is_completed": False,
            "stage": "error",
            "agent_type": "research",
            "thread_id": "thread-1",
            "citations": [],
            "error_code": "CHAT_EXECUTION_FAILED",
        }


class _RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _settings(mode: InternalAuthMode) -> InternalAuthSettings:
    return InternalAuthSettings(
        mode=mode,
        jwks_url=None if mode is InternalAuthMode.OFF else JWKS_URL,
    )


def _app(mode: InternalAuthMode) -> FastAPI:
    app = FastAPI()
    install_internal_auth(
        app,
        settings=_settings(mode),
        verifier_factory=lambda _settings: _TokenVerifier(),
    )
    app.include_router(chat_router.router)
    app.include_router(research_router.router)
    return app


def _payload(route: str) -> dict:
    base = {
        "patient_id": None,
        "doctor_id": DOCTOR_ID,
        "agent_type": "research",
        "role": "doctor",
        "session_id": "session-1",
        "conversation_id": "conversation-1",
    }
    if route in {"/api/research/chat", "/api/research/chat/stream"}:
        return {**base, "message": "科研问题"}
    if route == "/api/chat/edit-resend/stream":
        return {
            **base,
            "message": "编辑后的科研问题",
            "source_message_id": "user-1",
        }
    if route == "/api/chat/regenerate/stream":
        return {**base, "source_message_id": "assistant-1"}
    raise AssertionError("unknown route")


async def _post(
    app: FastAPI,
    route: str,
    *,
    service: ChatPersistenceService,
    graph,
    token: str | None,
) -> httpx.Response:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(chat_router, "graph_manager", graph)
        )
        stack.enter_context(
            patch.object(research_router, "graph_manager", graph)
        )
        stack.enter_context(
            patch.object(
                chat_router,
                "get_chat_persistence_service",
                return_value=service,
            )
        )
        stack.enter_context(
            patch.object(
                research_router,
                "get_chat_persistence_service",
                return_value=service,
            )
        )
        stack.enter_context(
            patch.object(
                research_router,
                "verify_doctor_role",
                return_value=True,
            )
        )
        stack.enter_context(
            patch(
                "agents.graph.id_mapping.get_thread_config",
                return_value={"configurable": {"thread_id": "thread-1"}},
            )
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                route,
                json=_payload(route),
                headers=headers,
            )


class LegacyResearchAuthModeMatrixTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_asgi_routes_preserve_rollout_and_stable_enforce_codes(self):
        routes = (
            "/api/research/chat",
            "/api/chat/edit-resend/stream",
            "/api/chat/regenerate/stream",
        )
        token_cases = (
            ("missing", None),
            ("invalid", "invalid-token"),
            ("wrong_scope", "wrong-scope-token"),
            ("valid", "valid-token"),
        )

        for mode in InternalAuthMode:
            for outcome, token in token_cases:
                for route in routes:
                    with self.subTest(mode=mode, outcome=outcome, route=route):
                        service, _, _ = _persistence()
                        graph = _SuccessfulGraph()
                        response = await _post(
                            _app(mode),
                            route,
                            service=service,
                            graph=graph,
                            token=token,
                        )

                        if mode is not InternalAuthMode.ENFORCE or outcome == "valid":
                            self.assertEqual(response.status_code, 200)
                            continue
                        if outcome == "missing":
                            self.assertEqual(response.status_code, 401)
                            self.assertEqual(
                                response.json(),
                                {"code": "INTERNAL_AUTH_REQUIRED"},
                            )
                        elif outcome == "invalid":
                            self.assertEqual(response.status_code, 401)
                            self.assertEqual(
                                response.json(),
                                {"code": "INTERNAL_AUTH_INVALID"},
                            )
                        else:
                            self.assertEqual(response.status_code, 403)
                            self.assertEqual(
                                response.json(),
                                {"code": "PLATFORM_DOCTOR_FORBIDDEN"},
                            )

    async def test_health_edit_keeps_patient_and_ai_chat_compatibility(self):
        service, _, _ = _persistence(
            user_context=_source_context(
                agent_type="health",
                patient_id=PATIENT_ID,
            )
        )
        graph = _SuccessfulGraph()
        app = _app(InternalAuthMode.ENFORCE)
        transport = httpx.ASGITransport(app=app)
        payload = {
            "message": "健康问题",
            "patient_id": PATIENT_ID,
            "doctor_id": DOCTOR_ID,
            "agent_type": "health",
            "role": "doctor",
            "session_id": "session-1",
            "conversation_id": "conversation-1",
            "source_message_id": "user-1",
        }
        with (
            patch.object(chat_router, "graph_manager", graph),
            patch.object(
                chat_router,
                "get_chat_persistence_service",
                return_value=service,
            ),
            patch(
                "agents.graph.id_mapping.get_thread_config",
                return_value={"configurable": {"thread_id": "thread-1"}},
            ),
        ):
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/api/chat/edit-resend/stream",
                    json=payload,
                    headers={"Authorization": "Bearer wrong-scope-token"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(graph.stream_calls, 1)


class LegacyBranchSourceAuthorityTest(unittest.IsolatedAsyncioTestCase):
    async def test_research_normal_rejects_cross_owner_before_graph(self):
        service, conversations, messages = _persistence(owner=OTHER_DOCTOR_ID)
        graph = _SuccessfulGraph()
        response = await _post(
            _app(InternalAuthMode.ENFORCE),
            "/api/research/chat",
            service=service,
            graph=graph,
            token="valid-token",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": "PLATFORM_DOCTOR_FORBIDDEN"},
        )
        self.assertEqual(graph.chat_calls, 0)
        self.assertEqual(conversations.write_count, 0)
        self.assertEqual(messages.write_count, 0)

    async def _assert_rejected_without_mutation(
        self,
        route: str,
        *,
        service: ChatPersistenceService,
        conversation_repo: _ConversationRepo,
        message_repo: _MessageRepo,
        expected_status: int,
        expected_code: str,
    ) -> None:
        graph = _SuccessfulGraph()
        message_count = len(message_repo.messages)
        response = await _post(
            _app(InternalAuthMode.ENFORCE),
            route,
            service=service,
            graph=graph,
            token="valid-token",
        )

        self.assertEqual(response.status_code, expected_status)
        self.assertEqual(response.json(), {"code": expected_code})
        self.assertEqual(graph.stream_calls, 0)
        self.assertEqual(conversation_repo.write_count, 0)
        self.assertEqual(message_repo.write_count, 0)
        self.assertEqual(len(message_repo.messages), message_count)

    async def test_edit_and_regenerate_reject_cross_owner_before_graph(self):
        for route in (
            "/api/chat/edit-resend/stream",
            "/api/chat/regenerate/stream",
        ):
            with self.subTest(route=route):
                service, conversations, messages = _persistence(
                    owner=OTHER_DOCTOR_ID
                )
                await self._assert_rejected_without_mutation(
                    route,
                    service=service,
                    conversation_repo=conversations,
                    message_repo=messages,
                    expected_status=403,
                    expected_code="PLATFORM_DOCTOR_FORBIDDEN",
                )

    async def test_edit_rejects_missing_malformed_or_conflicting_source_context(self):
        invalid_contexts = (
            "",
            "{broken",
            MessageContext(metadata={"agent_type": "research"}).to_json(),
            MessageContext(
                metadata={
                    "agent_type": "research",
                    "patient_id": None,
                    "unexpected": "not-canonical",
                }
            ).to_json(),
            _source_context(agent_type="health", patient_id=PATIENT_ID),
            _source_context(agent_type="research", patient_id=PATIENT_ID),
        )
        for user_context in invalid_contexts:
            with self.subTest(user_context=user_context):
                service, conversations, messages = _persistence(
                    user_context=user_context
                )
                await self._assert_rejected_without_mutation(
                    "/api/chat/edit-resend/stream",
                    service=service,
                    conversation_repo=conversations,
                    message_repo=messages,
                    expected_status=409,
                    expected_code="LEGACY_BRANCH_SOURCE_INVALID",
                )

    async def test_edit_rejects_invalid_parent_or_detached_active_path(self):
        def parent_none(conversations, messages):
            messages.messages["user-1"].parent_id = None

        def parent_missing(conversations, messages):
            messages.messages["user-1"].parent_id = "missing-parent"

        def parent_cross_conversation(conversations, messages):
            messages.messages["user-1"].parent_id = "foreign-root"
            messages.messages["foreign-root"] = ChatMessageEntity(
                id="foreign-root",
                chat_id="other-conversation",
                parent_id=None,
                message_order=0,
                message_content="",
                message_type="root",
                status="success",
            )

        def parent_deleted(conversations, messages):
            messages.messages["root-1"].deleted = True

        def parent_failed(conversations, messages):
            messages.messages["root-1"].status = "failed"

        def parent_wrong_role(conversations, messages):
            messages.messages["root-1"].message_type = "user"

        def source_not_on_active_path(conversations, messages):
            conversations.conversation.active_node_id = "root-1"

        cases = (
            parent_none,
            parent_missing,
            parent_cross_conversation,
            parent_deleted,
            parent_failed,
            parent_wrong_role,
            source_not_on_active_path,
        )
        for mutate in cases:
            with self.subTest(case=mutate.__name__):
                service, conversations, messages = _persistence()
                mutate(conversations, messages)
                await self._assert_rejected_without_mutation(
                    "/api/chat/edit-resend/stream",
                    service=service,
                    conversation_repo=conversations,
                    message_repo=messages,
                    expected_status=409,
                    expected_code="LEGACY_BRANCH_SOURCE_INVALID",
                )

    async def test_edit_rejects_duplicate_authority_keys_before_graph(self):
        duplicate_context = (
            '[{"metadata":{'
            '"agent_type":"health",'
            '"agent_type":"research",'
            f'"patient_id":"{PATIENT_ID}",'
            '"patient_id":null}}]'
        )
        service, conversations, messages = _persistence(
            user_context=duplicate_context
        )

        await self._assert_rejected_without_mutation(
            "/api/chat/edit-resend/stream",
            service=service,
            conversation_repo=conversations,
            message_repo=messages,
            expected_status=409,
            expected_code="LEGACY_BRANCH_SOURCE_INVALID",
        )

    async def test_regenerate_rejects_invalid_parent_source_before_graph(self):
        service, conversations, messages = _persistence(
            assistant_parent_id="missing-user"
        )
        await self._assert_rejected_without_mutation(
            "/api/chat/regenerate/stream",
            service=service,
            conversation_repo=conversations,
            message_repo=messages,
            expected_status=409,
            expected_code="LEGACY_BRANCH_SOURCE_INVALID",
        )


class LegacyResearchPublicErrorTest(unittest.IsolatedAsyncioTestCase):
    async def test_graph_failed_result_becomes_stable_http_error(self):
        service, _, _ = _persistence()
        response = await _post(
            _app(InternalAuthMode.OFF),
            "/api/research/chat",
            service=service,
            graph=_FailedResultGraph(),
            token=None,
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "code": "RESEARCH_CHAT_FAILED",
                "message": "科研对话暂时不可用，请稍后再试。",
            },
        )

    async def test_research_and_branch_failures_never_expose_exception_detail(self):
        service, _, _ = _persistence()
        graph = _ExplodingGraph()
        cases = (
            (
                research_router.logger,
                "/api/research/chat",
                500,
                "RESEARCH_CHAT_FAILED",
            ),
            (
                research_router.logger,
                "/api/research/chat/stream",
                200,
                "RESEARCH_CHAT_FAILED",
            ),
            (
                chat_router.logger,
                "/api/chat/edit-resend/stream",
                200,
                "CHAT_STREAM_FAILED",
            ),
        )

        for logger, route, expected_status, expected_code in cases:
            with self.subTest(route=route):
                handler = _RecordingHandler()
                previous_level = logger.level
                previous_propagate = logger.propagate
                logger.setLevel(logging.ERROR)
                logger.propagate = False
                logger.addHandler(handler)
                try:
                    response = await _post(
                        _app(InternalAuthMode.OFF),
                        route,
                        service=service,
                        graph=graph,
                        token=None,
                    )
                finally:
                    logger.removeHandler(handler)
                    logger.setLevel(previous_level)
                    logger.propagate = previous_propagate

                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn(SENTINEL, response.text)
                self.assertIn(expected_code, response.text)
                self.assertTrue(handler.records)
                for record in handler.records:
                    self.assertNotIn(SENTINEL, record.getMessage())
                    self.assertNotIn(SENTINEL, repr(record.args))
                    self.assertIsNone(record.exc_info)


class LegacyResearchOpenApiContractTest(unittest.TestCase):
    def test_patient_field_documents_null_only_wire_compatibility(self):
        description = (
            ResearchChatRequest.model_json_schema()["properties"]["patient_id"]
            ["description"]
        )

        self.assertEqual(
            description,
            "科研模式必须为空；字段仅为 wire compatibility 保留",
        )


if __name__ == "__main__":
    unittest.main()
