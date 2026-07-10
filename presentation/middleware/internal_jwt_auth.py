import logging
from collections.abc import Callable
from typing import Protocol

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


def _build_verifier(settings: InternalAuthSettings) -> PrincipalVerifier:
    return RS256JWTVerifier(settings, CachedJwksProvider(settings))


def should_authenticate(scope: dict) -> bool:
    path = scope.get("path", "")
    return (
        scope.get("type") == "http"
        and scope.get("method") != "OPTIONS"
        and (path == "/api" or path.startswith("/api/"))
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

        scope.setdefault("state", {})["internal_principal"] = None

        if self._settings.mode is InternalAuthMode.OFF:
            await self._app(scope, receive, send)
            return

        header_state, token = self._read_bearer_token(scope)
        if header_state == "missing":
            if self._settings.mode is InternalAuthMode.OBSERVE:
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
            if self._settings.mode is InternalAuthMode.OBSERVE:
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
            if self._settings.mode is InternalAuthMode.OBSERVE:
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
            if self._settings.mode is InternalAuthMode.OBSERVE:
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
        except Exception as error:
            self._log_internal_error(error)
            if self._settings.mode is InternalAuthMode.OBSERVE:
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
    def _log_internal_error(error: Exception) -> None:
        sanitized_error = RuntimeError(
            "internal authentication verifier failed"
        )
        logger.exception(
            "internal_auth outcome=internal_error",
            exc_info=(
                RuntimeError,
                sanitized_error,
                error.__traceback__,
            ),
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
