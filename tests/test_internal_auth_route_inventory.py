import ast
import unittest
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from domain.security.principal import CurrentPrincipal
from infrastructure.security.config import InternalAuthMode, InternalAuthSettings
from infrastructure.security.errors import JwksUnavailableError
from presentation.middleware import internal_jwt_auth
from presentation.middleware.internal_jwt_auth import should_authenticate


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MAIN_PATH = _PROJECT_ROOT / "main.py"
_ORIGIN = "https://platform.example"
_JWKS_URL = "https://backend.example/internal/auth/jwks"
_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put"}
)

_ROUTE_SOURCES = {
    "main.py": "",
    "presentation/routers/asr_router.py": "",
    "presentation/routers/chat_router.py": "/api/chat",
    "presentation/routers/compliance_router.py": "/api/compliance",
    "presentation/routers/conversation_router.py": "/api/conversations",
    "presentation/routers/file_router.py": "/api",
    "presentation/routers/recommendation_router.py": "/api/recommendation",
    "presentation/routers/research_router.py": "/api/research",
    "presentation/routers/platform_chat_turn_router.py": "/api/platform/chat/turns",
    "presentation/routers/research_document_router.py": "/api/platform/research-documents",
}

PLATFORM_EXCLUSIVE_ROUTE_TEMPLATES = frozenset(
    {
        ("GET", "/api/conversations/{conversation_id}"),
        ("POST", "/api/chat/edit-resend/stream"),
        ("POST", "/api/chat/regenerate/stream"),
        ("POST", "/api/research/chat/stream"),
        ("PUT", "/api/conversations/{conversation_id}/active-branch"),
        ("POST", "/api/platform/chat/turns/prepare"),
        ("POST", "/api/platform/chat/turns/execute"),
        ("GET", "/api/platform/chat/turns/{request_id}"),
        ("POST", "/api/platform/chat/turns/{request_id}/abort"),
        ("DELETE", "/api/platform/research-documents/{attachment_id}"),
    }
)

PATIENT_COMPATIBILITY_ROUTES = frozenset(
    {
        ("POST", "/api/chat"),
        ("POST", "/api/chat/stream"),
        ("POST", "/api/upload"),
        ("POST", "/api/asr/transcribe"),
    }
)

# This table is intentionally explicit. A route change must update the security
# inventory in the same review instead of relying on imports with DB side effects.
CURRENT_HTTP_API_ROUTES = frozenset(
    {
        ("DELETE", "/api/chat/{session_id}"),
        ("DELETE", "/api/conversations/{conversation_id}"),
        ("DELETE", "/api/research/conversations/{conversation_id}"),
        ("GET", "/api/chat/{session_id}/agent-history"),
        ("GET", "/api/chat/{session_id}/checkpoints"),
        ("GET", "/api/chat/{session_id}/messages"),
        ("GET", "/api/chat/{session_id}/state"),
        ("GET", "/api/compliance/health"),
        ("GET", "/api/conversations"),
        ("GET", "/api/conversations/{conversation_id}"),
        ("GET", "/api/export/{session_id}"),
        ("GET", "/api/info"),
        ("GET", "/api/recommendation/health"),
        ("GET", "/api/research/conversations"),
        ("GET", "/api/research/conversations/{conversation_id}"),
        ("GET", "/api/research/health"),
        ("GET", "/api/users"),
        ("POST", "/api/asr/transcribe"),
        ("POST", "/api/chat"),
        ("POST", "/api/chat/edit-resend/stream"),
        ("POST", "/api/chat/regenerate/stream"),
        ("POST", "/api/chat/stream"),
        ("POST", "/api/compliance/chat"),
        ("POST", "/api/compliance/chat/stream"),
        ("POST", "/api/recommendation/chat"),
        ("POST", "/api/recommendation/chat/stream"),
        ("POST", "/api/research/chat"),
        ("POST", "/api/research/chat/stream"),
        ("POST", "/api/upload"),
        ("PUT", "/api/conversations/{conversation_id}/active-branch"),
        ("POST", "/api/platform/chat/turns/prepare"),
        ("POST", "/api/platform/chat/turns/execute"),
        ("GET", "/api/platform/chat/turns/{request_id}"),
        ("POST", "/api/platform/chat/turns/{request_id}/abort"),
        ("DELETE", "/api/platform/research-documents/{attachment_id}"),
    }
)


