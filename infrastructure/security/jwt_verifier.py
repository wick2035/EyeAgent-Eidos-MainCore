import re
from typing import Any

import jwt

from domain.security.principal import CurrentPrincipal
from infrastructure.security.config import InternalAuthSettings
from infrastructure.security.errors import (
    InvalidKidError,
    JwksUnavailableError,
    SigningKeyNotFoundError,
    TokenValidationError,
)
from infrastructure.security.jwks import CachedJwksProvider


REQUIRED_CLAIMS = (
    "iss",
    "aud",
    "sub",
    "principal_type",
    "roles",
    "scope",
    "azp",
    "ver",
    "jti",
    "iat",
    "nbf",
    "exp",
)

_ALLOWED_PRINCIPAL_TYPES = frozenset({"user", "doctor", "patient"})
_MAX_TOKEN_BYTES = 16 * 1024
_MAX_KID_BYTES = 128
_SCOPE_PATTERN = re.compile(r"[A-Za-z0-9:*._-]+(?: [A-Za-z0-9:*._-]+)*")


class RS256JWTVerifier:
    def __init__(
        self,
        settings: InternalAuthSettings,
        jwks_provider: CachedJwksProvider,
    ) -> None:
        self._settings = settings
        self._jwks_provider = jwks_provider

    async def verify(self, token: str) -> CurrentPrincipal:
        self._validate_token_size(token)
        header = self._read_and_validate_header(token)
        kid = header["kid"]

        try:
            signing_key = await self._jwks_provider.get_signing_key(kid)
        except JwksUnavailableError:
            raise
        except (InvalidKidError, SigningKeyNotFoundError) as exc:
            raise TokenValidationError("token signing key is invalid") from exc

        try:
            payload = jwt.decode(
                token,
                key=signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                leeway=self._settings.clock_skew_seconds,
                options={"require": REQUIRED_CLAIMS},
            )
        except (jwt.PyJWTError, TypeError, ValueError, OverflowError) as exc:
            raise TokenValidationError("token cryptographic validation failed") from exc

        return self._principal_from_payload(payload)

    @staticmethod
    def _validate_token_size(token: str) -> None:
        if not isinstance(token, str) or not token:
            raise TokenValidationError("token must be a non-empty string")
        try:
            token_size = len(token.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise TokenValidationError("token must be valid UTF-8") from exc
        if token_size > _MAX_TOKEN_BYTES:
            raise TokenValidationError("token exceeds 16 KiB")

    @staticmethod
    def _read_and_validate_header(token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except (jwt.PyJWTError, TypeError, ValueError, UnicodeError) as exc:
            raise TokenValidationError("token header is invalid") from exc

        if header.get("alg") != "RS256":
            raise TokenValidationError("token algorithm is invalid")
        if header.get("typ") != "JWT":
            raise TokenValidationError("token type is invalid")
        if "jku" in header or "x5u" in header:
            raise TokenValidationError("remote key references are forbidden")

        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise TokenValidationError("token kid is invalid")
        try:
            encoded_kid = kid.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise TokenValidationError("token kid is invalid") from exc
        if len(encoded_kid) > _MAX_KID_BYTES:
            raise TokenValidationError("token kid is invalid")
        return header

    def _principal_from_payload(self, payload: dict[str, Any]) -> CurrentPrincipal:
        if payload.get("aud") != [self._settings.audience]:
            raise TokenValidationError("token audience shape is invalid")

        subject = self._non_empty_string(payload, "sub")
        token_id = self._non_empty_string(payload, "jti")
        authorized_party = self._non_empty_string(payload, "azp")
        if authorized_party != self._settings.authorized_party:
            raise TokenValidationError("token authorized party is invalid")

        principal_type = self._non_empty_string(payload, "principal_type")
        if principal_type not in _ALLOWED_PRINCIPAL_TYPES:
            raise TokenValidationError("token principal type is invalid")

        schema_version = payload.get("ver")
        if type(schema_version) is not int or schema_version != 1:
            raise TokenValidationError("token schema version is invalid")

        roles = payload.get("roles")
        if not isinstance(roles, list) or not all(
            isinstance(role, str) for role in roles
        ):
            raise TokenValidationError("token roles are invalid")

        scope = payload.get("scope")
        if not isinstance(scope, str) or _SCOPE_PATTERN.fullmatch(scope) is None:
            raise TokenValidationError("token scope is invalid")
        scopes = frozenset(scope.split(" "))

        issued_at = self._integer_date(payload, "iat")
        not_before = self._integer_date(payload, "nbf")
        expires_at = self._integer_date(payload, "exp")
        token_ttl = expires_at - issued_at
        if token_ttl <= 0 or token_ttl > self._settings.max_token_ttl_seconds:
            raise TokenValidationError("token lifetime is invalid")

        institution_id = self._optional_non_empty_string(
            payload, "institution_id"
        )
        tenant_id = self._optional_non_empty_string(payload, "tenant_id")

        return CurrentPrincipal(
            issuer=payload["iss"],
            subject=subject,
            principal_type=principal_type,
            roles=frozenset(roles),
            scopes=scopes,
            institution_id=institution_id,
            tenant_id=tenant_id,
            authorized_party=authorized_party,
            schema_version=schema_version,
            token_id=token_id,
            issued_at=issued_at,
            not_before=not_before,
            expires_at=expires_at,
        )

    @staticmethod
    def _non_empty_string(payload: dict[str, Any], claim: str) -> str:
        value = payload.get(claim)
        if not isinstance(value, str) or not value.strip():
            raise TokenValidationError(f"token {claim} is invalid")
        return value

    @staticmethod
    def _optional_non_empty_string(
        payload: dict[str, Any], claim: str
    ) -> str | None:
        if claim not in payload:
            return None
        return RS256JWTVerifier._non_empty_string(payload, claim)

    @staticmethod
    def _integer_date(payload: dict[str, Any], claim: str) -> int:
        value = payload.get(claim)
        if type(value) is not int:
            raise TokenValidationError(f"token {claim} is invalid")
        return value
