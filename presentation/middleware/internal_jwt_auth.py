import logging
from collections.abc import Callable
from typing import Protocol

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
        ("POST", "/api/research/chat/stream"),
    }
)


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
            if effective_mode is InternalAuthMode.OBSERVE:
                self._log_observation("legacy_missing")
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
            if effective_mode is InternalAuthMode.OBSERVE:
                self._log_observation("invalid")
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
            if effective_mode is InternalAuthMode.OBSERVE:
                self._log_observation("invalid")
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
            if effective_mode is InternalAuthMode.OBSERVE:
                self._log_observation("unavailable")
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
            self._log_internal_error()
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
    def _log_observation(outcome: str) -> None:
        logger.warning("internal_auth outcome=%s", outcome)

    @staticmethod
    def _log_internal_error() -> None:
        logger.error(
            "internal_auth outcome=internal_error",
            exc_info=None,
        )

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
