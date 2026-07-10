import json
import unittest
from dataclasses import dataclass, field
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from domain.security.principal import CurrentPrincipal
from infrastructure.security.config import InternalAuthMode, InternalAuthSettings
from infrastructure.security.errors import TokenValidationError
from presentation.dependencies.security import get_current_principal
from presentation.middleware import internal_jwt_auth


_JWKS_URL = "https://backend.example/internal/auth/jwks"
_RAW_TOKEN = "eyJ.raw-internal-token.signature-secret"
SSE_PATHS = (
    "/api/chat/stream",
    "/api/chat/edit-resend/stream",
    "/api/chat/regenerate/stream",
    "/api/research/chat/stream",
    "/api/compliance/chat/stream",
    "/api/recommendation/chat/stream",
)


def _principal() -> CurrentPrincipal:
    return CurrentPrincipal(
        issuer="eye-agent-backend",
        subject="doctor:42",
        principal_type="doctor",
        roles=frozenset({"DOCTOR", "USER"}),
        scopes=frozenset({"maincore:invoke"}),
        institution_id="institution-7",
        tenant_id="tenant-9",
        authorized_party="eye-agent-java-gateway",
        schema_version=1,
        token_id="jti-123",
        issued_at=1_700_000_000,
        not_before=1_700_000_000,
        expires_at=1_700_000_300,
    )


def _settings(mode: InternalAuthMode) -> InternalAuthSettings:
    return InternalAuthSettings(mode=mode, jwks_url=_JWKS_URL)


def _install_internal_auth(
    app: FastAPI,
    *,
    settings: InternalAuthSettings,
    verifier_factory,
) -> None:
    installer = getattr(internal_jwt_auth, "install_internal_auth", None)
    if not callable(installer):
        raise AssertionError(
            "presentation.middleware.internal_jwt_auth.install_internal_auth "
            "must be implemented"
        )
    installer(
        app,
        settings=settings,
        verifier_factory=verifier_factory,
    )


class StubVerifier:
    def __init__(
        self,
        *,
        principal: Optional[CurrentPrincipal] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self.principal = principal
        self.error = error
        self.tokens: list[str] = []

    async def verify(self, token: str) -> CurrentPrincipal:
        self.tokens.append(token)
        if self.error is not None:
            raise self.error
        if self.principal is None:
            raise AssertionError("stub verifier principal is missing")
        return self.principal


@dataclass
class StreamProbe:
    downstream_calls: int = 0
    handler_calls: int = 0
    generator_starts: int = 0
    principals: list[Optional[CurrentPrincipal]] = field(default_factory=list)


class DownstreamCounterMiddleware:
    def __init__(self, app: ASGIApp, *, probe: StreamProbe) -> None:
        self._app = app
        self._probe = probe

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] == "http":
            self._probe.downstream_calls += 1
        await self._app(scope, receive, send)


def _streaming_app(
    *,
    mode: InternalAuthMode,
    verifier: StubVerifier,
) -> tuple[FastAPI, StreamProbe]:
    app = FastAPI()
    probe = StreamProbe()

    async def stream_endpoint(request: Request) -> StreamingResponse:
        probe.handler_calls += 1
        principal = get_current_principal(request)
        probe.principals.append(principal)

        async def events():
            probe.generator_starts += 1
            payload = {
                "subject": None if principal is None else principal.subject,
                "principal_type": (
                    None if principal is None else principal.principal_type
                ),
            }
            yield f"event: principal\ndata: {json.dumps(payload)}\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"X-Stream-Contract": "principal-only"},
        )

    for path in SSE_PATHS:
        app.add_api_route(path, stream_endpoint, methods=["POST"])

    app.add_middleware(DownstreamCounterMiddleware, probe=probe)
    _install_internal_auth(
        app,
        settings=_settings(mode),
        verifier_factory=lambda _settings: verifier,
    )
    return app, probe


async def _post(
    app: FastAPI,
    path: str,
    *,
    token: Optional[str] = None,
) -> httpx.Response:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(path, headers=headers)


class InternalAuthSSEBoundaryTest(unittest.IsolatedAsyncioTestCase):
    async def test_enforce_missing_rejects_before_downstream_and_generator(self):
        for path in SSE_PATHS:
            with self.subTest(path=path):
                verifier = StubVerifier(principal=_principal())
                app, probe = _streaming_app(
                    mode=InternalAuthMode.ENFORCE,
                    verifier=verifier,
                )

                response = await _post(app, path)

                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.json(),
                    {"code": "INTERNAL_AUTH_REQUIRED"},
                )
                self.assertEqual(probe.downstream_calls, 0)
                self.assertEqual(probe.handler_calls, 0)
                self.assertEqual(probe.generator_starts, 0)
                self.assertNotIn(
                    "text/event-stream",
                    response.headers.get("content-type", ""),
                )
                self.assertEqual(verifier.tokens, [])

    async def test_observe_invalid_still_streams_once_without_token_leak(self):
        for path in SSE_PATHS:
            with self.subTest(path=path):
                verifier = StubVerifier(
                    error=TokenValidationError("invalid token")
                )
                app, probe = _streaming_app(
                    mode=InternalAuthMode.OBSERVE,
                    verifier=verifier,
                )

                response = await _post(app, path, token=_RAW_TOKEN)

                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "text/event-stream",
                    response.headers.get("content-type", ""),
                )
                self.assertEqual(probe.downstream_calls, 1)
                self.assertEqual(probe.handler_calls, 1)
                self.assertEqual(probe.generator_starts, 1)
                self.assertEqual(probe.principals, [None])
                self.assertEqual(verifier.tokens, [_RAW_TOKEN])
                self.assertNotIn(_RAW_TOKEN, response.text)
                self.assertNotIn(_RAW_TOKEN, repr(dict(response.headers)))

    async def test_enforce_valid_stream_exposes_principal_without_token_leak(self):
        for path in SSE_PATHS:
            with self.subTest(path=path):
                principal = _principal()
                verifier = StubVerifier(principal=principal)
                app, probe = _streaming_app(
                    mode=InternalAuthMode.ENFORCE,
                    verifier=verifier,
                )

                response = await _post(app, path, token=_RAW_TOKEN)

                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "text/event-stream",
                    response.headers.get("content-type", ""),
                )
                self.assertEqual(probe.downstream_calls, 1)
                self.assertEqual(probe.handler_calls, 1)
                self.assertEqual(probe.generator_starts, 1)
                self.assertEqual(probe.principals, [principal])
                self.assertEqual(verifier.tokens, [_RAW_TOKEN])
                self.assertIn(principal.subject, response.text)
                self.assertNotIn(_RAW_TOKEN, response.text)
                self.assertNotIn(_RAW_TOKEN, repr(dict(response.headers)))
