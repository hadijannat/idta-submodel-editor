"""URL validation helpers for outbound provider endpoints."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import SplitResult, urlsplit, urlunsplit

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class UnsafeURL(ValueError):
    """Raised when a URL is unsafe for outbound provider validation."""


def _split_url(url: str) -> SplitResult:
    try:
        parsed = urlsplit(url.strip())
    except ValueError as exc:
        raise UnsafeURL("Base URL is invalid") from exc

    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL("Base URL must use http or https")
    if not parsed.hostname:
        raise UnsafeURL("Base URL must include a hostname")
    if parsed.username or parsed.password:
        raise UnsafeURL("Base URL must not include credentials")

    try:
        parsed.port
    except ValueError as exc:
        raise UnsafeURL("Base URL includes an invalid port") from exc

    return parsed


def _normalize_url(url: str) -> str:
    parsed = _split_url(url)
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path.rstrip("/"),
            parsed.query,
            "",
        )
    )


def _coerce_allowlist(values: object) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, str):
        candidates = values.split(",")
    elif isinstance(values, (list, tuple, set, frozenset)):
        candidates = values
    else:
        return set()

    normalized: set[str] = set()
    for value in candidates:
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            normalized.add(_normalize_url(value))
        except UnsafeURL:
            continue
    return normalized


def get_provider_base_url_allowlist(settings: object) -> set[str]:
    """Return configured base URL allowlist entries when a settings field exists."""
    allowlist: set[str] = set()
    for attr in (
        "llm_provider_base_url_allowlist",
        "llm_base_url_allowlist",
        "ollama_base_url_allowlist",
        "allowed_provider_base_urls",
        "allowed_llm_base_urls",
    ):
        allowlist.update(_coerce_allowlist(getattr(settings, attr, None)))
    return allowlist


def _resolve_host(hostname: str, port: int | None) -> set[IPAddress]:
    try:
        infos = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeURL("Base URL hostname could not be resolved") from exc

    addresses: set[IPAddress] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        address = sockaddr[0]
        try:
            addresses.add(ipaddress.ip_address(address))
        except ValueError as exc:
            raise UnsafeURL("Base URL resolved to an invalid IP address") from exc

    if not addresses:
        raise UnsafeURL("Base URL hostname did not resolve to an IP address")
    return addresses


def _is_unsafe_ip(address: IPAddress) -> bool:
    return (
        not address.is_global
        or address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
        or address.is_reserved
    )


def validate_provider_base_url(
    url: str,
    *,
    configured_ollama_base_url: str,
    allowlist: set[str] | None = None,
) -> str:
    """
    Validate a provider base URL before outbound requests.

    Private, loopback, link-local, metadata, and other non-global resolved
    addresses are rejected unless the URL is explicitly configured as the local
    Ollama endpoint or appears in the configured allowlist.
    """
    normalized = _normalize_url(url)
    allowed_private_urls = {_normalize_url(configured_ollama_base_url)}
    if allowlist:
        allowed_private_urls.update(allowlist)

    parsed = _split_url(url)
    addresses = _resolve_host(parsed.hostname or "", parsed.port)
    if normalized not in allowed_private_urls and any(
        _is_unsafe_ip(address) for address in addresses
    ):
        raise UnsafeURL(
            "Base URL resolves to a loopback, private, link-local, metadata, "
            "or otherwise non-public address"
        )

    return url.strip().rstrip("/")
