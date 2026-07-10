import hashlib
import logging
from collections.abc import Callable
from typing import Protocol

import jwt
from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from domain.security.principal import CurrentPrincipal
from infrastructure.security.config import InternalAuthMode, InternalAuthSettings
from infrastructure.security.errors import (
    JwksUnavailableError,
    TokenValidationError,
)
from infrastructure.security.jwks import CachedJwksProvider
from infrastructure.security.jwt_verifier import RS256JWTVerifier


logger = logging.getLogger(__name__)


class PrincipalVerifier(Protocol):
    async def verify(self, token: str) -> CurrentPrincipal:
        ...


VerifierFactory = Callable[[InternalAuthSettings], PrincipalVerifier]

_ENFORCED_EXACT_ROUTES = frozenset(
    {
        ("POST", "/api/chat/edit-resend/stream"),
        ("POST", "/api/chat/regenerate/stream"),
        ("POST", "/api/platform/chat/turns/execute"),
        ("POST", "/api/platform/chat/turns/prepare"),
        ("POST", "/api/research/chat/stream"),
    }
)

_ENFORCED_DYNAMIC_ROUTES = frozenset(
    {
        ("GET", "/api/platform/chat/turns/{request_id}"),
        ("POST", "/api/platform/chat/turns/{request_id}/abort"),
    }
)

