import os
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from unittest.mock import patch

from domain.security.principal import CurrentPrincipal
from infrastructure.security.config import InternalAuthMode, InternalAuthSettings


class InternalAuthSettingsTest(unittest.TestCase):
    def test_mode_only_allows_off_observe_and_enforce(self):
        self.assertEqual(
            [mode.value for mode in InternalAuthMode],
            ["off", "observe", "enforce"],
        )
        with self.assertRaises(ValueError):
            InternalAuthMode("warn")

    def test_defaults_keep_authentication_off_and_use_fixed_contract(self):
        settings = InternalAuthSettings()

        self.assertEqual(settings.mode, InternalAuthMode.OFF)
        self.assertEqual(settings.issuer, "eye-agent-backend")
        self.assertEqual(settings.audience, "eyeagent-maincore")
        self.assertEqual(settings.authorized_party, "eye-agent-java-gateway")
        self.assertEqual(settings.algorithm, "RS256")
        self.assertEqual(settings.max_token_ttl_seconds, 300)
        self.assertEqual(settings.negative_cache_max_entries, 256)

    def test_off_mode_does_not_require_jwks_url(self):
        settings = InternalAuthSettings(mode=InternalAuthMode.OFF, jwks_url=None)

        self.assertIsNone(settings.jwks_url)

    def test_observe_and_enforce_modes_require_non_blank_jwks_url(self):
        for mode in (InternalAuthMode.OBSERVE, InternalAuthMode.ENFORCE):
            for jwks_url in (None, "", "   "):
                with self.subTest(mode=mode, jwks_url=jwks_url):
                    with self.assertRaises(ValueError):
                        InternalAuthSettings(mode=mode, jwks_url=jwks_url)

    def test_from_env_reads_supported_server_settings(self):
        environment = {
            "INTERNAL_AUTH_MODE": "observe",
            "INTERNAL_JWT_JWKS_URL": "https://backend.example/internal/jwks",
            "INTERNAL_JWT_CACHE_TTL_SECONDS": "120",
            "INTERNAL_JWT_NEGATIVE_CACHE_SECONDS": "12",
            "INTERNAL_JWT_REFRESH_COOLDOWN_SECONDS": "4",
            "INTERNAL_JWT_REQUEST_TIMEOUT_SECONDS": "1.5",
            "INTERNAL_JWT_CLOCK_SKEW_SECONDS": "8",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = InternalAuthSettings.from_env()

        self.assertEqual(settings.mode, InternalAuthMode.OBSERVE)
        self.assertEqual(
            settings.jwks_url,
            "https://backend.example/internal/jwks",
        )
        self.assertEqual(settings.cache_ttl_seconds, 120)
        self.assertEqual(settings.negative_cache_seconds, 12)
        self.assertEqual(settings.refresh_cooldown_seconds, 4)
        self.assertEqual(settings.request_timeout_seconds, 1.5)
        self.assertEqual(settings.clock_skew_seconds, 8)

    def test_from_env_does_not_override_fixed_cross_language_contract(self):
        environment = {
            "INTERNAL_JWT_ISSUER": "attacker-controlled-issuer",
            "INTERNAL_JWT_AUDIENCE": "attacker-controlled-audience",
            "INTERNAL_JWT_AUTHORIZED_PARTY": "attacker-controlled-party",
            "INTERNAL_JWT_ALGORITHM": "HS256",
            "INTERNAL_JWT_MAX_TOKEN_TTL_SECONDS": "3600",
            "INTERNAL_JWT_NEGATIVE_CACHE_MAX_ENTRIES": "4096",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = InternalAuthSettings.from_env()

        self.assertEqual(settings.issuer, "eye-agent-backend")
        self.assertEqual(settings.audience, "eyeagent-maincore")
        self.assertEqual(settings.authorized_party, "eye-agent-java-gateway")
        self.assertEqual(settings.algorithm, "RS256")
        self.assertEqual(settings.max_token_ttl_seconds, 300)
        self.assertEqual(settings.negative_cache_max_entries, 256)

    def test_direct_construction_and_replace_reject_fixed_contract_changes(self):
        settings = InternalAuthSettings()
        invalid_overrides = {
            "issuer": "other-issuer",
            "audience": "other-audience",
            "authorized_party": "other-authorized-party",
            "algorithm": "HS256",
            "max_token_ttl_seconds": 301,
        }

        for field_name, invalid_value in invalid_overrides.items():
            with self.subTest(operation="construct", field_name=field_name):
                with self.assertRaises(ValueError):
                    InternalAuthSettings(**{field_name: invalid_value})

            with self.subTest(operation="replace", field_name=field_name):
                with self.assertRaises(ValueError):
                    replace(settings, **{field_name: invalid_value})

    def test_from_env_rejects_non_finite_request_timeout(self):
        for request_timeout in ("nan", "inf", "-inf"):
            with self.subTest(request_timeout=request_timeout):
                with patch.dict(
                    os.environ,
                    {"INTERNAL_JWT_REQUEST_TIMEOUT_SECONDS": request_timeout},
                    clear=True,
                ):
                    with self.assertRaises(ValueError):
                        InternalAuthSettings.from_env()

    def test_ttl_cooldown_and_timeout_reject_non_finite_values(self):
        settings = InternalAuthSettings()
        guarded_fields = (
            "cache_ttl_seconds",
            "negative_cache_seconds",
            "refresh_cooldown_seconds",
            "request_timeout_seconds",
        )

        for field_name in guarded_fields:
            for invalid_value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(
                    operation="construct",
                    field_name=field_name,
                    invalid_value=invalid_value,
                ):
                    with self.assertRaises(ValueError):
                        InternalAuthSettings(**{field_name: invalid_value})

                with self.subTest(
                    operation="replace",
                    field_name=field_name,
                    invalid_value=invalid_value,
                ):
                    with self.assertRaises(ValueError):
                        replace(settings, **{field_name: invalid_value})

    def test_clock_skew_must_be_between_zero_and_thirty_seconds(self):
        for clock_skew_seconds in (0, 30):
            with self.subTest(clock_skew_seconds=clock_skew_seconds):
                settings = InternalAuthSettings(
                    clock_skew_seconds=clock_skew_seconds,
                )
                self.assertEqual(settings.clock_skew_seconds, clock_skew_seconds)

        for clock_skew_seconds in (-1, 31):
            with self.subTest(clock_skew_seconds=clock_skew_seconds):
                with self.assertRaises(ValueError):
                    InternalAuthSettings(clock_skew_seconds=clock_skew_seconds)

    def test_ttl_cooldown_and_timeout_settings_must_be_positive(self):
        settings = InternalAuthSettings()
        positive_fields = (
            "cache_ttl_seconds",
            "negative_cache_seconds",
            "refresh_cooldown_seconds",
            "request_timeout_seconds",
            "max_token_ttl_seconds",
        )

        for field_name in positive_fields:
            for invalid_value in (0, -1):
                with self.subTest(
                    operation="construct",
                    field_name=field_name,
                    invalid_value=invalid_value,
                ):
                    with self.assertRaises(ValueError):
                        InternalAuthSettings(**{field_name: invalid_value})

                with self.subTest(
                    operation="replace",
                    field_name=field_name,
                    invalid_value=invalid_value,
                ):
                    with self.assertRaises(ValueError):
                        replace(settings, **{field_name: invalid_value})

    def test_negative_cache_capacity_must_be_between_one_and_256(self):
        for capacity in (1, 256):
            with self.subTest(capacity=capacity):
                settings = InternalAuthSettings(
                    negative_cache_max_entries=capacity,
                )
                self.assertEqual(settings.negative_cache_max_entries, capacity)

        for capacity in (0, 257):
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError):
                    InternalAuthSettings(negative_cache_max_entries=capacity)


class CurrentPrincipalTest(unittest.TestCase):
    def _make_principal(self) -> CurrentPrincipal:
        return CurrentPrincipal(
            issuer="eye-agent-backend",
            subject="doctor-42",
            principal_type="doctor",
            roles={"doctor", "researcher"},
            scopes={"chat:write", "history:read"},
            institution_id="institution-7",
            tenant_id="tenant-3",
            authorized_party="eye-agent-java-gateway",
            schema_version=1,
            token_id="token-99",
            issued_at=1_700_000_000,
            not_before=1_700_000_000,
            expires_at=1_700_000_300,
        )

    def test_principal_is_frozen_slotted_and_uses_frozensets(self):
        principal = self._make_principal()

        self.assertIsInstance(principal.roles, frozenset)
        self.assertIsInstance(principal.scopes, frozenset)
        self.assertFalse(hasattr(principal, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            principal.subject = "doctor-43"

    def test_principal_does_not_retain_raw_token(self):
        principal_fields = {field.name for field in fields(CurrentPrincipal)}

        self.assertNotIn("raw_token", principal_fields)
        self.assertFalse(hasattr(self._make_principal(), "raw_token"))


if __name__ == "__main__":
    unittest.main()
