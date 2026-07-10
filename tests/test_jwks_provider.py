import asyncio
import json
import unittest
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from typing import Any
from unittest.mock import patch

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


class BlockingFetcher:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response
        self.call_count = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self) -> Mapping[str, Any]:
        self.call_count += 1
        self.started.set()
        await self.release.wait()
        return deepcopy(self.response)


class ChunkedContent:
    def __init__(self, *chunks: bytes) -> None:
        self.chunks = list(chunks)
        self.read_sizes: list[int] = []
        self.bytes_returned = 0

    async def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        result = chunk[:size]
        if len(chunk) > size:
            self.chunks.insert(0, chunk[size:])
        self.bytes_returned += len(result)
        return result


class NoReadContent:
    def __init__(self) -> None:
        self.read_calls = 0

    async def read(self, size: int) -> bytes:
        self.read_calls += 1
        raise AssertionError(f"body must not be read with size={size}")


class FakeResponse:
    def __init__(
        self,
        content: object,
        *,
        status: int = 200,
        content_length: int | None = None,
    ) -> None:
        self.status = status
        self.content_length = content_length
        self.content = content

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class RecordingClientSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> "RecordingClientSession":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append((url, kwargs))
        return self.response


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

    async def test_concurrent_same_kid_uses_one_overlapping_fetch(self):
        fetcher = BlockingFetcher(jwks(rsa_jwk("rotated")))
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=FakeClock()
        )

        first = asyncio.create_task(provider.get_signing_key("rotated"))
        await asyncio.wait_for(fetcher.started.wait(), timeout=1)
        followers = [
            asyncio.create_task(provider.get_signing_key("rotated"))
            for _ in range(19)
        ]
        await asyncio.sleep(0)

        self.assertEqual(fetcher.call_count, 1)
        self.assertTrue(all(not task.done() for task in followers))
        fetcher.release.set()
        keys = await asyncio.gather(first, *followers)

        self.assertTrue(all(key.key_id == "rotated" for key in keys))
        self.assertEqual(fetcher.call_count, 1)

    async def test_concurrent_different_unknown_kids_share_one_fetch(self):
        fetcher = BlockingFetcher(jwks(rsa_jwk("current")))
        provider = CachedJwksProvider(
            auth_settings(), fetcher=fetcher, clock=FakeClock()
        )

        first = asyncio.create_task(provider.get_signing_key("missing-a"))
        await asyncio.wait_for(fetcher.started.wait(), timeout=1)
        second = asyncio.create_task(provider.get_signing_key("missing-b"))
        await asyncio.sleep(0)

        self.assertEqual(fetcher.call_count, 1)
        self.assertFalse(second.done())
        fetcher.release.set()
        results = await asyncio.gather(
            first,
            second,
            return_exceptions=True,
        )

        self.assertTrue(
            all(isinstance(result, SigningKeyNotFoundError) for result in results)
        )
        self.assertEqual(fetcher.call_count, 1)

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

    async def test_expired_cache_does_not_bypass_refresh_cooldown(self):
        clock = FakeClock()
        fetcher = SequenceFetcher(
            jwks(rsa_jwk("current")), OSError("unexpected refresh")
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
        with self.assertRaises(JwksUnavailableError):
            await provider.get_signing_key("current")

        self.assertEqual(fetcher.call_count, 1)

    async def test_failed_expired_cache_refresh_is_not_repeated_in_cooldown(self):
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
        clock.advance(5.1)

        with self.assertRaises(JwksUnavailableError):
            await provider.get_signing_key("current")
        clock.advance(1)
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

    async def test_default_fetcher_accumulates_chunked_body_to_eof(self):
        body = json.dumps(jwks(rsa_jwk("current"))).encode("utf-8")
        content = ChunkedContent(body[:7], body[7:31], body[31:])
        session = RecordingClientSession(FakeResponse(content))

        with patch(
            "infrastructure.security.jwks.aiohttp.ClientSession",
            return_value=session,
        ):
            provider = CachedJwksProvider(auth_settings(), clock=FakeClock())
            key = await provider.get_signing_key("current")

        self.assertEqual(key.key_id, "current")
        self.assertGreaterEqual(len(content.read_sizes), 4)
        self.assertEqual(content.bytes_returned, len(body))

    async def test_default_fetcher_rejects_chunked_body_at_65537_bytes(self):
        content = ChunkedContent(b"x" * 32_768, b"y" * 32_769)
        session = RecordingClientSession(FakeResponse(content))

        with patch(
            "infrastructure.security.jwks.aiohttp.ClientSession",
            return_value=session,
        ):
            provider = CachedJwksProvider(auth_settings(), clock=FakeClock())
            with self.assertRaises(InvalidJwksResponseError):
                await provider.get_signing_key("current")

        self.assertEqual(content.bytes_returned, 65_537)
        self.assertGreaterEqual(len(content.read_sizes), 2)

    async def test_default_fetcher_rejects_oversized_content_length_without_read(self):
        content = NoReadContent()
        session = RecordingClientSession(
            FakeResponse(content, content_length=65_537)
        )

        with patch(
            "infrastructure.security.jwks.aiohttp.ClientSession",
            return_value=session,
        ):
            provider = CachedJwksProvider(auth_settings(), clock=FakeClock())
            with self.assertRaises(InvalidJwksResponseError):
                await provider.get_signing_key("current")

        self.assertEqual(content.read_calls, 0)

    async def test_default_fetcher_uses_two_second_timeout_without_redirects(self):
        body = json.dumps(jwks(rsa_jwk("current"))).encode("utf-8")
        session = RecordingClientSession(
            FakeResponse(ChunkedContent(body), content_length=len(body))
        )

        with patch(
            "infrastructure.security.jwks.aiohttp.ClientSession",
            return_value=session,
        ) as session_factory:
            provider = CachedJwksProvider(
                auth_settings(request_timeout_seconds=10),
                clock=FakeClock(),
            )
            await provider.get_signing_key("current")

        timeout = session_factory.call_args.kwargs["timeout"]
        self.assertEqual(timeout.total, 2.0)
        self.assertEqual(
            session.requests,
            [
                (
                    "https://backend.example/internal/auth/jwks",
                    {"allow_redirects": False},
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
