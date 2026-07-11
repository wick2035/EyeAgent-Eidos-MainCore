import ipaddress
import json
import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit


_ALLOWLIST_ENV = "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON"
_ALLOW_HTTP_ENV = "PLATFORM_ATTACHMENT_ALLOW_HTTP"


class AttachmentConfigurationError(RuntimeError):
    """附件下载安全配置缺失或无效。"""


@dataclass(frozen=True)
class AllowedAttachmentEndpoint:
    scheme: str
    host: str
    port: int
    ip: str


@dataclass(frozen=True)
class AttachmentDownloadSettings:
    endpoints: tuple[AllowedAttachmentEndpoint, ...]
    allow_http: bool = False

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "AttachmentDownloadSettings":
        source = os.environ if environ is None else environ
        raw_allowlist = source.get(_ALLOWLIST_ENV)
        if not raw_allowlist:
            raise AttachmentConfigurationError(
                "PLATFORM_ATTACHMENT_DOWNLOAD_ALLOWLIST_JSON is required"
            )

        try:
            decoded = json.loads(raw_allowlist)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AttachmentConfigurationError("invalid attachment allowlist JSON") from exc

        if not isinstance(decoded, list) or not decoded:
            raise AttachmentConfigurationError("attachment allowlist must not be empty")

        endpoints: list[AllowedAttachmentEndpoint] = []
        for entry in decoded:
            if not isinstance(entry, list) or len(entry) != 4:
                raise AttachmentConfigurationError(
                    "each attachment allowlist entry must be a JSON four-tuple"
                )
            scheme, host, port, ip_literal = entry
            if not isinstance(scheme, str) or scheme not in {"https", "http"}:
                raise AttachmentConfigurationError("unsupported attachment URL scheme")
            if not isinstance(host, str):
                raise AttachmentConfigurationError("attachment host must be a string")
            normalized_host = _normalize_exact_host(host)
            if isinstance(port, bool) or not isinstance(port, int):
                raise AttachmentConfigurationError("attachment port must be an integer")
            if not 1 <= port <= 65535:
                raise AttachmentConfigurationError("attachment port is out of range")
            if not isinstance(ip_literal, str) or "/" in ip_literal:
                raise AttachmentConfigurationError("attachment IP must be an exact address")
            try:
                normalized_ip = str(ipaddress.ip_address(ip_literal))
            except ValueError as exc:
                raise AttachmentConfigurationError(
                    "attachment IP must be an exact address"
                ) from exc
            try:
                host_ip = str(ipaddress.ip_address(normalized_host))
            except ValueError:
                host_ip = None
            if host_ip is not None and host_ip != normalized_ip:
                raise AttachmentConfigurationError(
                    "literal attachment host must equal its pinned IP"
                )
            endpoints.append(
                AllowedAttachmentEndpoint(
                    scheme=scheme,
                    host=normalized_host,
                    port=port,
                    ip=normalized_ip,
                )
            )

        raw_allow_http = source.get(_ALLOW_HTTP_ENV, "false")
        if not isinstance(raw_allow_http, str) or raw_allow_http.lower() not in {
            "true",
            "false",
        }:
            raise AttachmentConfigurationError(
                "PLATFORM_ATTACHMENT_ALLOW_HTTP must be true or false"
            )
        return cls(
            endpoints=tuple(dict.fromkeys(endpoints)),
            allow_http=raw_allow_http.lower() == "true",
        )

    def endpoints_for_url(self, url: str) -> tuple[AllowedAttachmentEndpoint, ...]:
        if not isinstance(url, str) or not url or any(
            ord(character) < 0x20 for character in url
        ):
            raise AttachmentConfigurationError("attachment URL is invalid")
        if "#" in url:
            raise AttachmentConfigurationError("attachment URL fragments are forbidden")
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise AttachmentConfigurationError("attachment URL is invalid") from exc
        if (
            parsed.username is not None
            or parsed.password is not None
            or not parsed.scheme
            or host is None
        ):
            raise AttachmentConfigurationError("attachment URL authority is invalid")
        scheme = parsed.scheme.lower()
        if scheme not in {"https", "http"}:
            raise AttachmentConfigurationError("attachment URL scheme is forbidden")
        if scheme == "http" and not self.allow_http:
            raise AttachmentConfigurationError("attachment HTTP downloads are disabled")
        normalized_host = _normalize_exact_host(host)
        effective_port = port if port is not None else (443 if scheme == "https" else 80)
        matches = tuple(
            endpoint
            for endpoint in self.endpoints
            if endpoint.scheme == scheme
            and endpoint.host == normalized_host
            and endpoint.port == effective_port
        )
        if not matches:
            raise AttachmentConfigurationError("attachment URL is not allowlisted")
        return matches


def _normalize_exact_host(host: str) -> str:
    if (
        not host
        or host != host.strip()
        or host.endswith(".")
        or "*" in host
        or "/" in host
        or "\\" in host
    ):
        raise AttachmentConfigurationError("attachment host must be exact")
    try:
        normalized = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise AttachmentConfigurationError("attachment host is invalid") from exc
    if not normalized or any(character.isspace() for character in normalized):
        raise AttachmentConfigurationError("attachment host is invalid")
    return normalized
