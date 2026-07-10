import os
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Optional


class InternalAuthMode(str, Enum):
    OFF = "off"
    OBSERVE = "observe"
    ENFORCE = "enforce"


@dataclass(frozen=True, slots=True)
class InternalAuthSettings:
    mode: InternalAuthMode = InternalAuthMode.OFF
    issuer: str = "eye-agent-backend"
    audience: str = "eyeagent-maincore"
    authorized_party: str = "eye-agent-java-gateway"
    jwks_url: Optional[str] = None
    algorithm: str = "RS256"
    cache_ttl_seconds: int = 300
    negative_cache_seconds: int = 15
    refresh_cooldown_seconds: int = 5
    negative_cache_max_entries: int = 256
    request_timeout_seconds: float = 2.0
    clock_skew_seconds: int = 5
    max_token_ttl_seconds: int = 300

    def __post_init__(self) -> None:
        mode = InternalAuthMode(self.mode)
        object.__setattr__(self, "mode", mode)

        fixed_contract = (
            ("issuer", "eye-agent-backend"),
            ("audience", "eyeagent-maincore"),
            ("authorized_party", "eye-agent-java-gateway"),
            ("algorithm", "RS256"),
            ("max_token_ttl_seconds", 300),
        )
        for field_name, expected_value in fixed_contract:
            if getattr(self, field_name) != expected_value:
                raise ValueError(
                    f"{field_name} must be fixed to {expected_value!r}"
                )

        if self.jwks_url is not None:
            object.__setattr__(self, "jwks_url", self.jwks_url.strip())

        if mode is not InternalAuthMode.OFF and not self.jwks_url:
            raise ValueError("JWKS URL is required when internal auth is enabled")

        positive_fields = (
            "cache_ttl_seconds",
            "negative_cache_seconds",
            "refresh_cooldown_seconds",
            "max_token_ttl_seconds",
        )
        for field_name in positive_fields:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")

        if (
            not isfinite(self.request_timeout_seconds)
            or self.request_timeout_seconds <= 0
        ):
            raise ValueError("request_timeout_seconds must be finite and positive")

        if not 0 <= self.clock_skew_seconds <= 30:
            raise ValueError("clock_skew_seconds must be between 0 and 30")

        if not 1 <= self.negative_cache_max_entries <= 256:
            raise ValueError(
                "negative_cache_max_entries must be between 1 and 256"
            )

    @classmethod
    def from_env(cls) -> "InternalAuthSettings":
        defaults = cls()
        return cls(
            mode=InternalAuthMode(
                os.environ.get("INTERNAL_AUTH_MODE", defaults.mode.value)
            ),
            jwks_url=os.environ.get("INTERNAL_JWT_JWKS_URL"),
            cache_ttl_seconds=int(
                os.environ.get(
                    "INTERNAL_JWT_CACHE_TTL_SECONDS",
                    defaults.cache_ttl_seconds,
                )
            ),
            negative_cache_seconds=int(
                os.environ.get(
                    "INTERNAL_JWT_NEGATIVE_CACHE_SECONDS",
                    defaults.negative_cache_seconds,
                )
            ),
            refresh_cooldown_seconds=int(
                os.environ.get(
                    "INTERNAL_JWT_REFRESH_COOLDOWN_SECONDS",
                    defaults.refresh_cooldown_seconds,
                )
            ),
            request_timeout_seconds=float(
                os.environ.get(
                    "INTERNAL_JWT_REQUEST_TIMEOUT_SECONDS",
                    defaults.request_timeout_seconds,
                )
            ),
            clock_skew_seconds=int(
                os.environ.get(
                    "INTERNAL_JWT_CLOCK_SKEW_SECONDS",
                    defaults.clock_skew_seconds,
                )
            ),
        )