def _source_routes(relative_path: str, prefix: str) -> set[tuple[str, str]]:
    tree = ast.parse((_PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))
    routes: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            function = decorator.func
            if not isinstance(function, ast.Attribute):
                continue
            method = function.attr.lower()
            if method not in _HTTP_METHODS or not decorator.args:
                continue
            route_argument = decorator.args[0]
            if not (
                isinstance(route_argument, ast.Constant)
                and isinstance(route_argument.value, str)
            ):
                continue
            path = f"{prefix}{route_argument.value}" or "/"
            routes.add((method.upper(), path))
    return routes


def _discovered_api_routes() -> frozenset[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for relative_path, prefix in _ROUTE_SOURCES.items():
        routes.update(_source_routes(relative_path, prefix))
    return frozenset(route for route in routes if route[1].startswith("/api"))


def _scope(method: str, path: str, *, scope_type: str = "http") -> dict:
    return {"type": scope_type, "method": method, "path": path}


def _concrete_path(path: str) -> str:
    return (
        path.replace("{conversation_id}", "conversation-7")
        .replace("{session_id}", "session-7")
        .replace("{attachment_id}", "33333333-3333-4333-8333-333333333333")
    )


def _effective_auth_mode(
    scope: dict,
    configured_mode: InternalAuthMode,
) -> InternalAuthMode:
    resolver = getattr(internal_jwt_auth, "effective_auth_mode", None)
    if not callable(resolver):
        raise AssertionError(
            "presentation.middleware.internal_jwt_auth.effective_auth_mode "
            "must be implemented"
        )
    return resolver(scope, configured_mode)


def _settings(mode: InternalAuthMode) -> InternalAuthSettings:
    return InternalAuthSettings(
        mode=mode,
        jwks_url=None if mode is InternalAuthMode.OFF else _JWKS_URL,
    )


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
    def __init__(self, *, error: Optional[Exception] = None) -> None:
        self.error = error
        self.tokens: list[str] = []

    async def verify(self, token: str) -> CurrentPrincipal:
        self.tokens.append(token)
        if self.error is not None:
            raise self.error
        raise AssertionError("this verifier must not return a principal")


class InternalAuthRouteInventoryTest(unittest.TestCase):
    def test_explicit_inventory_matches_current_source_routes(self):
        self.assertEqual(_discovered_api_routes(), CURRENT_HTTP_API_ROUTES)

    def test_turn_watchdog_is_lifespan_internal_not_an_http_route(self):
        tree = ast.parse(_MAIN_PATH.read_text(encoding="utf-8"))
        lifespan = next(
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "lifespan"
        )
        calls = {
            node.func.id
            for node in ast.walk(lifespan)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        }

        self.assertIn("get_chat_turn_watchdog", calls)
        self.assertFalse(
            any("watchdog" in path for _method, path in _discovered_api_routes())
        )

    def test_every_current_http_api_route_requires_authentication(self):
        for method, path in sorted(CURRENT_HTTP_API_ROUTES):
            with self.subTest(method=method, path=path):
                self.assertTrue(should_authenticate(_scope(method, path)))

    def test_every_current_route_has_stable_telemetry_template(self):
        normalizer = getattr(
            internal_jwt_auth, "normalized_route_template", None
        )
        self.assertTrue(callable(normalizer))

        for method, route_template in sorted(CURRENT_HTTP_API_ROUTES):
            with self.subTest(method=method, route=route_template):
                self.assertEqual(
                    normalizer(_scope(method, _concrete_path(route_template))),
                    route_template,
                )

        self.assertEqual(
            normalizer(_scope("PATCH", "/api/future/sensitive-value")),
            "/api/{unknown}",
        )

    def test_enforce_mode_only_escalates_platform_exclusive_inventory(self):
        self.assertTrue(
            PLATFORM_EXCLUSIVE_ROUTE_TEMPLATES <= CURRENT_HTTP_API_ROUTES
        )
        self.assertTrue(PATIENT_COMPATIBILITY_ROUTES <= CURRENT_HTTP_API_ROUTES)

        for method, route_template in sorted(CURRENT_HTTP_API_ROUTES):
            with self.subTest(method=method, path=route_template):
                expected_mode = (
                    InternalAuthMode.ENFORCE
                    if (method, route_template)
                    in PLATFORM_EXCLUSIVE_ROUTE_TEMPLATES
                    else InternalAuthMode.OBSERVE
                )
                self.assertIs(
                    _effective_auth_mode(
                        _scope(method, _concrete_path(route_template)),
                        InternalAuthMode.ENFORCE,
                    ),
                    expected_mode,
                )

    def test_platform_route_matching_rejects_method_and_path_variants(self):
        observe_requests = (
            ("POST", "/api/conversations/conversation-7"),
            ("GET", "/api/conversations/conversation-7/extra"),
            ("GET", "/api/conversations/conversation-7/"),
            ("PUT", "/api/conversations/conversation-7/active-branch/"),
            ("PATCH", "/api/future/business-route"),
        )

        for method, path in observe_requests:
            with self.subTest(method=method, path=path):
                self.assertIs(
                    _effective_auth_mode(
                        _scope(method, path),
                        InternalAuthMode.ENFORCE,
                    ),
                    InternalAuthMode.OBSERVE,
                )

    def test_off_and_observe_modes_never_escalate_routes(self):
        routes = (
            ("GET", "/api/conversations/conversation-7"),
            ("PATCH", "/api/future/business-route"),
        )
        for configured_mode in (
            InternalAuthMode.OFF,
            InternalAuthMode.OBSERVE,
        ):
            for method, path in routes:
                with self.subTest(
                    configured_mode=configured_mode,
                    method=method,
                    path=path,
                ):
                    self.assertIs(
                        _effective_auth_mode(
                            _scope(method, path),
                            configured_mode,
                        ),
                        configured_mode,
                    )

    def test_future_api_routes_are_covered_without_per_route_dependencies(self):
        self.assertTrue(should_authenticate(_scope("POST", "/api")))
        self.assertTrue(
            should_authenticate(_scope("PATCH", "/api/future/business-route"))
        )

    def test_health_and_asr_websocket_are_outside_the_http_auth_boundary(self):
        self.assertFalse(should_authenticate(_scope("GET", "/health")))
        self.assertFalse(
            should_authenticate(
                _scope("GET", "/ws/asr", scope_type="websocket")
            )
        )

    def test_main_installs_auth_before_cors_without_importing_main(self):
        tree = ast.parse(_MAIN_PATH.read_text(encoding="utf-8"))
        auth_call_indexes: list[int] = []
        cors_call_indexes: list[int] = []

        for index, statement in enumerate(tree.body):
            if not (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
            ):
                continue
            call = statement.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "install_internal_auth"
                and len(call.args) == 1
                and isinstance(call.args[0], ast.Name)
                and call.args[0].id == "app"
                and not call.keywords
            ):
                auth_call_indexes.append(index)
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "app"
                and call.func.attr == "add_middleware"
                and call.args
                and isinstance(call.args[0], ast.Name)
                and call.args[0].id == "CORSMiddleware"
            ):
                cors_call_indexes.append(index)

        self.assertEqual(len(auth_call_indexes), 1)
        self.assertEqual(len(cors_call_indexes), 1)
        self.assertLess(auth_call_indexes[0], cors_call_indexes[0])


class InternalAuthApplicationWiringTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _app(
        verifier: StubVerifier,
    ) -> tuple[FastAPI, dict[str, int]]:
        app = FastAPI()
        handler_calls = {"count": 0}

        @app.get("/api/conversations/conversation-7")
        async def protected() -> dict[str, bool]:
            handler_calls["count"] += 1
            return {"ok": True}

        _install_internal_auth(
            app,
            settings=_settings(InternalAuthMode.ENFORCE),
            verifier_factory=lambda _settings: verifier,
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[_ORIGIN],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return app, handler_calls

    async def test_cors_wraps_enforce_401_and_503_responses(self):
        cases = (
            (StubVerifier(), {}, 401, "INTERNAL_AUTH_REQUIRED"),
            (
                StubVerifier(error=JwksUnavailableError("network down")),
                {"Authorization": "Bearer signed.raw.token"},
                503,
                "INTERNAL_AUTH_UNAVAILABLE",
            ),
        )

        for verifier, auth_headers, expected_status, expected_code in cases:
            with self.subTest(expected_status=expected_status):
                app, handler_calls = self._app(verifier)
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    response = await client.get(
                        "/api/conversations/conversation-7",
                        headers={"Origin": _ORIGIN, **auth_headers},
                    )

                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.json(), {"code": expected_code})
                self.assertEqual(
                    response.headers.get("access-control-allow-origin"),
                    _ORIGIN,
                )
                self.assertEqual(handler_calls["count"], 0)

    async def test_cors_preflight_does_not_call_auth_verifier(self):
        verifier = StubVerifier(
            error=AssertionError("OPTIONS must not call the verifier")
        )
        app, handler_calls = self._app(verifier)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.options(
                "/api/conversations/conversation-7",
                headers={
                    "Origin": _ORIGIN,
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            _ORIGIN,
        )
        self.assertEqual(verifier.tokens, [])
        self.assertEqual(handler_calls["count"], 0)
