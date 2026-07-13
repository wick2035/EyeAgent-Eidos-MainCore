import base64
from copy import deepcopy
from typing import Any

from cryptography.hazmat.primitives.asymmetric import rsa


_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_NUMBERS = _PRIVATE_KEY.public_key().public_numbers()


def _base64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def rsa_jwk(kid: str = "key-1", **overrides: Any) -> dict[str, Any]:
    jwk: dict[str, Any] = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "key_ops": ["verify"],
        "n": _base64url_uint(_PUBLIC_NUMBERS.n),
        "e": _base64url_uint(_PUBLIC_NUMBERS.e),
    }
    jwk.update(overrides)
    return deepcopy(jwk)


def rsa_jwk_for_key_size(key_size: int, kid: str) -> dict[str, Any]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    public_numbers = private_key.public_key().public_numbers()
    return rsa_jwk(
        kid,
        n=_base64url_uint(public_numbers.n),
        e=_base64url_uint(public_numbers.e),
    )


def jwks(*keys: dict[str, Any]) -> dict[str, Any]:
    return {"keys": [deepcopy(key) for key in keys]}
