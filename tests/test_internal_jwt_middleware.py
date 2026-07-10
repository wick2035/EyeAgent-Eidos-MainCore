import json
import logging
import unittest
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from domain.security.principal import CurrentPrincipal
from infrastructure.security.config import InternalAuthMode, InternalAuthSettings
from infrastructure.security.errors import (
    JwksUnavailableError,
    TokenValidationError,
)
from presentation.dependencies.security import get_current_principal
from presentation.middleware.internal_jwt_auth import (
    InternalJWTAuthMiddleware,
    should_authenticate,
)


_JWKS_URL = "https://backend.example/internal/auth/jwks"
_LOGGER_NAME = "presentation.middleware.internal_jwt_auth"


class RecordingLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _exception_chain_text(exc_info: Any) -> str:
    if exc_info is None:
        return ""

    exception = exc_info[1]
    seen: set[int] = set()
    chain: list[str] = []
    while exception is not None and id(exception) not in seen:
        seen.add(id(exception))
        chain.append(repr(exception))
        exception = exception.__cause__ or exception.__context__
    return "\n".join(chain)


def _traceback_frame_locals_text(exc_info: Any) -> str:
    traceback = None if exc_info is None else exc_info[2]
    frame_locals: list[str] = []
    while traceback is not None:
        frame_locals.append(repr(dict(traceback.tb_frame.f_locals)))
        traceback = traceback.tb_next
    return "\n".join(frame_locals)


def _principal() -> CurrentPrincipal:
    return CurrentPrincipal(
        issuer="eye-agent-backend",
        subject="doctor:42",
        principal_type="doctor",
        roles=frozenset({"DOCTOR", "USER"}),
        scopes=frozenset({"ai:chat", "conversation:read"}),
        institution_id="institution-7",
        tenant_id="tenant-3",
        authorized_party="eye-agent-java-gateway",
        schema_version=1,
        token_id="token-123",
        issued_at=1_700_000_000,
        not_before=1_700_000_000,
        expires_at=1_700_000_300,
    )


def _scope(
    *,
    scope_type: str = "http",
    method: str = "GET",
    path: str = "/api/chat",
    headers: Optional[list[tuple[bytes, bytes]]] = None,
    state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    scope: dict[str, Any] = {
        "type": scope_type,
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": list(headers or []),
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    if state is not None:
        scope["state"] = state
    return scope


def _authorization(value: str) -> list[tuple[bytes, bytes]]:
    return [(b"authorization", value.encode("ascii"))]


class RecordingApp:
    def __init__(self) -> None:
        self.scopes: list[dict[str, Any]] = []

    async def __call__(self, scope, receive, send) -> None:
        self.scopes.append(scope)
        if scope["type"] != "http":
            return
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"ok":true}',
            }
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
            raise AssertionError("test verifier has no configured result")
        return self.principal


class RecordingVerifierFactory:
    def __init__(self, verifier: StubVerifier) -> None:
        self.verifier = verifier
        self.settings: list[InternalAuthSettings] = []

    def __call__(self, settings: InternalAuthSettings) -> StubVerifier:
        self.settings.append(settings)
        return self.verifier


class FailingVerifierFactory:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, settings: InternalAuthSettings) -> StubVerifier:
        self.calls += 1
        raise AssertionError("off mode must not construct a verifier")


class InternalJWTAuthMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    def _middleware(
        self,
        mode: InternalAuthMode,
        *,
        verifier: Optional[StubVerifier] = None,
        factory: Optional[Any] = None,
    ) -> tuple[RecordingApp, InternalJWTAuthMiddleware, Any]:
        app = RecordingApp()
        settings = InternalAuthSettings(
            mode=mode,
            jwks_url=None if mode is InternalAuthMode.OFF else _JWKS_URL,
        )
        actual_verifier = verifier or StubVerifier(principal=_principal())
        actual_factory = factory or RecordingVerifierFactory(actual_verifier)
        middleware = InternalJWTAuthMiddleware(
            app,
            settings=settings,
            verifier_factory=actual_factory,
        )
        return app, middleware, actual_factory

    async def _call(
        self,
        middleware: InternalJWTAuthMiddleware,
        scope: dict[str, Any],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        async def receive() -> dict[str, Any]:
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await middleware(scope, receive, send)
        return messages

    @staticmethod
    def _status(messages: list[dict[str, Any]]) -> int:
        response_start = next(
            message
            for message in messages
            if message["type"] == "http.response.start"
        )
        return response_start["status"]

    @staticmethod
    def _headers(messages: list[dict[str, Any]]) -> dict[str, str]:
        response_start = next(
            message
            for message in messages
            if message["type"] == "http.response.start"
        )
        return {
            name.decode("latin-1").lower(): value.decode("latin-1")
            for name, value in response_start["headers"]
        }

    @staticmethod
    def _json_body(messages: list[dict[str, Any]]) -> dict[str, Any]:
        body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return json.loads(body)

    def test_should_authenticate_only_http_api_non_options(self):
        cases = (
            (_scope(path="/api"), True),
            (_scope(path="/api/chat"), True),
            (_scope(path="/apiology"), False),
            (_scope(path="/health"), False),
            (_scope(method="OPTIONS", path="/api/chat"), False),
            (_scope(scope_type="websocket", path="/api/chat"), False),
        )

        for scope, expected in cases:
            with self.subTest(scope=scope):
                self.assertIs(should_authenticate(scope), expected)

    async def test_off_missing_token_passes_without_constructing_verifier(self):
        factory = FailingVerifierFactory()
        app, middleware, _ = self._middleware(
            InternalAuthMode.OFF,
            factory=factory,
        )
        scope = _scope()

        messages = await self._call(middleware, scope)

        self.assertEqual(self._status(messages), 200)
        self.assertEqual(len(app.scopes), 1)
        self.assertEqual(factory.calls, 0)
        self.assertEqual(scope["state"], {"internal_principal": None})

    async def test_off_forged_token_passes_without_parsing(self):
        factory = FailingVerifierFactory()
        app, middleware, _ = self._middleware(
            InternalAuthMode.OFF,
            factory=factory,
        )
        scope = _scope(headers=_authorization("Bearer forged.secret.token"))

        messages = await self._call(middleware, scope)

        self.assertEqual(self._status(messages), 200)
        self.assertEqual(len(app.scopes), 1)
        self.assertEqual(factory.calls, 0)
        self.assertEqual(scope["state"], {"internal_principal": None})

    async def test_observe_missing_token_logs_legacy_missing_and_passes(self):
        verifier = StubVerifier(principal=_principal())
        app, middleware, factory = self._middleware(
            InternalAuthMode.OBSERVE,
            verifier=verifier,
        )
        scope = _scope()

        with self.assertLogs(_LOGGER_NAME, level=logging.WARNING) as captured:
            messages = await self._call(middleware, scope)

        self.assertEqual(self._status(messages), 200)
        self.assertEqual(len(app.scopes), 1)
        self.assertEqual(len(factory.settings), 1)
        self.assertEqual(verifier.tokens, [])
        self.assertIsNone(scope["state"]["internal_principal"])
        self.assertIn("legacy_missing", "\n".join(captured.output))

    async def test_observe_invalid_token_logs_invalid_without_token_and_passes(self):
        token = "attacker-controlled.raw.token"
        verifier = StubVerifier(
            error=TokenValidationError(f"invalid credential: {token}")
        )
        app, middleware, _ = self._middleware(
            InternalAuthMode.OBSERVE,
            verifier=verifier,
        )
        scope = _scope(headers=_authorization(f"Bearer {token}"))

        with self.assertLogs(_LOGGER_NAME, level=logging.WARNING) as captured:
            messages = await self._call(middleware, scope)

        logs = "\n".join(captured.output)
        self.assertEqual(self._status(messages), 200)
        self.assertEqual(len(app.scopes), 1)
        self.assertEqual(verifier.tokens, [token])
        self.assertIsNone(scope["state"]["internal_principal"])
        self.assertIn("invalid", logs)
        self.assertNotIn(token, logs)

    async def test_observe_valid_token_sets_principal_without_storing_token(self):
        token = "signed.raw.token"
        principal = _principal()
        verifier = StubVerifier(principal=principal)
        app, middleware, _ = self._middleware(
            InternalAuthMode.OBSERVE,
            verifier=verifier,
        )
        scope = _scope(
            headers=_authorization(f"Bearer {token}"),
            state={"request_id": "request-7"},
        )

        messages = await self._call(middleware, scope)

        self.assertEqual(self._status(messages), 200)
        self.assertEqual(len(app.scopes), 1)
        self.assertIs(scope["state"]["internal_principal"], principal)
        self.assertEqual(scope["state"]["request_id"], "request-7")
        self.assertNotIn(token, repr(scope["state"]))

    async def test_observe_jwks_unavailable_logs_unavailable_and_passes(self):
        token = "signed.raw.token"
        verifier = StubVerifier(
            error=JwksUnavailableError(f"upstream unavailable for {token}")
        )
        app, middleware, _ = self._middleware(
            InternalAuthMode.OBSERVE,
            verifier=verifier,
        )
        scope = _scope(headers=_authorization(f"Bearer {token}"))

        with self.assertLogs(_LOGGER_NAME, level=logging.WARNING) as captured:
            messages = await self._call(middleware, scope)

        logs = "\n".join(captured.output)
        self.assertEqual(self._status(messages), 200)
        self.assertEqual(len(app.scopes), 1)
        self.assertIsNone(scope["state"]["internal_principal"])
        self.assertIn("unavailable", logs)
        self.assertNotIn(token, logs)

    async def test_observe_unexpected_error_logs_sanitized_internal_error_and_passes(self):
        token = "signed.raw.token"
        verifier = StubVerifier(error=RuntimeError(f"secret failure: {token}"))
        app, middleware, _ = self._middleware(
            InternalAuthMode.OBSERVE,
            verifier=verifier,
        )
        scope = _scope(headers=_authorization(f"Bearer {token}"))

        with self.assertLogs(_LOGGER_NAME, level=logging.ERROR) as captured:
            messages = await self._call(middleware, scope)

        logs = "\n".join(captured.output)
        self.assertEqual(self._status(messages), 200)
        self.assertEqual(len(app.scopes), 1)
        self.assertIsNone(scope["state"]["internal_principal"])
        self.assertIn("internal_error", logs)
        self.assertNotIn(token, logs)

    async def test_unexpected_error_log_record_cannot_reveal_raw_token(self):
        cases = (
            (InternalAuthMode.OBSERVE, 200, 1),
            (InternalAuthMode.ENFORCE, 500, 0),
        )

        for mode, expected_status, downstream_calls in cases:
            with self.subTest(mode=mode):
                token = f"signed.raw.token.{mode.value}"
                verifier = StubVerifier(
                    error=RuntimeError(f"secret failure: {token}")
                )
                app, middleware, _ = self._middleware(
                    mode,
                    verifier=verifier,
                )
                scope = _scope(headers=_authorization(f"Bearer {token}"))
                handler = RecordingLogHandler()
                event_logger = logging.getLogger(_LOGGER_NAME)
                previous_level = event_logger.level
                previous_propagate = event_logger.propagate
                event_logger.setLevel(logging.ERROR)
                event_logger.propagate = False
                event_logger.addHandler(handler)
                try:
                    messages = await self._call(middleware, scope)
                finally:
                    event_logger.removeHandler(handler)
                    event_logger.setLevel(previous_level)
                    event_logger.propagate = previous_propagate

                self.assertEqual(self._status(messages), expected_status)
                self.assertEqual(len(app.scopes), downstream_calls)
                self.assertEqual(len(handler.records), 1)
                record = handler.records[0]
                exposed_surfaces = {
                    "message": record.getMessage(),
                    "args": repr(record.args),
                    "exception_chain": _exception_chain_text(
                        record.exc_info
                    ),
                    "frame_locals": _traceback_frame_locals_text(
                        record.exc_info
                    ),
                    "exc_text": record.exc_text or "",
                    "stack_info": record.stack_info or "",
                }
                leaks = {
                    surface: token in value
                    for surface, value in exposed_surfaces.items()
                }
                leaks["exc_info_attached"] = record.exc_info is not None

                self.assertEqual(
                    leaks,
                    {surface: False for surface in leaks},
                )

    async def test_enforce_missing_token_returns_required_401_before_downstream(self):
        verifier = StubVerifier(principal=_principal())
        app, middleware, _ = self._middleware(
            InternalAuthMode.ENFORCE,
            verifier=verifier,
        )
        scope = _scope()

        messages = await self._call(middleware, scope)

        self.assertEqual(self._status(messages), 401)
        self.assertEqual(
            self._json_body(messages),
            {"code": "INTERNAL_AUTH_REQUIRED"},
        )
        self.assertEqual(self._headers(messages)["www-authenticate"], "Bearer")
        self.assertEqual(app.scopes, [])
        self.assertEqual(verifier.tokens, [])
        self.assertEqual(scope["state"], {"internal_principal": None})

    async def test_enforce_rejects_non_bearer_and_duplicate_authorization(self):
        cases = (
            _authorization("Basic abc123"),
            [
                (b"authorization", b"Bearer first.token.value"),
                (b"Authorization", b"Bearer second.token.value"),
            ],
        )

        for headers in cases:
            with self.subTest(headers=headers):
                verifier = StubVerifier(principal=_principal())
                app, middleware, _ = self._middleware(
                    InternalAuthMode.ENFORCE,
                    verifier=verifier,
                )
                scope = _scope(headers=headers)

                messages = await self._call(middleware, scope)

                self.assertEqual(self._status(messages), 401)
                self.assertEqual(
                    self._json_body(messages),
                    {"code": "INTERNAL_AUTH_INVALID"},
                )
                self.assertEqual(
                    self._headers(messages)["www-authenticate"],
                    "Bearer",
                )
                self.assertEqual(app.scopes, [])
                self.assertEqual(verifier.tokens, [])
                self.assertEqual(
                    scope["state"],
                    {"internal_principal": None},
                )

    async def test_enforce_invalid_token_returns_invalid_401(self):
        token = "invalid.raw.token"
        verifier = StubVerifier(error=TokenValidationError("invalid token"))
        app, middleware, _ = self._middleware(
            InternalAuthMode.ENFORCE,
            verifier=verifier,
        )
        scope = _scope(headers=_authorization(f"Bearer {token}"))

        messages = await self._call(middleware, scope)

        self.assertEqual(self._status(messages), 401)
        self.assertEqual(
            self._json_body(messages),
            {"code": "INTERNAL_AUTH_INVALID"},
        )
        self.assertEqual(self._headers(messages)["www-authenticate"], "Bearer")
        self.assertEqual(app.scopes, [])
        self.assertEqual(verifier.tokens, [token])

    async def test_enforce_jwks_unavailable_returns_503(self):
        verifier = StubVerifier(error=JwksUnavailableError("network down"))
        app, middleware, _ = self._middleware(
            InternalAuthMode.ENFORCE,
            verifier=verifier,
        )
        scope = _scope(headers=_authorization("Bearer signed.raw.token"))

        messages = await self._call(middleware, scope)

        self.assertEqual(self._status(messages), 503)
        self.assertEqual(
            self._json_body(messages),
            {"code": "INTERNAL_AUTH_UNAVAILABLE"},
        )
        self.assertNotIn("www-authenticate", self._headers(messages))
        self.assertEqual(app.scopes, [])
        self.assertIsNone(scope["state"]["internal_principal"])

    async def test_enforce_unexpected_error_returns_500_without_leaking_token(self):
        token = "signed.raw.token"
        verifier = StubVerifier(error=RuntimeError(f"secret failure: {token}"))
        app, middleware, _ = self._middleware(
            InternalAuthMode.ENFORCE,
            verifier=verifier,
        )
        scope = _scope(headers=_authorization(f"Bearer {token}"))

        with self.assertLogs(_LOGGER_NAME, level=logging.ERROR) as captured:
            messages = await self._call(middleware, scope)

        logs = "\n".join(captured.output)
        self.assertEqual(self._status(messages), 500)
        self.assertEqual(
            self._json_body(messages),
            {"code": "INTERNAL_AUTH_INTERNAL_ERROR"},
        )
        self.assertEqual(app.scopes, [])
        self.assertIn("internal_error", logs)
        self.assertNotIn(token, logs)

    async def test_enforce_valid_token_sets_principal_and_calls_downstream(self):
        token = "signed.raw.token"
        principal = _principal()
        verifier = StubVerifier(principal=principal)
        app, middleware, _ = self._middleware(
            InternalAuthMode.ENFORCE,
            verifier=verifier,
        )
        scope = _scope(headers=_authorization(f"Bearer {token}"))

        messages = await self._call(middleware, scope)

        self.assertEqual(self._status(messages), 200)
        self.assertEqual(len(app.scopes), 1)
        self.assertEqual(verifier.tokens, [token])
        self.assertIs(scope["state"]["internal_principal"], principal)
        self.assertNotIn(token, repr(scope["state"]))

    async def test_health_options_and_websocket_bypass_authentication(self):
        cases = (
            _scope(path="/health"),
            _scope(method="OPTIONS", path="/api/chat"),
            _scope(scope_type="websocket", path="/api/chat"),
        )

        for scope in cases:
            with self.subTest(scope=scope):
                verifier = StubVerifier(principal=_principal())
                app, middleware, _ = self._middleware(
                    InternalAuthMode.ENFORCE,
                    verifier=verifier,
                )

                await self._call(middleware, scope)

                self.assertEqual(len(app.scopes), 1)
                self.assertEqual(verifier.tokens, [])
                self.assertNotIn("state", scope)

    def test_middleware_is_pure_asgi_not_base_http_middleware(self):
        _, middleware, _ = self._middleware(InternalAuthMode.OFF)

        self.assertNotIsInstance(middleware, BaseHTTPMiddleware)


class CurrentPrincipalDependencyTest(unittest.TestCase):
    def test_returns_current_principal_from_request_state(self):
        principal = _principal()
        request = Request(_scope(state={"internal_principal": principal}))

        self.assertIs(get_current_principal(request), principal)

    def test_returns_none_when_request_state_has_no_principal(self):
        request = Request(_scope(state={}))

        self.assertIsNone(get_current_principal(request))
