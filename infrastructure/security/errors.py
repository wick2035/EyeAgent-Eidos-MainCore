class JwksError(Exception):
    """Base error for JWKS lookup failures."""


class InvalidKidError(JwksError):
    """The token key identifier is not safe to process."""


class SigningKeyNotFoundError(JwksError):
    """No signing key exists for the requested key identifier."""


class JwksUnavailableError(JwksError):
    """The configured JWKS cannot currently be obtained safely."""


class InvalidJwksResponseError(JwksUnavailableError):
    """The JWKS response violates the fixed internal authentication contract."""