_TELEMETRY_ROUTE_TEMPLATES = frozenset(
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
        ("GET", "/api/platform/chat/turns/{request_id}"),
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
        ("POST", "/api/platform/chat/turns/execute"),
        ("POST", "/api/platform/chat/turns/prepare"),
        ("POST", "/api/platform/chat/turns/{request_id}/abort"),
        ("POST", "/api/recommendation/chat"),
        ("POST", "/api/recommendation/chat/stream"),
        ("POST", "/api/research/chat"),
        ("POST", "/api/research/chat/stream"),
        ("POST", "/api/upload"),
        ("PUT", "/api/conversations/{conversation_id}/active-branch"),
    }
)
_SAFE_HTTP_METHODS = frozenset(
    {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
)
_SAFE_PRINCIPAL_TYPES = frozenset({"user", "doctor", "patient"})
_UNKNOWN_ROUTE_TEMPLATE = "/api/{unknown}"


def _build_verifier(settings: InternalAuthSettings) -> PrincipalVerifier:
    return RS256JWTVerifier(settings, CachedJwksProvider(settings))


def install_internal_auth(
    app: FastAPI,
    *,
    settings: InternalAuthSettings | None = None,
    verifier_factory: VerifierFactory = _build_verifier,
) -> None:
    app.add_middleware(
        InternalJWTAuthMiddleware,
        settings=settings,
        verifier_factory=verifier_factory,
    )


def should_authenticate(scope: dict) -> bool:
    path = scope.get("path", "")
    return (
        scope.get("type") == "http"
        and scope.get("method") != "OPTIONS"
        and (path == "/api" or path.startswith("/api/"))
    )


def effective_auth_mode(
    scope: dict,
    configured_mode: InternalAuthMode,
) -> InternalAuthMode:
    if configured_mode is not InternalAuthMode.ENFORCE:
        return configured_mode

    method = scope.get("method")
    path = scope.get("path", "")
    if (method, path) in _ENFORCED_EXACT_ROUTES:
        return InternalAuthMode.ENFORCE

    if any(
        candidate_method == method and _route_matches(path, route_template)
        for candidate_method, route_template in _ENFORCED_DYNAMIC_ROUTES
    ):
        return InternalAuthMode.ENFORCE

    segments = path.split("/")
    is_conversation_path = (
        len(segments) >= 4
        and segments[:3] == ["", "api", "conversations"]
        and bool(segments[3])
    )
    if method == "GET" and is_conversation_path and len(segments) == 4:
        return InternalAuthMode.ENFORCE
    if (
        method == "PUT"
        and is_conversation_path
        and len(segments) == 5
        and segments[4] == "active-branch"
    ):
        return InternalAuthMode.ENFORCE
    return InternalAuthMode.OBSERVE


def normalized_route_template(scope: dict) -> str:
    method = _normalized_method(scope)
    path = scope.get("path", "")
    if not isinstance(path, str):
        return _UNKNOWN_ROUTE_TEMPLATE

    for candidate_method, route_template in _TELEMETRY_ROUTE_TEMPLATES:
        if candidate_method == method and _route_matches(path, route_template):
            return route_template
    return _UNKNOWN_ROUTE_TEMPLATE


def _normalized_method(scope: dict) -> str:
    method = scope.get("method")
    if not isinstance(method, str):
        return "OTHER"
    normalized = method.upper()
    return normalized if normalized in _SAFE_HTTP_METHODS else "OTHER"


def _route_matches(path: str, route_template: str) -> bool:
    path_segments = path.split("/")
    template_segments = route_template.split("/")
    if len(path_segments) != len(template_segments):
        return False
    return all(
        bool(path_segment)
        if template_segment.startswith("{") and template_segment.endswith("}")
        else path_segment == template_segment
        for path_segment, template_segment in zip(
            path_segments, template_segments, strict=True
        )
    )


def _kid_fingerprint(kid: str) -> str:
    return hashlib.sha256(kid.encode("utf-8")).hexdigest()[:16]


def _trusted_kid_fingerprint(token: str) -> str:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except (jwt.PyJWTError, TypeError, ValueError, UnicodeError):
        return "unavailable"
    if not isinstance(kid, str) or not kid:
        return "unavailable"
    try:
        return _kid_fingerprint(kid)
    except UnicodeEncodeError:
        return "unavailable"


def _log_auth_event(
    event: str,
    scope: Scope,
    effective_mode: InternalAuthMode,
    *,
    level: int,
    details: str = "",
) -> None:
    logger.log(
        level,
        "internal_auth_%s mode=%s method=%s route=%s%s",
        event,
        effective_mode.value,
        _normalized_method(scope),
        normalized_route_template(scope),
        details,
        exc_info=None,
    )


class InternalJWTAuthMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: InternalAuthSettings | None = None,
        verifier_factory: VerifierFactory = _build_verifier,
    ) -> None:
        self._app = app
        self._settings = settings or InternalAuthSettings.from_env()
        self._verifier = (
            None
            if self._settings.mode is InternalAuthMode.OFF
            else verifier_factory(self._settings)
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if not should_authenticate(scope):
            await self._app(scope, receive, send)
            return

        effective_mode = effective_auth_mode(scope, self._settings.mode)
        scope.setdefault("state", {})["internal_principal"] = None

        if effective_mode is InternalAuthMode.OFF:
            await self._app(scope, receive, send)
            return

        header_state, token = self._read_bearer_token(scope)
        if header_state == "missing":
            _log_auth_event(
                "missing",
                scope,
                effective_mode,
                level=logging.WARNING,
                details=" reason=legacy_missing",
            )
            if effective_mode is InternalAuthMode.OBSERVE:
                await self._app(scope, receive, send)
            else:
                await self._send_error(
                    scope,
                    receive,
                    send,
                    status_code=401,
                    code="INTERNAL_AUTH_REQUIRED",
                )
            return

        if header_state == "invalid" or token is None:
            _log_auth_event(
                "invalid",
                scope,
                effective_mode,
                level=logging.WARNING,
                details=" reason=header",
            )
            if effective_mode is InternalAuthMode.OBSERVE:
                await self._app(scope, receive, send)
            else:
                await self._send_error(
                    scope,
                    receive,
                    send,
                    status_code=401,
                    code="INTERNAL_AUTH_INVALID",
                )
            return

        try:
            if self._verifier is None:
                raise RuntimeError("internal authentication verifier is missing")
            principal = await self._verifier.verify(token)
        except TokenValidationError:
            _log_auth_event(
                "invalid",
                scope,
                effective_mode,
                level=logging.WARNING,
                details=" reason=token error_type=token_validation",
            )
            if effective_mode is InternalAuthMode.OBSERVE:
                await self._app(scope, receive, send)
            else:
                await self._send_error(
                    scope,
                    receive,
                    send,
                    status_code=401,
                    code="INTERNAL_AUTH_INVALID",
                )
            return
        except JwksUnavailableError:
            _log_auth_event(
                "unavailable",
                scope,
                effective_mode,
                level=logging.WARNING,
                details=" error_type=jwks_unavailable",
            )
            if effective_mode is InternalAuthMode.OBSERVE:
                await self._app(scope, receive, send)
            else:
                await self._send_error(
                    scope,
                    receive,
                    send,
                    status_code=503,
                    code="INTERNAL_AUTH_UNAVAILABLE",
                )
            return
        except Exception:
            _log_auth_event(
                "internal_error",
                scope,
                effective_mode,
                level=logging.ERROR,
                details=" error_type=internal_exception",
            )
            if effective_mode is InternalAuthMode.OBSERVE:
                await self._app(scope, receive, send)
            else:
                await self._send_error(
                    scope,
                    receive,
                    send,
                    status_code=500,
                    code="INTERNAL_AUTH_INTERNAL_ERROR",
                )
            return

        scope["state"]["internal_principal"] = principal
        principal_type = (
            principal.principal_type
            if principal.principal_type in _SAFE_PRINCIPAL_TYPES
            else "unknown"
        )
        _log_auth_event(
            "valid",
            scope,
            effective_mode,
            level=logging.INFO,
            details=(
                f" principal_type={principal_type}"
                f" kid_fp={_trusted_kid_fingerprint(token)}"
            ),
        )
        await self._app(scope, receive, send)

    @staticmethod
    def _read_bearer_token(scope: Scope) -> tuple[str, str | None]:
        authorization_values = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"authorization"
        ]
        if not authorization_values:
            return "missing", None
        if len(authorization_values) != 1:
            return "invalid", None

        try:
            authorization = authorization_values[0].decode("ascii")
        except UnicodeDecodeError:
            return "invalid", None

        scheme, separator, token = authorization.partition(" ")
        if (
            separator != " "
            or scheme.lower() != "bearer"
            or not token
            or any(character.isspace() for character in token)
        ):
            return "invalid", None
        return "valid", token

    @staticmethod
    async def _send_error(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        code: str,
    ) -> None:
        headers = (
            {"WWW-Authenticate": "Bearer"}
            if status_code == 401
            else None
        )
        response = JSONResponse(
            {"code": code},
            status_code=status_code,
            headers=headers,
        )
        await response(scope, receive, send)
