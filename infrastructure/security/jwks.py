import asyncio
import hashlib
import ipaddress
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Optional
from urllib.parse import urlsplit

import aiohttp
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from infrastructure.security.config import InternalAuthSettings
from infrastructure.security.errors import (
    InvalidJwksResponseError,
    InvalidKidError,
    JwksUnavailableError,
    SigningKeyNotFoundError,
)


JwksFetcher = Callable[[], Awaitable[Mapping[str, Any]]]
MonotonicClock = Callable[[], float]

_MAX_RESPONSE_BYTES = 64 * 1024
_MAX_KID_BYTES = 128
_MIN_RSA_BITS = 2048
_RSA_PRIVATE_PARAMETERS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth"})

logger = logging.getLogger(__name__)


class CachedJwksProvider:
    def __init__(
        self,
        settings: InternalAuthSettings,
        *,
        fetcher: Optional[JwksFetcher] = None,
        clock: MonotonicClock = time.monotonic,
    ) -> None:
        self._settings = settings
        self._clock = clock
        if fetcher is None:
            self._validate_url(settings.jwks_url)
            self._fetcher = self._fetch_remote_jwks
        else:
            self._fetcher = fetcher

        self._keys: dict[str, jwt.PyJWK] = {}
        self._cache_expires_at: Optional[float] = None
        self._negative_cache: OrderedDict[str, float] = OrderedDict()
        self._last_refresh_at: Optional[float] = None
        self._last_refresh_error: Optional[JwksUnavailableError] = None
        self._refresh_lock = asyncio.Lock()

    async def get_signing_key(self, kid: str) -> jwt.PyJWK:
        self._validate_kid(kid)
        now = self._clock()

        key = self._get_fresh_key(kid, now)
        if key is not None:
            return key
        if self._cache_is_fresh(now) and self._is_negatively_cached(kid, now):
            raise SigningKeyNotFoundError(f"no signing key for kid {kid!r}")

        async with self._refresh_lock:
            now = self._clock()
            key = self._get_fresh_key(kid, now)
            if key is not None:
                return key
            if self._cache_is_fresh(now) and self._is_negatively_cached(kid, now):
                raise SigningKeyNotFoundError(f"no signing key for kid {kid!r}")

            if self._refresh_is_cooling_down(now):
                if self._cache_is_fresh(now):
                    self._remember_missing(kid, now)
                    raise SigningKeyNotFoundError(
                        f"no signing key for kid {kid!r}"
                    )
                raise JwksUnavailableError(
                    "JWKS refresh is cooling down after the previous attempt"
                ) from self._last_refresh_error

            await self._refresh()
            now = self._clock()
            key = self._get_fresh_key(kid, now)
            if key is not None:
                return key

            self._remember_missing(kid, now)
            raise SigningKeyNotFoundError(f"no signing key for kid {kid!r}")

    def _cache_is_fresh(self, now: float) -> bool:
        return (
            self._cache_expires_at is not None
            and now < self._cache_expires_at
        )

    def _get_fresh_key(self, kid: str, now: float) -> Optional[jwt.PyJWK]:
        if not self._cache_is_fresh(now):
            return None
        return self._keys.get(kid)

    def _refresh_is_cooling_down(self, now: float) -> bool:
        return (
            self._last_refresh_at is not None
            and now - self._last_refresh_at
            < self._settings.refresh_cooldown_seconds
        )

    def _is_negatively_cached(self, kid: str, now: float) -> bool:
        self._prune_negative_cache(now)
        expires_at = self._negative_cache.get(kid)
        return expires_at is not None and now < expires_at

    def _remember_missing(self, kid: str, now: float) -> None:
        self._prune_negative_cache(now)
        self._negative_cache.pop(kid, None)
        self._negative_cache[kid] = (
            now + self._settings.negative_cache_seconds
        )
        while (
            len(self._negative_cache)
            > self._settings.negative_cache_max_entries
        ):
            self._negative_cache.popitem(last=False)

    def _prune_negative_cache(self, now: float) -> None:
        expired = [
            kid
            for kid, expires_at in self._negative_cache.items()
            if now >= expires_at
        ]
        for kid in expired:
            self._negative_cache.pop(kid, None)

    async def _refresh(self) -> None:
        try:
            payload = await self._fetcher()
            keys = self._parse_jwks(payload)
        except InvalidJwksResponseError as exc:
            self._record_refresh_failure(exc)
            raise
        except Exception as exc:
            unavailable = JwksUnavailableError("unable to fetch JWKS")
            self._record_refresh_failure(unavailable)
            raise unavailable from exc

        refreshed_at = self._clock()
        self._keys = keys
        self._cache_expires_at = (
            refreshed_at + self._settings.cache_ttl_seconds
        )
        self._last_refresh_at = refreshed_at
        self._last_refresh_error = None
        for kid in keys:
            self._negative_cache.pop(kid, None)
        logger.info(
            "jwks_refresh_success key_count=%d kid_fps=%s",
            len(keys),
            ",".join(sorted(self._kid_fingerprint(kid) for kid in keys)),
        )

    def _record_refresh_failure(self, error: JwksUnavailableError) -> None:
        self._last_refresh_at = self._clock()
        self._last_refresh_error = error
        error_type = (
            "invalid_response"
            if isinstance(error, InvalidJwksResponseError)
            else "unavailable"
        )
        logger.warning(
            "jwks_refresh_failed error_type=%s",
            error_type,
            exc_info=None,
        )

    @staticmethod
    def _kid_fingerprint(kid: str) -> str:
        return hashlib.sha256(kid.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _parse_jwks(
        cls, payload: Mapping[str, Any]
    ) -> dict[str, jwt.PyJWK]:
        if not isinstance(payload, Mapping):
            raise InvalidJwksResponseError("JWKS response must be an object")
        raw_keys = payload.get("keys")
        if not isinstance(raw_keys, list) or not raw_keys:
            raise InvalidJwksResponseError(
                "JWKS response must contain a non-empty keys array"
            )

        parsed_keys: dict[str, jwt.PyJWK] = {}
        for raw_key in raw_keys:
            if not isinstance(raw_key, Mapping):
                raise InvalidJwksResponseError("each JWK must be an object")
            jwk_data = dict(raw_key)
            kid = jwk_data.get("kid")
            try:
                cls._validate_kid(kid)
            except InvalidKidError as exc:
                raise InvalidJwksResponseError(
                    "each JWK must contain a valid kid"
                ) from exc

            if kid in parsed_keys:
                raise InvalidJwksResponseError(f"duplicate JWK kid {kid!r}")
            if (
                jwk_data.get("kty") != "RSA"
                or jwk_data.get("use") != "sig"
                or jwk_data.get("alg") != "RS256"
            ):
                raise InvalidJwksResponseError(
                    "JWK must use kty=RSA, use=sig, and alg=RS256"
                )
            key_ops = jwk_data.get("key_ops")
            if key_ops is not None and (
                not isinstance(key_ops, list)
                or not all(isinstance(operation, str) for operation in key_ops)
                or "verify" not in key_ops
            ):
                raise InvalidJwksResponseError(
                    "JWK key_ops must include verify when present"
                )
            if _RSA_PRIVATE_PARAMETERS.intersection(jwk_data):
                raise InvalidJwksResponseError(
                    "JWKS must not contain RSA private parameters"
                )

            try:
                parsed = jwt.PyJWK(jwk_data, algorithm=None)
            except Exception as exc:
                raise InvalidJwksResponseError("invalid RSA public JWK") from exc
            if not isinstance(parsed.key, RSAPublicKey):
                raise InvalidJwksResponseError("JWK must contain an RSA public key")
            if parsed.key.key_size < _MIN_RSA_BITS:
                raise InvalidJwksResponseError(
                    "RSA public JWK must be at least 2048 bits"
                )
            parsed_keys[kid] = parsed

        return parsed_keys

    @staticmethod
    def _validate_kid(kid: object) -> None:
        if not isinstance(kid, str) or not kid.strip():
            raise InvalidKidError("kid must be a non-empty string")
        try:
            encoded = kid.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise InvalidKidError("kid must be valid UTF-8") from exc
        if len(encoded) > _MAX_KID_BYTES:
            raise InvalidKidError("kid must not exceed 128 UTF-8 bytes")

    def _validate_url(self, url: Optional[str]) -> None:
        if not url:
            raise ValueError("JWKS URL is required")
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("JWKS URL must use http or https")
        if parsed.scheme == "https":
            return
        try:
            hostname = parsed.hostname
        except ValueError as exc:
            raise ValueError("JWKS URL hostname is invalid") from exc
        if self._is_loopback_host(hostname):
            return
        if not self._settings.allow_insecure_non_loopback_http_jwks:
            raise ValueError(
                "non-loopback HTTP JWKS requires explicit insecure opt-in"
            )

    @staticmethod
    def _is_loopback_host(hostname: Optional[str]) -> bool:
        if hostname is None:
            return False
        if hostname.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            return False

    async def _fetch_remote_jwks(self) -> Mapping[str, Any]:
        url = self._settings.jwks_url
        self._validate_url(url)
        timeout = aiohttp.ClientTimeout(
            total=min(float(self._settings.request_timeout_seconds), 2.0)
        )
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    url,
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise JwksUnavailableError(
                            f"JWKS endpoint returned HTTP {response.status}"
                        )
                    if (
                        response.content_length is not None
                        and response.content_length > _MAX_RESPONSE_BYTES
                    ):
                        raise InvalidJwksResponseError(
                            "JWKS response exceeds 64 KiB"
                        )

                    body = bytearray()
                    while len(body) <= _MAX_RESPONSE_BYTES:
                        chunk = await response.content.read(
                            _MAX_RESPONSE_BYTES + 1 - len(body)
                        )
                        if not chunk:
                            break
                        body.extend(chunk)
        except JwksUnavailableError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise JwksUnavailableError("unable to fetch JWKS") from exc

        if len(body) > _MAX_RESPONSE_BYTES:
            raise InvalidJwksResponseError(
                "JWKS response exceeds 64 KiB"
            )
        try:
            payload = json.loads(bytes(body).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidJwksResponseError(
                "JWKS response is not valid UTF-8 JSON"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidJwksResponseError("JWKS response must be an object")
        return payload
