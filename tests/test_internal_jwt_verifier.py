import base64
import time
import unittest
from copy import deepcopy
from typing import Any, Optional

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from domain.security.principal import CurrentPrincipal
from infrastructure.security.config import InternalAuthMode, InternalAuthSettings
from infrastructure.security.errors import (
    InvalidJwksResponseError,
    JwksUnavailableError,
    SigningKeyNotFoundError,
    TokenValidationError,
)
from infrastructure.security.jwt_verifier import RS256JWTVerifier


_KID = "java-key-1"
_REQUIRED_CLAIMS = (
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


def _base64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _public_jwk(private_key: rsa.RSAPrivateKey, kid: str) -> jwt.PyJWK:
    numbers = private_key.public_key().public_numbers()
    return jwt.PyJWK(
        {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": kid,
            "key_ops": ["verify"],
            "n": _base64url_uint(numbers.n),
            "e": _base64url_uint(numbers.e),
        }
    )


class StaticJwksProvider:
    def __init__(
        self,
        signing_key: jwt.PyJWK,
        *,
        error: Optional[Exception] = None,
    ) -> None:
        self.signing_key = signing_key
        self.error = error
        self.requested_kids: list[str] = []

    async def get_signing_key(self, kid: str) -> jwt.PyJWK:
        self.requested_kids.append(kid)
        if self.error is not None:
            raise self.error
        return self.signing_key


class RS256JWTVerifierTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        cls.other_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        cls.signing_key = _public_jwk(cls.private_key, _KID)

    def setUp(self) -> None:
        self.settings = InternalAuthSettings(
            mode=InternalAuthMode.ENFORCE,
            jwks_url="https://backend.example/internal/auth/jwks",
        )
        self.provider = StaticJwksProvider(self.signing_key)
        self.verifier = RS256JWTVerifier(self.settings, self.provider)
        self.now = int(time.time())

    def _claims(self, **overrides: Any) -> dict[str, Any]:
        claims: dict[str, Any] = {
            "iss": self.settings.issuer,
            "aud": [self.settings.audience],
            "sub": "doctor:42",
            "principal_type": "doctor",
            "roles": ["DOCTOR", "USER"],
            "scope": "ai:chat conversation:read",
            "institution_id": "institution-7",
            "tenant_id": "tenant-3",
            "azp": self.settings.authorized_party,
            "ver": 1,
            "jti": "token-123",
            "iat": self.now - 1,
            "nbf": self.now - 1,
            "exp": self.now + 60,
        }
        claims.update(overrides)
        return claims

    def _token(
        self,
        *,
        claims: Optional[dict[str, Any]] = None,
        omit: tuple[str, ...] = (),
        omit_headers: tuple[str, ...] = (),
        headers: Optional[dict[str, Any]] = None,
        private_key: Optional[rsa.RSAPrivateKey] = None,
    ) -> str:
        payload = deepcopy(claims if claims is not None else self._claims())
        for claim in omit:
            payload.pop(claim, None)
        token_headers: dict[str, Any] = {
            "alg": "RS256",
            "kid": _KID,
            "typ": "JWT",
        }
        if headers is not None:
            token_headers.update(headers)
        for header in omit_headers:
            token_headers.pop(header, None)
        return jwt.encode(
            payload,
            private_key or self.private_key,
            algorithm="RS256",
            headers=token_headers,
        )

    async def _assert_invalid(self, token: str) -> None:
        with self.assertRaises(TokenValidationError):
            await self.verifier.verify(token)

    async def test_valid_java_contract_token_creates_current_principal(self):
        principal = await self.verifier.verify(self._token())

        self.assertIsInstance(principal, CurrentPrincipal)
        self.assertEqual(
            principal,
            CurrentPrincipal(
                issuer=self.settings.issuer,
                subject="doctor:42",
                principal_type="doctor",
                roles=frozenset({"DOCTOR", "USER"}),
                scopes=frozenset({"ai:chat", "conversation:read"}),
                institution_id="institution-7",
                tenant_id="tenant-3",
                authorized_party=self.settings.authorized_party,
                schema_version=1,
                token_id="token-123",
                issued_at=self.now - 1,
                not_before=self.now - 1,
                expires_at=self.now + 60,
            ),
        )
        self.assertEqual(self.provider.requested_kids, [_KID])

    async def test_optional_institution_and_tenant_claims_may_be_omitted(self):
        principal = await self.verifier.verify(
            self._token(omit=("institution_id", "tenant_id"))
        )

        self.assertIsNone(principal.institution_id)
        self.assertIsNone(principal.tenant_id)

    async def test_accepts_each_supported_principal_type(self):
        for principal_type in ("user", "doctor", "patient"):
            with self.subTest(principal_type=principal_type):
                principal = await self.verifier.verify(
                    self._token(
                        claims=self._claims(principal_type=principal_type)
                    )
                )
                self.assertEqual(principal.principal_type, principal_type)

    async def test_rejects_wrong_signature_issuer_audience_azp_and_version(self):
        invalid_tokens = {
            "signature": self._token(private_key=self.other_private_key),
            "issuer": self._token(
                claims=self._claims(iss="attacker.example")
            ),
            "audience": self._token(
                claims=self._claims(aud=["other-service"])
            ),
            "azp": self._token(
                claims=self._claims(azp="other-gateway")
            ),
            "version": self._token(claims=self._claims(ver=2)),
        }

        for case, token in invalid_tokens.items():
            with self.subTest(case=case):
                await self._assert_invalid(token)

    async def test_rejects_expired_future_nbf_and_future_iat(self):
        invalid_claims = {
            "expired": self._claims(
                iat=self.now - 120,
                nbf=self.now - 120,
                exp=self.now - 60,
            ),
            "future_nbf": self._claims(
                nbf=self.now + 60,
                exp=self.now + 120,
            ),
            "future_iat": self._claims(
                iat=self.now + 60,
                exp=self.now + 120,
            ),
        }

        for case, claims in invalid_claims.items():
            with self.subTest(case=case):
                await self._assert_invalid(self._token(claims=claims))

    async def test_rejects_each_missing_required_claim(self):
        for claim in _REQUIRED_CLAIMS:
            with self.subTest(claim=claim):
                await self._assert_invalid(self._token(omit=(claim,)))

    async def test_rejects_none_and_hs256_before_jwks_lookup(self):
        none_token = jwt.encode(
            self._claims(),
            key="",
            algorithm="none",
            headers={"kid": _KID, "typ": "JWT"},
        )
        hs256_token = jwt.encode(
            self._claims(),
            key="attacker-controlled-secret-that-is-long-enough",
            algorithm="HS256",
            headers={"kid": _KID, "typ": "JWT"},
        )

        await self._assert_invalid(none_token)
        await self._assert_invalid(hs256_token)

        self.assertEqual(self.provider.requested_kids, [])

    async def test_rejects_remote_key_headers_before_jwks_lookup(self):
        for header_name in ("jku", "x5u"):
            with self.subTest(header_name=header_name):
                token = self._token(
                    headers={header_name: "https://attacker.example/jwks"}
                )
                await self._assert_invalid(token)

        self.assertEqual(self.provider.requested_kids, [])

    async def test_typ_must_be_exactly_jwt(self):
        for invalid_typ in (None, "jwt", "JOSE", "JWT "):
            with self.subTest(typ=invalid_typ):
                await self._assert_invalid(
                    self._token(headers={"typ": invalid_typ})
                )

        self.assertEqual(self.provider.requested_kids, [])

    async def test_audience_must_be_exact_single_element_array(self):
        invalid_audiences = (
            self.settings.audience,
            [self.settings.audience, "other-service"],
            ["other-service", self.settings.audience],
            [],
        )

        for audience in invalid_audiences:
            with self.subTest(audience=audience):
                await self._assert_invalid(
                    self._token(claims=self._claims(aud=audience))
                )

    async def test_identity_string_claims_must_be_non_empty_strings(self):
        for claim in ("sub", "jti", "azp", "principal_type"):
            for invalid_value in ("", "   ", 42, None):
                with self.subTest(claim=claim, value=invalid_value):
                    await self._assert_invalid(
                        self._token(
                            claims=self._claims(**{claim: invalid_value})
                        )
                    )

    async def test_version_must_be_integer_one_not_boolean_or_string(self):
        for version in ("1", True, 1.0, 2, None):
            with self.subTest(version=version):
                await self._assert_invalid(
                    self._token(claims=self._claims(ver=version))
                )

    async def test_rejects_invalid_ttl_boundaries(self):
        invalid_claims = (
            self._claims(iat=self.now, nbf=self.now, exp=self.now),
            self._claims(iat=self.now, nbf=self.now, exp=self.now - 1),
            self._claims(
                iat=self.now - 301,
                nbf=self.now - 301,
                exp=self.now,
            ),
        )

        for claims in invalid_claims:
            with self.subTest(iat=claims["iat"], exp=claims["exp"]):
                await self._assert_invalid(self._token(claims=claims))

    async def test_accepts_maximum_300_second_ttl(self):
        principal = await self.verifier.verify(
            self._token(
                claims=self._claims(
                    iat=self.now - 1,
                    nbf=self.now - 1,
                    exp=self.now + 299,
                )
            )
        )

        self.assertEqual(principal.expires_at - principal.issued_at, 300)

    async def test_roles_must_be_an_array_of_strings(self):
        invalid_roles = (
            "DOCTOR",
            ["DOCTOR", 7],
            {"DOCTOR": True},
            None,
        )

        for roles in invalid_roles:
            with self.subTest(roles=roles):
                await self._assert_invalid(
                    self._token(claims=self._claims(roles=roles))
                )

    async def test_scope_must_be_a_space_delimited_string(self):
        for scope in (["ai:chat"], {"ai:chat": True}, 7, None):
            with self.subTest(scope=scope):
                await self._assert_invalid(
                    self._token(claims=self._claims(scope=scope))
                )

    async def test_rejects_token_larger_than_16_kib_before_jwks_lookup(self):
        await self._assert_invalid("a" * (16 * 1024 + 1))

        self.assertEqual(self.provider.requested_kids, [])

    async def test_invalid_kid_does_not_access_jwks(self):
        await self._assert_invalid(self._token(omit_headers=("kid",)))

        for kid in ("", "a" * 129, "界" * 43):
            with self.subTest(kid=kid):
                await self._assert_invalid(self._token(headers={"kid": kid}))

        self.assertEqual(self.provider.requested_kids, [])

    async def test_unknown_kid_is_token_validation_error(self):
        provider = StaticJwksProvider(
            self.signing_key,
            error=SigningKeyNotFoundError("unknown kid"),
        )
        verifier = RS256JWTVerifier(self.settings, provider)

        with self.assertRaises(TokenValidationError):
            await verifier.verify(self._token())

        self.assertEqual(provider.requested_kids, [_KID])

    async def test_jwks_unavailable_errors_are_preserved(self):
        errors = (
            JwksUnavailableError("network unavailable"),
            InvalidJwksResponseError("server returned malformed JWKS"),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):
                provider = StaticJwksProvider(self.signing_key, error=error)
                verifier = RS256JWTVerifier(self.settings, provider)
                with self.assertRaises(JwksUnavailableError) as raised:
                    await verifier.verify(self._token())
                self.assertIs(raised.exception, error)


if __name__ == "__main__":
    unittest.main()
