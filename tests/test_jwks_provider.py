import asyncio
import unittest
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from typing import Any

import jwt

from infrastructure.security.config import InternalAuthMode, InternalAuthSettings
from infrastructure.security.errors import (
    InvalidJwksResponseError,
    InvalidKidError,
    JwksUnavailableError,
    SigningKeyNotFoundError,
)
from infrastructure.security.jwks import CachedJwksProvider
from tests.jwt_test_utils import jwks, rsa_jwk


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class SequenceFetcher:
    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.call_count = 0

    async def __call__(self) -> Mapping[str, Any]:
        self.call_count += 1
        if not self.responses:
            raise AssertionError("unexpected JWKS fetch")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        assert isinstance(response, Mapping)
        return deepcopy(response)


def auth_settings(**overrides: Any) -> InternalAuthSettings:
    settings = InternalAuthSettings(
        mode=InternalAuthMode.ENFORCE,
        jwks_url="https://backend.example/internal/auth/jwks",
        cache_ttl_seconds=60,
        negative_cache_seconds=15,
        refresh_cooldown_seconds=5,
    )
    return replace(settings, **overrides)


class CachedJwksProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_first_lookup_fetches_once_and_returns_pyjwk(self):
        fetcher = SequenceFetcher(jwks(rsa_jwk("current")))
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=FakeClock()
        )

        key = await provider.get_signing_key("current")

        self.assertIsInstance(key, jwt.PyJWK)
        self.assertEqual(key.key_id, "current")
        self.assertEqual(fetcher.call_count, 1)

    async def test_fresh_known_key_does_not_refetch(self):
        clock = FakeClock()
        fetcher = SequenceFetcher(jwks(rsa_jwk("current")))
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=clock
        )

        first = await provider.get_signing_key("current")
        clock.advance(59)
        second = await provider.get_signing_key("current")

        self.assertIs(first, second)
        self.assertEqual(fetcher.call_count, 1)

    async def test_unknown_kid_refreshes_once_after_cooldown(self):
        clock = FakeClock()
        fetcher = SequenceFetcher(
            jwks(rsa_jwk("current")),
            jwks(rsa_jwk("current"), rsa_jwk("rotated")),
        )
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=clock
        )
        await provider.get_signing_key("current")
        clock.advance(6)

        key = await provider.get_signing_key("rotated")

        self.assertEqual(key.key_id, "rotated")
        self.assertEqual(fetcher.call_count, 2)

    async def test_concurrent_unknown_kid_uses_single_flight_refresh(self):
        clock = FakeClock()
        fetcher = SequenceFetcher(
            jwks(rsa_jwk("current")),
            jwks(rsa_jwk("current"), rsa_jwk("rotated")),
        )
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=clock
        )
        await provider.get_signing_key("current")
        clock.advance(6)

        keys = await asyncio.gather(
            *(provider.get_signing_key("rotated") for _ in range(20))
        )

        self.assertTrue(all(key.key_id == "rotated" for key in keys))
        self.assertEqual(fetcher.call_count, 2)

    async def test_unknown_kid_is_negatively_cached_for_fifteen_seconds(self):
        clock = FakeClock()
        fetcher = SequenceFetcher(
            jwks(rsa_jwk("current")),
            jwks(rsa_jwk("current")),
        )
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=clock
        )

        with self.assertRaises(SigningKeyNotFoundError):
            await provider.get_signing_key("missing")
        clock.advance(14.9)
        with self.assertRaises(SigningKeyNotFoundError):
            await provider.get_signing_key("missing")
        self.assertEqual(fetcher.call_count, 1)

        clock.advance(0.2)
        with self.assertRaises(SigningKeyNotFoundError):
            await provider.get_signing_key("missing")
        self.assertEqual(fetcher.call_count, 2)

    async def test_negative_cache_is_bounded_and_evicts_oldest_entry(self):
        clock = FakeClock()
        response = jwks(rsa_jwk("current"))
        fetcher = SequenceFetcher(response, response, response, response)
        provider = CachedJwksProvider(
            auth_settings(
                negative_cache_seconds=100,
                negative_cache_max_entries=2,
                refresh_cooldown_seconds=1,
            ),
            fetcher=fetcher,
            clock=clock,
        )

        for kid in ("missing-a", "missing-b", "missing-c"):
            with self.assertRaises(SigningKeyNotFoundError):
                await provider.get_signing_key(kid)
            clock.advance(2)

        with self.assertRaises(SigningKeyNotFoundError):
            await provider.get_signing_key("missing-a")
        self.assertEqual(fetcher.call_count, 4)

    async def test_global_cooldown_blocks_different_unknown_kids(self):
        clock = FakeClock()
        fetcher = SequenceFetcher(jwks(rsa_jwk("current")))
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=clock
        )

        with self.assertRaises(SigningKeyNotFoundError):
            await provider.get_signing_key("missing-a")
        clock.advance(1)
        with self.assertRaises(SigningKeyNotFoundError):
            await provider.get_signing_key("missing-b")

        self.assertEqual(fetcher.call_count, 1)

    async def test_one_hundred_random_kids_fetch_at_most_once_per_cooldown(self):
        fetcher = SequenceFetcher(jwks(rsa_jwk("current")))
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=FakeClock()
        )

        for index in range(100):
            with self.assertRaises(SigningKeyNotFoundError):
                await provider.get_signing_key(f"random-{index}")

        self.assertEqual(fetcher.call_count, 1)

    async def test_kid_must_be_non_empty_string_with_at_most_128_utf8_bytes(self):
        fetcher = SequenceFetcher(jwks(rsa_jwk("current")))
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=FakeClock()
        )

        for invalid_kid in ("", "a" * 129, "界" * 43, None, 42):
            with self.subTest(kid=invalid_kid):
                with self.assertRaises(InvalidKidError):
                    await provider.get_signing_key(invalid_kid)  # type: ignore[arg-type]

        self.assertEqual(fetcher.call_count, 0)

    async def test_rejects_jwks_keys_outside_fixed_rsa_signing_contract(self):
        invalid_keys = (
            rsa_jwk("bad", kty="EC"),
            rsa_jwk("bad", use="enc"),
            rsa_jwk("bad", alg="RS512"),
            rsa_jwk("bad", key_ops=["sign"]),
            {key: value for key, value in rsa_jwk("bad").items() if key != "kid"},
        )

        for invalid_key in invalid_keys:
            with self.subTest(jwk=invalid_key):
                provider = CachedJwksProvider(
                    auth_settings(),
                    fetcher=SequenceFetcher(jwks(invalid_key)),
                    clock=FakeClock(),
                )
                with self.assertRaises(InvalidJwksResponseError):
                    await provider.get_signing_key("bad")

    async def test_rejects_duplicate_kids(self):
        provider = CachedJwksProvider(
            auth_settings(),
            fetcher=SequenceFetcher(jwks(rsa_jwk("dup"), rsa_jwk("dup"))),
            clock=FakeClock(),
        )

        with self.assertRaises(InvalidJwksResponseError):
            await provider.get_signing_key("dup")

    async def test_rejects_private_rsa_parameters(self):
        for private_parameter in ("d", "p", "q", "dp", "dq", "qi", "oth"):
            with self.subTest(private_parameter=private_parameter):
                provider = CachedJwksProvider(
                    auth_settings(),
                    fetcher=SequenceFetcher(
                        jwks(rsa_jwk("private", **{private_parameter: "AQAB"}))
                    ),
                    clock=FakeClock(),
                )
                with self.assertRaises(InvalidJwksResponseError):
                    await provider.get_signing_key("private")

    async def test_expired_cache_fails_closed_when_refresh_fails(self):
        clock = FakeClock()
        fetcher = SequenceFetcher(
            jwks(rsa_jwk("current")), OSError("backend unavailable")
        )
        provider = CachedJwksProvider(
            auth_settings(
                cache_ttl_seconds=1,
                refresh_cooldown_seconds=5,
            ),
            fetcher=fetcher,
            clock=clock,
        )
        await provider.get_signing_key("current")
        clock.advance(1.1)

        with self.assertRaises(JwksUnavailableError):
            await provider.get_signing_key("current")

        self.assertEqual(fetcher.call_count, 2)

    async def test_no_cache_and_unreachable_backend_raises_unavailable(self):
        provider = CachedJwksProvider(
            auth_settings(),
            fetcher=SequenceFetcher(OSError("backend unavailable")),
            clock=FakeClock(),
        )

        with self.assertRaises(JwksUnavailableError):
            await provider.get_signing_key("current")

    def test_default_fetcher_rejects_non_http_jwks_url(self):
        with self.assertRaises(ValueError):
            CachedJwksProvider(
                auth_settings(jwks_url="file:///tmp/jwks.json"),
                clock=FakeClock(),
            )


if __name__ == "__main__":
    unittest.main()
